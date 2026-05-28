#!/bin/sh
set -e

TEMPORAL_HOST="${TEMPORAL_ADDRESS:-temporal:7233}"
TEMPORAL_HOST_ONLY="${TEMPORAL_HOST%%:*}"
TEMPORAL_PORT="${TEMPORAL_HOST##*:}"
if [ "$TEMPORAL_PORT" = "$TEMPORAL_HOST" ]; then
  TEMPORAL_PORT=7233
fi

echo "Waiting for Temporal at ${TEMPORAL_HOST_ONLY}:${TEMPORAL_PORT}..."
TRIES=0
MAX_TRIES=60
while ! nc -z "$TEMPORAL_HOST_ONLY" "$TEMPORAL_PORT" 2>/dev/null; do
  TRIES=$((TRIES + 1))
  if [ "$TRIES" -ge "$MAX_TRIES" ]; then
    echo "Temporal did not become ready in time."
    exit 1
  fi
  sleep 2
done
echo "Temporal is ready. Starting CFO Agent..."

mkdir -p /data
exec "$@"
