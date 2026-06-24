#!/bin/sh
set -e

if [ -z "$PORT" ]; then
  echo "PORT is not set"
  exit 1
fi

if [ -z "$PROXY_USER" ]; then
  echo "PROXY_USER is not set"
  exit 1
fi

if [ -z "$PROXY_PASS" ]; then
  echo "PROXY_PASS is not set"
  exit 1
fi

sed \
  -e "s/\${PORT}/$PORT/g" \
  -e "s/\${PROXY_USER}/$PROXY_USER/g" \
  -e "s/\${PROXY_PASS}/$PROXY_PASS/g" \
  /etc/sing-box/config.template.json > /etc/sing-box/config.json

echo "Starting sing-box on port $PORT"

sing-box run -c /etc/sing-box/config.json
