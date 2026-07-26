#!/bin/sh
set -e

CONFIG_TEMPLATE="/etc/sing-box/config.template.json"
CONFIG_FILE="/etc/sing-box/config.json"

if [ -z "" ]; then
  echo "FATAL: UUID is not set"
  exit 1
fi

if [ ! -f "" ]; then
  echo "FATAL: Template  not found"
  exit 1
fi

sed -e "s|\||g" "" > ""

echo "Starting sing-box (VLESS+WS) on port 8081, proxied by Caddy on port 8080"

sing-box run -c "" 2>&1