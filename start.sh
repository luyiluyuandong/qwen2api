#!/bin/sh
set -e

CONFIG_TEMPLATE="/etc/sing-box/config.template.json"
CONFIG_FILE="/etc/sing-box/config.json"

for var in PORT UUID; do
  eval "value=\$$var"
  if [ -z "$value" ]; then
    echo "FATAL: $var is not set"
    exit 1
  fi
done

if [ ! -f "$CONFIG_TEMPLATE" ]; then
  echo "FATAL: Template $CONFIG_TEMPLATE not found"
  exit 1
fi

sed \
  -e "s|\${PORT}|$PORT|g" \
  -e "s|\${UUID}|$UUID|g" \
  "$CONFIG_TEMPLATE" > "$CONFIG_FILE"

echo "Starting sing-box (VLESS+WS) on port $PORT"

trap 'kill $PID; wait $PID; exit 0' TERM INT

sing-box run -c "$CONFIG_FILE" &
PID=$!
wait $PID
