FROM ghcr.io/sagernet/sing-box:latest

WORKDIR /etc/sing-box

COPY config.template.json /etc/sing-box/config.template.json
COPY start.sh /etc/sing-box/start.sh

RUN chmod +x /etc/sing-box/start.sh

CMD ["/etc/sing-box/start.sh"]
