#!/bin/sh
set -e

CONFIG_TEMPLATE="/etc/sing-box/config.template.json"
CONFIG_FILE="/etc/sing-box/config.json"

if [ -z "$UUID" ]; then
  echo "FATAL: UUID is not set"
  exit 1
fi

if [ ! -f "$CONFIG_TEMPLATE" ]; then
  echo "FATAL: Template $CONFIG_TEMPLATE not found"
  exit 1
fi

sed -e "s|\${UUID}|$UUID|g" "$CONFIG_TEMPLATE" > "$CONFIG_FILE"

echo "Starting sing-box (VLESS+WS) on port 8081, proxied by Caddy on port 8080"

sing-box run -c "$CONFIG_FILE" 2>&1