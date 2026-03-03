# Cloud Run Monitoring Bootstrap

This folder contains monitoring automation for the backend service on Cloud Run.

Scripts:
- `setup_cloudrun_monitoring.sh`:
  - Base Cloud Run dashboard (request rate, p95 latency, 4xx/5xx, instance count).
  - Base alerts: 5xx spike, p95 latency high, instance spike.
- `setup_uptime_monitoring.sh`:
  - Uptime check for `/health`.
  - Uptime failure alert policy.
- `setup_openai_observability.sh`:
  - Log-based metrics from backend structured logs (`openai_call` events).
  - OpenAI health dashboard + timeout/rate-limit alert policies.

Defaults:
- Region: `us-central1`
- Service: `profile-bot-api-usc`

## 1. Optional: Create Notification Channel

```bash
gcloud beta monitoring channels create \
  --display-name="Profile Bot Ops Email" \
  --type=email \
  --channel-labels=email_address=YOUR_EMAIL@example.com
```

```bash
gcloud beta monitoring channels list --format='value(name,displayName)'
```

Example channel:
`projects/profilebot-474605/notificationChannels/1234567890123456789`

## 2. Deploy Backend First

`setup_openai_observability.sh` depends on structured logs emitted by backend code.
Deploy backend before running it:

```bash
gcloud run deploy profile-bot-api-usc ...
```

## 3. Run All Monitoring Bootstraps

From repo root:

```bash
chmod +x ops/monitoring/*.sh

PROJECT_ID=profilebot-474605 \
REGION=us-central1 \
SERVICE_NAME=profile-bot-api-usc \
NOTIFICATION_CHANNELS=projects/profilebot-474605/notificationChannels/1234567890123456789 \
./ops/monitoring/setup_cloudrun_monitoring.sh

PROJECT_ID=profilebot-474605 \
REGION=us-central1 \
SERVICE_NAME=profile-bot-api-usc \
NOTIFICATION_CHANNELS=projects/profilebot-474605/notificationChannels/1234567890123456789 \
./ops/monitoring/setup_uptime_monitoring.sh

PROJECT_ID=profilebot-474605 \
REGION=us-central1 \
SERVICE_NAME=profile-bot-api-usc \
NOTIFICATION_CHANNELS=projects/profilebot-474605/notificationChannels/1234567890123456789 \
./ops/monitoring/setup_openai_observability.sh
```

If you do not want notifications yet, omit `NOTIFICATION_CHANNELS`.
