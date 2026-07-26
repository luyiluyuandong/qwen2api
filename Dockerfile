FROM caddy:latest

COPY Caddyfile /etc/caddy/Caddyfile
COPY config.template.json /etc/sing-box/config.template.json
COPY start.sh /start.sh

ADD https://github.com/SagerNet/sing-box/releases/latest/download/sing-box-linux-amd64.tar.gz /tmp/
RUN tar xzf /tmp/sing-box-linux-amd64.tar.gz -C /usr/local/bin/ --strip-components=1 && \
    chmod +x /start.sh

EXPOSE 8080

CMD /start.sh & caddy run --config /etc/caddy/Caddyfile; wait