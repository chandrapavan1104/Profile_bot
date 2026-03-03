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
BACKEND_URL="${BACKEND_URL:-}"
UPTIME_PATH="${UPTIME_PATH:-/health}"
UPTIME_DISPLAY_NAME="${UPTIME_DISPLAY_NAME:-[Profile Bot API] Health Uptime (${REGION})}"
ALERT_PREFIX="${ALERT_PREFIX:-Profile Bot API}"
ALERT_AUTO_CLOSE="${ALERT_AUTO_CLOSE:-1800s}"
NOTIFICATION_CHANNELS="${NOTIFICATION_CHANNELS:-}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "PROJECT_ID is required. Set PROJECT_ID or configure gcloud project." >&2
  exit 1
fi

if [[ -z "${BACKEND_URL}" ]]; then
  BACKEND_URL="$(
    gcloud run services describe "${SERVICE_NAME}" \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --format='value(status.url)'
  )"
fi

if [[ -z "${BACKEND_URL}" ]]; then
  echo "Could not determine backend URL. Set BACKEND_URL explicitly." >&2
  exit 1
fi

if [[ "${UPTIME_PATH}" != /* ]]; then
  UPTIME_PATH="/${UPTIME_PATH}"
fi

host="${BACKEND_URL#https://}"
host="${host#http://}"
host="${host%%/*}"

if [[ -z "${host}" ]]; then
  echo "Could not parse host from BACKEND_URL=${BACKEND_URL}" >&2
  exit 1
fi

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
policy_file="${tmp_dir}/uptime_alert_policy.json"

ACCESS_TOKEN="$(gcloud auth print-access-token)"
MONITORING_V3_BASE="https://monitoring.googleapis.com/v3/projects/${PROJECT_ID}"

find_uptime_names_by_display() {
  local display_name="$1"
  local payload

  payload="$(
    curl -fsS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      "${MONITORING_V3_BASE}/uptimeCheckConfigs?pageSize=1000" \
      || echo "{}"
  )"

  printf "%s" "${payload}" | python3 -c '
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

for item in payload.get("uptimeCheckConfigs", []):
    if item.get("displayName") == target:
        print(item.get("name", ""))
' "${display_name}"
}

existing_uptime_names="$(find_uptime_names_by_display "${UPTIME_DISPLAY_NAME}")"

if [[ -n "${existing_uptime_names}" ]]; then
  while IFS= read -r uptime_name; do
    if [[ -z "${uptime_name}" ]]; then
      continue
    fi
    echo "Deleting existing uptime check: ${uptime_name}"
    curl -sS -X DELETE \
      -H "Authorization: Bearer ${ACCESS_TOKEN}" \
      "https://monitoring.googleapis.com/v3/${uptime_name}" >/dev/null || true
  done <<<"${existing_uptime_names}"
fi

echo "Creating uptime check: ${UPTIME_DISPLAY_NAME}"
create_output="$(
  gcloud beta monitoring uptime create "${UPTIME_DISPLAY_NAME}" \
  --project "${PROJECT_ID}" \
  --resource-type=uptime-url \
  --resource-labels="project_id=${PROJECT_ID},host=${host}" \
  --protocol=https \
  --path="${UPTIME_PATH}" \
  --period=1 \
  --timeout=10 \
  --status-classes=2xx \
  2>&1
)"
printf "%s\n" "${create_output}"

created_uptime_name="$(
  printf "%s" "${create_output}" | python3 -c '
import sys

raw = sys.stdin.read()
for line in raw.splitlines():
    if "uptimeCheckConfigs/" not in line:
        continue
    start = line.find("projects/")
    if start < 0:
        continue
    end = line.find("]", start)
    if end < 0:
        end = len(line)
    value = line[start:end].strip().rstrip(".")
    if value:
        print(value)
        break
'
)"

if [[ -z "${created_uptime_name}" ]]; then
  for _ in 1 2 3 4 5; do
    created_uptime_name="$(find_uptime_names_by_display "${UPTIME_DISPLAY_NAME}" | tail -n 1)"
    if [[ -n "${created_uptime_name}" ]]; then
      break
    fi
    sleep 2
  done
fi

if [[ -z "${created_uptime_name}" ]]; then
  echo "Failed to resolve created uptime check by display name." >&2
  exit 1
fi

check_id="${created_uptime_name##*/}"

cat >"${policy_file}" <<EOF
{
  "displayName": "[${ALERT_PREFIX}] Uptime Check Failed",
  "enabled": true,
  "combiner": "OR",
  "documentation": {
    "mimeType": "text/markdown",
    "content": "Uptime check \`${UPTIME_DISPLAY_NAME}\` is failing for service \`${SERVICE_NAME}\`."
  },
  "notificationChannels": ${CHANNELS_JSON},
  "alertStrategy": {
    "autoClose": "${ALERT_AUTO_CLOSE}"
  },
  "conditions": [
    {
      "displayName": "Uptime checker reports failures",
      "conditionThreshold": {
        "filter": "metric.type=\\"monitoring.googleapis.com/uptime_check/check_passed\\" AND resource.type=\\"uptime_url\\" AND metric.labels.check_id=\\"${check_id}\\"",
        "aggregations": [
          {
            "alignmentPeriod": "300s",
            "perSeriesAligner": "ALIGN_NEXT_OLDER",
            "crossSeriesReducer": "REDUCE_COUNT_FALSE"
          }
        ],
        "comparison": "COMPARISON_GT",
        "thresholdValue": 1,
        "duration": "300s",
        "trigger": {
          "count": 1
        }
      }
    }
  ]
}
EOF

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

policy_name="[${ALERT_PREFIX}] Uptime Check Failed"
delete_policy_by_name "${policy_name}"

echo "Creating alert policy: ${policy_name}"
curl -fsS -X POST \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  "${MONITORING_V3_BASE}/alertPolicies" \
  --data-binary "@${policy_file}" >/dev/null

echo ""
echo "Uptime monitoring bootstrap complete."
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Backend URL: ${BACKEND_URL}"
echo "Uptime Check: ${created_uptime_name}"
echo "Alert Policy: ${policy_name}"
