#!/usr/bin/env bash
set -euo pipefail

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd gcloud
require_cmd curl
require_cmd python3
require_cmd mktemp

PROJECT_ID="${PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-profile-bot-api-usc}"
ALERT_PREFIX="${ALERT_PREFIX:-Profile Bot API}"
DASHBOARD_DISPLAY_NAME="${DASHBOARD_DISPLAY_NAME:-Profile Bot API - OpenAI Health (${REGION})}"
NOTIFICATION_CHANNELS="${NOTIFICATION_CHANNELS:-}"
ALERT_AUTO_CLOSE="${ALERT_AUTO_CLOSE:-1800s}"

METRIC_TOTAL="${METRIC_TOTAL:-profile_bot_openai_calls_total}"
METRIC_FAILED="${METRIC_FAILED:-profile_bot_openai_calls_failed_total}"
METRIC_TIMEOUT="${METRIC_TIMEOUT:-profile_bot_openai_calls_timeout_total}"
METRIC_RATE_LIMIT="${METRIC_RATE_LIMIT:-profile_bot_openai_calls_rate_limit_total}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "PROJECT_ID is required. Set PROJECT_ID or configure gcloud project." >&2
  exit 1
fi

COMMON_FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND resource.labels.location=\"${REGION}\""
OPENAI_BASE_FILTER="${COMMON_FILTER} AND (jsonPayload.event=\"openai_call\" OR textPayload:\"\\\"event\\\":\\\"openai_call\\\"\") AND (jsonPayload.upstream_provider=\"openai\" OR textPayload:\"\\\"upstream_provider\\\":\\\"openai\\\"\")"
FAILED_FILTER="${OPENAI_BASE_FILTER} AND (jsonPayload.success=false OR textPayload:\"\\\"success\\\":false\")"
TIMEOUT_FILTER="${OPENAI_BASE_FILTER} AND (jsonPayload.error_type=\"timeout\" OR textPayload:\"\\\"error_type\\\":\\\"timeout\\\"\")"
RATE_LIMIT_FILTER="${OPENAI_BASE_FILTER} AND (jsonPayload.error_type=\"rate_limit\" OR textPayload:\"\\\"error_type\\\":\\\"rate_limit\\\"\")"

upsert_counter_metric() {
  local name="$1"
  local description="$2"
  local filter="$3"

  if gcloud logging metrics describe "${name}" --project "${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud logging metrics update "${name}" \
      --project "${PROJECT_ID}" \
      --description "${description}" \
      --log-filter "${filter}" >/dev/null
  else
    gcloud logging metrics create "${name}" \
      --project "${PROJECT_ID}" \
      --description "${description}" \
      --log-filter "${filter}" >/dev/null
  fi
}

echo "Creating/updating OpenAI log-based metrics..."
upsert_counter_metric "${METRIC_TOTAL}" "Total OpenAI calls from ${SERVICE_NAME}." "${OPENAI_BASE_FILTER}"
upsert_counter_metric "${METRIC_FAILED}" "Failed OpenAI calls from ${SERVICE_NAME}." "${FAILED_FILTER}"
upsert_counter_metric "${METRIC_TIMEOUT}" "OpenAI timeout errors from ${SERVICE_NAME}." "${TIMEOUT_FILTER}"
upsert_counter_metric "${METRIC_RATE_LIMIT}" "OpenAI rate-limit errors from ${SERVICE_NAME}." "${RATE_LIMIT_FILTER}"

CHANNELS_JSON="$(
  python3 - "${NOTIFICATION_CHANNELS}" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
channels = [item.strip() for item in raw.split(",") if item.strip()]
print(json.dumps(channels))
PY
)"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT
dashboard_file="${tmp_dir}/openai_dashboard.json"
policy_timeout_file="${tmp_dir}/policy_timeout.json"
policy_rate_limit_file="${tmp_dir}/policy_rate_limit.json"

cat >"${dashboard_file}" <<EOF
{
  "displayName": "${DASHBOARD_DISPLAY_NAME}",
  "gridLayout": {
    "columns": "2",
    "widgets": [
      {
        "title": "OpenAI Calls Rate (req/s)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_TOTAL}\\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "req/s",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "OpenAI Failures Rate (req/s)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_FAILED}\\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "failures/s",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "OpenAI Failure Ratio",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilterRatio": {
                  "numerator": {
                    "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_FAILED}\\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  },
                  "denominator": {
                    "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_TOTAL}\\"",
                    "aggregation": {
                      "alignmentPeriod": "300s",
                      "perSeriesAligner": "ALIGN_RATE",
                      "crossSeriesReducer": "REDUCE_SUM"
                    }
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "ratio",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Timeouts (10m sum)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_TIMEOUT}\\"",
                  "aggregation": {
                    "alignmentPeriod": "600s",
                    "perSeriesAligner": "ALIGN_SUM",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "timeouts",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Rate Limits (10m sum)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_RATE_LIMIT}\\"",
                  "aggregation": {
                    "alignmentPeriod": "600s",
                    "perSeriesAligner": "ALIGN_SUM",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "rate-limit errors",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Runbook",
        "text": {
          "content": "### OpenAI Dependency Health\\nService: \`${SERVICE_NAME}\`\\nRegion: \`${REGION}\`\\n\\nInterpretation order:\\n1. Failure ratio trend\\n2. Rate-limit spikes\\n3. Timeout spikes\\n\\nThis dashboard uses log-based metrics emitted by backend structured logs.",
          "format": "MARKDOWN"
        }
      }
    ]
  }
}
EOF

cat >"${policy_timeout_file}" <<EOF
{
  "displayName": "[${ALERT_PREFIX}] OpenAI Timeout Spike",
  "enabled": true,
  "combiner": "OR",
  "documentation": {
    "mimeType": "text/markdown",
    "content": "OpenAI timeout errors are elevated for \`${SERVICE_NAME}\`."
  },
  "notificationChannels": ${CHANNELS_JSON},
  "alertStrategy": {
    "autoClose": "${ALERT_AUTO_CLOSE}"
  },
  "conditions": [
    {
      "displayName": "timeouts > 2 over 10 minutes",
      "conditionThreshold": {
        "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_TIMEOUT}\\" AND resource.type=\\"cloud_run_revision\\"",
        "aggregations": [
          {
            "alignmentPeriod": "600s",
            "perSeriesAligner": "ALIGN_DELTA"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 2,
        "duration": "0s",
        "trigger": {
          "count": 1
        }
      }
    }
  ]
}
EOF

cat >"${policy_rate_limit_file}" <<EOF
{
  "displayName": "[${ALERT_PREFIX}] OpenAI Rate-Limit Spike",
  "enabled": true,
  "combiner": "OR",
  "documentation": {
    "mimeType": "text/markdown",
    "content": "OpenAI rate-limit (429) errors are elevated for \`${SERVICE_NAME}\`."
  },
  "notificationChannels": ${CHANNELS_JSON},
  "alertStrategy": {
    "autoClose": "${ALERT_AUTO_CLOSE}"
  },
  "conditions": [
    {
      "displayName": "rate-limit errors > 2 over 10 minutes",
      "conditionThreshold": {
        "filter": "metric.type=\\"logging.googleapis.com/user/${METRIC_RATE_LIMIT}\\" AND resource.type=\\"cloud_run_revision\\"",
        "aggregations": [
          {
            "alignmentPeriod": "600s",
            "perSeriesAligner": "ALIGN_DELTA"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 2,
        "duration": "0s",
        "trigger": {
          "count": 1
        }
      }
    }
  ]
}
EOF

dashboard_ids="$(
  gcloud monitoring dashboards list \
    --project "${PROJECT_ID}" \
    --format=json \
    2>/dev/null \
    | python3 -c '
import json
import sys

target = sys.argv[1]
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
try:
    dashboards = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)

for item in dashboards:
    if item.get("displayName") == target:
        print(item.get("name", ""))
' "${DASHBOARD_DISPLAY_NAME}"
)"

if [[ -n "${dashboard_ids}" ]]; then
  while IFS= read -r dashboard_id; do
    if [[ -z "${dashboard_id}" ]]; then
      continue
    fi
    echo "Deleting existing dashboard: ${dashboard_id}"
    gcloud monitoring dashboards delete "${dashboard_id}" --project "${PROJECT_ID}" --quiet >/dev/null
  done <<<"${dashboard_ids}"
fi

echo "Creating OpenAI health dashboard: ${DASHBOARD_DISPLAY_NAME}"
gcloud monitoring dashboards create --project "${PROJECT_ID}" --config-from-file "${dashboard_file}" >/dev/null

ACCESS_TOKEN="$(gcloud auth print-access-token)"
MONITORING_V3_BASE="https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}"

delete_policy_by_name() {
  local policy_display_name="$1"
  local existing_names
  local payload

  payload="$(
    curl -fsS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      "${MONITORING_V3_BASE}/alertPolicies?pageSize=1000" \
      || echo "{}"
  )"

  existing_names="$(
    printf "%s" "${payload}" | python3 -c '
import json
import sys

target = sys.argv[1]
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)

for policy in data.get("alertPolicies", []):
    if policy.get("displayName") == target:
        print(policy.get("name", ""))
' "${policy_display_name}"
  )"

  if [[ -z "${existing_names}" ]]; then
    return
  fi

  while IFS= read -r name; do
    if [[ -z "${name}" ]]; then
      continue
    fi
    echo "Deleting existing alert policy: ${name}"
    curl -fsS -X DELETE \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      "https://monitoring.googleapis.com/v3/${name}" >/dev/null
  done <<<"${existing_names}"
}

create_policy() {
  local policy_file="$1"
  local policy_name="$2"
  local response_file
  local status

  response_file="${tmp_dir}/policy_create_response.json"

  delete_policy_by_name "${policy_name}"
  echo "Creating alert policy: ${policy_name}"
  status="$(
    curl -sS -o "${response_file}" -w "%{http_code}" -X POST \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    "${MONITORING_V3_BASE}/alertPolicies" \
    --data-binary "@${policy_file}"
  )"

  if [[ "${status}" -lt 200 || "${status}" -ge 300 ]]; then
    echo "Failed creating policy ${policy_name} (HTTP ${status})." >&2
    cat "${response_file}" >&2
    exit 1
  fi
}

timeout_policy_name="[${ALERT_PREFIX}] OpenAI Timeout Spike"
rate_limit_policy_name="[${ALERT_PREFIX}] OpenAI Rate-Limit Spike"

create_policy "${policy_timeout_file}" "${timeout_policy_name}"
create_policy "${policy_rate_limit_file}" "${rate_limit_policy_name}"

echo ""
echo "OpenAI observability bootstrap complete."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Dashboard: ${DASHBOARD_DISPLAY_NAME}"
echo "Log-based metrics:"
echo "  - ${METRIC_TOTAL}"
echo "  - ${METRIC_FAILED}"
echo "  - ${METRIC_TIMEOUT}"
echo "  - ${METRIC_RATE_LIMIT}"
echo "Alert policies:"
echo "  - ${timeout_policy_name}"
echo "  - ${rate_limit_policy_name}"
