#!/usr/bin/env bash
set -e

PROJECT_ID="skillful-cider-440305-d7"
INSTANCE_NAME="instance-20250730-083312"
ZONE="us-west1-a"

INSTANCE_ID=$(gcloud compute instances describe "$INSTANCE_NAME" \
  --zone="$ZONE" --project="$PROJECT_ID" --format='value(id)')

START="2025-07-01T00:00:00Z"
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

RESPONSE=$(curl -sS \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "Content-Type: application/json" \
  "https://monitoring.googleapis.com/v3/projects/$PROJECT_ID/timeSeries" \
  -G \
  --data-urlencode "filter=metric.type=\"compute.googleapis.com/instance/network/sent_bytes_count\" resource.label.\"instance_id\"=\"$INSTANCE_ID\"" \
  --data-urlencode "interval.startTime=$START" \
  --data-urlencode "interval.endTime=$END" \
  --data-urlencode "aggregation.alignmentPeriod=60s" \
  --data-urlencode "aggregation.perSeriesAligner=ALIGN_RATE" \
  --data-urlencode "aggregation.crossSeriesReducer=REDUCE_SUM")

echo "Instance ID: $INSTANCE_ID"
echo "Raw JSON:"
echo "$RESPONSE"

TOTAL_BYTES=$(echo "$RESPONSE" | jq -r '
  .timeSeries[0].points
  | map(.value.doubleValue)
  | add // 0 | . * 60 | floor')

echo
echo "Total outbound bytes from 2025-07-01 to now: $TOTAL_BYTES"