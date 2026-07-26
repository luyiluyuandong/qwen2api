FROM caddy:builder AS builder
FROM caddy:latest

COPY Caddyfile /etc/caddy/Caddyfile

# 下载 sing-box
ADD https://github.com/SagerNet/sing-box/releases/latest/download/sing-box-linux-amd64.tar.gz /tmp/
RUN tar xzf /tmp/sing-box-linux-amd64.tar.gz -C /usr/local/bin/ --strip-components=1

COPY config.json /etc/sing-box/config.json

EXPOSE 8080

CMD caddy run --config /etc/caddy/Caddyfile & sing-box run -c /etc/sing-box/config.json
