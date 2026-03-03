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
DASHBOARD_DISPLAY_NAME="${DASHBOARD_DISPLAY_NAME:-Profile Bot API - Cloud Run (${REGION})}"
ALERT_PREFIX="${ALERT_PREFIX:-Profile Bot API}"
NOTIFICATION_CHANNELS="${NOTIFICATION_CHANNELS:-}"
ALERT_AUTO_CLOSE="${ALERT_AUTO_CLOSE:-1800s}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "PROJECT_ID is required. Set PROJECT_ID or configure gcloud project." >&2
  exit 1
fi

BASE_FILTER="resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"${SERVICE_NAME}\" AND resource.labels.location=\"${REGION}\""
BASE_FILTER_JSON="${BASE_FILTER//\"/\\\"}"

CHANNELS_JSON="$(
  python3 - "${NOTIFICATION_CHANNELS}" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
channels = [item.strip() for item in raw.split(",") if item.strip()]
print(json.dumps(channels))
PY
)"

ACCESS_TOKEN="$(gcloud auth print-access-token)"
MONITORING_V3_BASE="https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}"

latency_descriptor_payload="$(
  curl -fsS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "${MONITORING_V3_BASE}/metricDescriptors/run.googleapis.com%2Frequest_latencies" \
    2>/dev/null \
    || true
)"

LATENCY_UNIT="$(
  printf "%s" "${latency_descriptor_payload}" | python3 -c '
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    print("")
    raise SystemExit(0)

try:
    data = json.loads(raw)
except json.JSONDecodeError:
    print("")
    raise SystemExit(0)

print(data.get("unit", ""))
'
)"

LATENCY_THRESHOLD="8000"
LATENCY_UNIT_LABEL="ms"
if [[ "${LATENCY_UNIT}" == "s" ]]; then
  LATENCY_THRESHOLD="8"
  LATENCY_UNIT_LABEL="s"
elif [[ -n "${LATENCY_UNIT}" ]]; then
  LATENCY_UNIT_LABEL="${LATENCY_UNIT}"
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "${tmp_dir}"' EXIT

dashboard_file="${tmp_dir}/dashboard.json"
policy_5xx_file="${tmp_dir}/policy_5xx.json"
policy_latency_file="${tmp_dir}/policy_latency.json"
policy_instance_file="${tmp_dir}/policy_instance.json"

cat >"${dashboard_file}" <<EOF
{
  "displayName": "${DASHBOARD_DISPLAY_NAME}",
  "gridLayout": {
    "columns": "2",
    "widgets": [
      {
        "title": "Request Rate (req/s)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"run.googleapis.com/request_count\\" AND ${BASE_FILTER_JSON}",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_RATE"
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
        "title": "p95 Request Latency (${LATENCY_UNIT_LABEL})",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"run.googleapis.com/request_latencies\\" AND ${BASE_FILTER_JSON}",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_PERCENTILE_95"
                  }
                }
              },
              "plotType": "LINE",
              "minAlignmentPeriod": "60s"
            }
          ],
          "yAxis": {
            "label": "${LATENCY_UNIT_LABEL}",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "4xx Responses (5m sum)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"run.googleapis.com/request_count\\" AND metric.labels.response_code_class=\\"4xx\\" AND ${BASE_FILTER_JSON}",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_SUM",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "requests",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "5xx Responses (5m sum)",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"run.googleapis.com/request_count\\" AND metric.labels.response_code_class=\\"5xx\\" AND ${BASE_FILTER_JSON}",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_SUM",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "requests",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Active Instance Count",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\\"run.googleapis.com/container/instance_count\\" AND ${BASE_FILTER_JSON}",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_MAX",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "instances",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Runbook",
        "text": {
          "content": "### Profile Bot Monitoring\\n- Region: \`${REGION}\`\\n- Service: \`${SERVICE_NAME}\`\\n- Traffic profile: ~100 visitors/day\\n\\nInvestigate in this order:\\n1. 5xx spikes\\n2. Latency regression\\n3. Instance spikes\\n\\nIf alerts are noisy, tune thresholds in \`ops/monitoring/setup_cloudrun_monitoring.sh\`.",
          "format": "MARKDOWN"
        }
      }
    ]
  }
}
EOF

cat >"${policy_5xx_file}" <<EOF
{
  "displayName": "[${ALERT_PREFIX}] 5xx Spike",
  "enabled": true,
  "combiner": "OR",
  "documentation": {
    "mimeType": "text/markdown",
    "content": "Cloud Run service \`${SERVICE_NAME}\` in \`${REGION}\` is returning elevated 5xx responses."
  },
  "notificationChannels": ${CHANNELS_JSON},
  "alertStrategy": {
    "autoClose": "${ALERT_AUTO_CLOSE}"
  },
  "conditions": [
    {
      "displayName": "5xx count > 3 over 10 minutes",
      "conditionThreshold": {
        "filter": "metric.type=\\"run.googleapis.com/request_count\\" AND metric.labels.response_code_class=\\"5xx\\" AND ${BASE_FILTER_JSON}",
        "aggregations": [
          {
            "alignmentPeriod": "600s",
            "perSeriesAligner": "ALIGN_SUM",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 3,
        "duration": "0s",
        "trigger": {
          "count": 1
        }
      }
    }
  ]
}
EOF

cat >"${policy_latency_file}" <<EOF
{
  "displayName": "[${ALERT_PREFIX}] p95 Latency High",
  "enabled": true,
  "combiner": "OR",
  "documentation": {
    "mimeType": "text/markdown",
    "content": "Cloud Run p95 latency is elevated for \`${SERVICE_NAME}\` in \`${REGION}\`."
  },
  "notificationChannels": ${CHANNELS_JSON},
  "alertStrategy": {
    "autoClose": "${ALERT_AUTO_CLOSE}"
  },
  "conditions": [
    {
      "displayName": "p95 request latency > ${LATENCY_THRESHOLD} ${LATENCY_UNIT_LABEL} for 5 minutes",
      "conditionThreshold": {
        "filter": "metric.type=\\"run.googleapis.com/request_latencies\\" AND ${BASE_FILTER_JSON}",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_PERCENTILE_95",
            "crossSeriesReducer": "REDUCE_MAX"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": ${LATENCY_THRESHOLD},
        "duration": "300s",
        "trigger": {
          "count": 1
        }
      }
    }
  ]
}
EOF

cat >"${policy_instance_file}" <<EOF
{
  "displayName": "[${ALERT_PREFIX}] Instance Spike",
  "enabled": true,
  "combiner": "OR",
  "documentation": {
    "mimeType": "text/markdown",
    "content": "Cloud Run active instance count is unusually high for \`${SERVICE_NAME}\` in \`${REGION}\`."
  },
  "notificationChannels": ${CHANNELS_JSON},
  "alertStrategy": {
    "autoClose": "${ALERT_AUTO_CLOSE}"
  },
  "conditions": [
    {
      "displayName": "active instances > 5 for 10 minutes",
      "conditionThreshold": {
        "filter": "metric.type=\\"run.googleapis.com/container/instance_count\\" AND ${BASE_FILTER_JSON}",
        "aggregations": [
          {
            "alignmentPeriod": "600s",
            "perSeriesAligner": "ALIGN_MAX",
            "crossSeriesReducer": "REDUCE_SUM"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 5,
        "duration": "600s",
        "trigger": {
          "count": 1
        }
      }
    }
  ]
}
EOF

dashboard_list_json="$(
  gcloud monitoring dashboards list \
    --project "${PROJECT_ID}" \
    --format=json \
    2>/dev/null \
    || echo "[]"
)"

dashboard_ids="$(
  printf "%s" "${dashboard_list_json}" | python3 -c '
import json
import sys

target = sys.argv[1]
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
try:
    items = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)

for item in items:
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
    gcloud monitoring dashboards delete "${dashboard_id}" --project "${PROJECT_ID}" --quiet
  done <<<"${dashboard_ids}"
fi

echo "Creating dashboard: ${DASHBOARD_DISPLAY_NAME}"
gcloud monitoring dashboards create --project "${PROJECT_ID}" --config-from-file "${dashboard_file}" >/dev/null

delete_policy_by_name() {
  local policy_display_name="$1"
  local existing_names
  local policy_list_json
  policy_list_json="$(
    curl -fsS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      "${MONITORING_V3_BASE}/alertPolicies?pageSize=1000" \
      || echo "{}"
  )"

  existing_names="$(
    printf "%s" "${policy_list_json}" | python3 -c '
import json
import sys

target = sys.argv[1]
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(0)
for policy in payload.get("alertPolicies", []):
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
  delete_policy_by_name "${policy_name}"
  echo "Creating alert policy: ${policy_name}"
  curl -fsS -X POST \
    -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    -H "Content-Type: application/json" \
    "${MONITORING_V3_BASE}/alertPolicies" \
    --data-binary "@${policy_file}" >/dev/null
}

policy_5xx_name="[${ALERT_PREFIX}] 5xx Spike"
policy_latency_name="[${ALERT_PREFIX}] p95 Latency High"
policy_instance_name="[${ALERT_PREFIX}] Instance Spike"

create_policy "${policy_5xx_file}" "${policy_5xx_name}"
create_policy "${policy_latency_file}" "${policy_latency_name}"
create_policy "${policy_instance_file}" "${policy_instance_name}"

echo ""
echo "Monitoring bootstrap complete."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Dashboard: ${DASHBOARD_DISPLAY_NAME}"
echo "Alerts:"
echo "  - ${policy_5xx_name}"
echo "  - ${policy_latency_name}"
echo "  - ${policy_instance_name}"
