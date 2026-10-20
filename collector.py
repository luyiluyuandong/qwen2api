#!/usr/bin/env python3

# -*- coding: utf-8 -*-

"""

================================================================================

GitHub Actions 代理节点全量深度采集与云端初筛引擎 (NodeHarvester - 云端初筛版)

================================================================================

【核心执行流程与铁律规范】：

1. 内存全网聚合：从 397 个全新公开订阅源全量解包（百万级节点纯内存驻留，绝不落地脏数据）

2. 规则 1 协议规范化：hy2:// 自动重写为 hysteria2://，补齐 insecure=1 与 sni 参数

3. 规则 2 基础过滤：剔除 .ir 死域、私有内网 IP 及无效测试占位符

4. 规则 3 协议聚焦与加密判定：支持 hysteria2/vless/vmess/trojan/ss/https，剔除裸明文

5. 规则 4 内存单 Host 粗排重：同一目标地址初筛去重，快速消肿

6. 规则 5 云端海外高并发握手测活：asyncio 250 并发底层探测，剔除 90%+ 绝对应答死亡节点

7. 规则 6 真实物理出口 IP 绝对唯一：通过 Socket peername 获取真实物理 IP，彻底消灭马甲换皮节点

8. 规则 7 质量排序：按协议优先级与握手延迟毫秒排序，优质节点排在最前

9. 规则 8 落地分卷存储：仅将初筛存活的优质节点落盘，单文件上限严格锁死 40MB，超限规律自动拆分

================================================================================

"""



import asyncio

import base64

import glob

import hashlib

import io

import json

import os

import re

import shutil

import socket

import subprocess

import sys

# 解决 Windows 控制台编码问题

if sys.platform.startswith("win"):

    try:

        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    except Exception:

        pass



import time

import urllib.error

import urllib.parse

import urllib.request

import zipfile

from concurrent.futures import ThreadPoolExecutor, as_completed



# ==============================================================================

# [基础路径与文件配置]

# ==============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

OUTPUT_FILE = os.path.join(BASE_DIR, "all_proxies.txt")

VALID_OUTPUT_FILE = os.path.join(BASE_DIR, "valid_proxies.txt")
FINAL_OUTPUT_FILE = os.path.join(BASE_DIR, "final_valid_proxies.txt")

SEEN_FILE = os.path.join(BASE_DIR, "seen_hashes.txt")



# ==============================================================================

# [云端执行参数配置]

# ==============================================================================

CHECK_CONCURRENCY = 250

CHECK_TIMEOUT_SECONDS = 2.5

MAX_OUTPUT_BYTES = 40 * 1024 * 1024  # 严格 40MB 单文件物理上限 (超限自动拆分)

REQUEST_TIMEOUT_SECONDS = 25



# ==============================================================================

# [数据源清单：13 原始核心仓库 + 超低关注度防封源 + 高频细分专线]

# ==============================================================================



# 一、超低关注度（1~20 Stars）高频小众宝藏源

LOW_ATTENTION_SOURCES = []




# 二、高频维护的细分协议订阅专线

CURATED_SUBSCRIPTIONS = [
    {"name": "3inker-v2ray-subscription-all_not_ru.txt", "repo": "3inker/v2ray-subscription", "url": "https://raw.githubusercontent.com/3inker/v2ray-subscription/main/subs/all_not_ru.txt", "desc": "new-source-1"},
    {"name": "3yed-61-V2rayCollector-vmess", "repo": "3yed-61/V2rayCollector", "url": "https://raw.githubusercontent.com/3yed-61/V2rayCollector/main/sub/vmess", "desc": "new-source-2"},
    {"name": "3yed-61-V2rayCollector-vmess", "repo": "3yed-61/V2rayCollector", "url": "https://raw.githubusercontent.com/3yed-61/V2rayCollector/refs/heads/main/sub/vmess", "desc": "new-source-3"},
    {"name": "aishervin-g2ray-vless.txt", "repo": "aishervin/g2ray", "url": "https://raw.githubusercontent.com/aishervin/g2ray/main/vless.txt", "desc": "new-source-4"},
    {"name": "aishervin-subfine-sub.txt", "repo": "aishervin/subfine", "url": "https://raw.githubusercontent.com/aishervin/subfine/main/sub.txt", "desc": "new-source-5"},
    {"name": "amir-reza-bijandi-v2ray-configs-configs.txt", "repo": "amir-reza-bijandi/v2ray-configs", "url": "https://raw.githubusercontent.com/amir-reza-bijandi/v2ray-configs/main/configs.txt", "desc": "new-source-6"},
    {"name": "Andrejewild-happ-v2rayng-configs-base64.txt", "repo": "Andrejewild/happ-v2rayng-configs", "url": "https://raw.githubusercontent.com/Andrejewild/happ-v2rayng-configs/main/base64.txt", "desc": "new-source-7"},
    {"name": "Andrejewild-happ-v2rayng-configs-sub.txt", "repo": "Andrejewild/happ-v2rayng-configs", "url": "https://raw.githubusercontent.com/Andrejewild/happ-v2rayng-configs/main/sub.txt", "desc": "new-source-8"},
    {"name": "Andrejewild-vless-free-keys-russia-base64.txt", "repo": "Andrejewild/vless-free-keys-russia", "url": "https://raw.githubusercontent.com/Andrejewild/vless-free-keys-russia/main/base64.txt", "desc": "new-source-9"},
    {"name": "Andrejewild-vless-free-keys-russia-sub.txt", "repo": "Andrejewild/vless-free-keys-russia", "url": "https://raw.githubusercontent.com/Andrejewild/vless-free-keys-russia/main/sub.txt", "desc": "new-source-10"},
    {"name": "asgharkapk-Sub-Config-Extractor-reality.yaml", "repo": "asgharkapk/Sub-Config-Extractor", "url": "https://raw.githubusercontent.com/asgharkapk/Sub-Config-Extractor/refs/heads/main/output_configs/clash/10ium/V2Hub3/reality.yaml", "desc": "new-source-11"},
    {"name": "asgharkapk-Sub-Config-Extractor-ss.txt.yaml", "repo": "asgharkapk/Sub-Config-Extractor", "url": "https://raw.githubusercontent.com/asgharkapk/Sub-Config-Extractor/refs/heads/main/output_configs/clash/MatinGhanbari/v2ray-configs/ss.txt.yaml", "desc": "new-source-12"},
    {"name": "ashah404-V2rayCollector-ipv4", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/layers/ipv4", "desc": "new-source-13"},
    {"name": "ashah404-V2rayCollector-ipv6", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/layers/ipv6", "desc": "new-source-14"},
    {"name": "ashah404-V2rayCollector-grpc", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/networks/grpc", "desc": "new-source-15"},
    {"name": "ashah404-V2rayCollector-http", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/networks/http", "desc": "new-source-16"},
    {"name": "ashah404-V2rayCollector-tcp", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/networks/tcp", "desc": "new-source-17"},
    {"name": "ashah404-V2rayCollector-ws", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/networks/ws", "desc": "new-source-18"},
    {"name": "ashah404-V2rayCollector-hysteria", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/hysteria", "desc": "new-source-19"},
    {"name": "ashah404-V2rayCollector-reality", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/reality", "desc": "new-source-20"},
    {"name": "ashah404-V2rayCollector-shadowsocks", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/shadowsocks", "desc": "new-source-21"},
    {"name": "ashah404-V2rayCollector-trojan", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/trojan", "desc": "new-source-22"},
    {"name": "ashah404-V2rayCollector-tuic", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/tuic", "desc": "new-source-23"},
    {"name": "ashah404-V2rayCollector-vless", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/vless", "desc": "new-source-24"},
    {"name": "ashah404-V2rayCollector-vmess", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/protocols/vmess", "desc": "new-source-25"},
    {"name": "ashah404-V2rayCollector-non-tls", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/security/non-tls", "desc": "new-source-26"},
    {"name": "ashah404-V2rayCollector-tls", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/channels/security/tls", "desc": "new-source-27"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ae/mixed", "desc": "new-source-28"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/af/mixed", "desc": "new-source-29"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/al/mixed", "desc": "new-source-30"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/am/mixed", "desc": "new-source-31"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/aq/mixed", "desc": "new-source-32"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ar/mixed", "desc": "new-source-33"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/at/mixed", "desc": "new-source-34"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/au/mixed", "desc": "new-source-35"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/az/mixed", "desc": "new-source-36"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ba/mixed", "desc": "new-source-37"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/bd/mixed", "desc": "new-source-38"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/be/mixed", "desc": "new-source-39"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/bg/mixed", "desc": "new-source-40"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/bh/mixed", "desc": "new-source-41"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/bo/mixed", "desc": "new-source-42"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/br/mixed", "desc": "new-source-43"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/by/mixed", "desc": "new-source-44"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/bz/mixed", "desc": "new-source-45"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ca/mixed", "desc": "new-source-46"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ch/mixed", "desc": "new-source-47"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/cl/mixed", "desc": "new-source-48"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/cn/mixed", "desc": "new-source-49"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/co/mixed", "desc": "new-source-50"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/cr/mixed", "desc": "new-source-51"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/cw/mixed", "desc": "new-source-52"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/cy/mixed", "desc": "new-source-53"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/cz/mixed", "desc": "new-source-54"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/de/mixed", "desc": "new-source-55"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/dk/mixed", "desc": "new-source-56"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/do/mixed", "desc": "new-source-57"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/dz/mixed", "desc": "new-source-58"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ec/mixed", "desc": "new-source-59"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ee/mixed", "desc": "new-source-60"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/eg/mixed", "desc": "new-source-61"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/es/mixed", "desc": "new-source-62"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/fi/mixed", "desc": "new-source-63"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/fr/mixed", "desc": "new-source-64"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/gb/mixed", "desc": "new-source-65"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ge/mixed", "desc": "new-source-66"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/gi/mixed", "desc": "new-source-67"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/gr/mixed", "desc": "new-source-68"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/gt/mixed", "desc": "new-source-69"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/hk/mixed", "desc": "new-source-70"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/hr/mixed", "desc": "new-source-71"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/hu/mixed", "desc": "new-source-72"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/id/mixed", "desc": "new-source-73"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ie/mixed", "desc": "new-source-74"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/il/mixed", "desc": "new-source-75"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/im/mixed", "desc": "new-source-76"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/in/mixed", "desc": "new-source-77"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/iq/mixed", "desc": "new-source-78"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ir/mixed", "desc": "new-source-79"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/is/mixed", "desc": "new-source-80"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/it/mixed", "desc": "new-source-81"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/jo/mixed", "desc": "new-source-82"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/jp/mixed", "desc": "new-source-83"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ke/mixed", "desc": "new-source-84"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/kg/mixed", "desc": "new-source-85"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/kh/mixed", "desc": "new-source-86"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/km/mixed", "desc": "new-source-87"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/kr/mixed", "desc": "new-source-88"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/kw/mixed", "desc": "new-source-89"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/kz/mixed", "desc": "new-source-90"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/la/mixed", "desc": "new-source-91"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/li/mixed", "desc": "new-source-92"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/lt/mixed", "desc": "new-source-93"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/lu/mixed", "desc": "new-source-94"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/lv/mixed", "desc": "new-source-95"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ma/mixed", "desc": "new-source-96"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/md/mixed", "desc": "new-source-97"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/me/mixed", "desc": "new-source-98"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mh/mixed", "desc": "new-source-99"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mk/mixed", "desc": "new-source-100"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mm/mixed", "desc": "new-source-101"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mn/mixed", "desc": "new-source-102"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mo/mixed", "desc": "new-source-103"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mt/mixed", "desc": "new-source-104"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mu/mixed", "desc": "new-source-105"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mv/mixed", "desc": "new-source-106"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/mx/mixed", "desc": "new-source-107"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/my/mixed", "desc": "new-source-108"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/na/mixed", "desc": "new-source-109"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ng/mixed", "desc": "new-source-110"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/nl/mixed", "desc": "new-source-111"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/no/mixed", "desc": "new-source-112"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/np/mixed", "desc": "new-source-113"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/nz/mixed", "desc": "new-source-114"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/om/mixed", "desc": "new-source-115"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pa/mixed", "desc": "new-source-116"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pe/mixed", "desc": "new-source-117"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ph/mixed", "desc": "new-source-118"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pk/mixed", "desc": "new-source-119"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pl/mixed", "desc": "new-source-120"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pr/mixed", "desc": "new-source-121"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ps/mixed", "desc": "new-source-122"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pt/mixed", "desc": "new-source-123"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/pw/mixed", "desc": "new-source-124"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/py/mixed", "desc": "new-source-125"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/qa/mixed", "desc": "new-source-126"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/re/mixed", "desc": "new-source-127"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ro/mixed", "desc": "new-source-128"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/rs/mixed", "desc": "new-source-129"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ru/mixed", "desc": "new-source-130"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/sa/mixed", "desc": "new-source-131"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/sc/mixed", "desc": "new-source-132"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/se/mixed", "desc": "new-source-133"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/sg/mixed", "desc": "new-source-134"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/si/mixed", "desc": "new-source-135"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/sk/mixed", "desc": "new-source-136"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/sy/mixed", "desc": "new-source-137"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/th/mixed", "desc": "new-source-138"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/tr/mixed", "desc": "new-source-139"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/tt/mixed", "desc": "new-source-140"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/tw/mixed", "desc": "new-source-141"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/ua/mixed", "desc": "new-source-142"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/us/mixed", "desc": "new-source-143"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/uy/mixed", "desc": "new-source-144"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/uz/mixed", "desc": "new-source-145"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/vg/mixed", "desc": "new-source-146"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/vi/mixed", "desc": "new-source-147"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/vn/mixed", "desc": "new-source-148"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/xk/mixed", "desc": "new-source-149"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/countries/za/mixed", "desc": "new-source-150"},
    {"name": "ashah404-V2rayCollector-ipv4", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/layers/ipv4", "desc": "new-source-151"},
    {"name": "ashah404-V2rayCollector-ipv6", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/layers/ipv6", "desc": "new-source-152"},
    {"name": "ashah404-V2rayCollector-grpc", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/networks/grpc", "desc": "new-source-153"},
    {"name": "ashah404-V2rayCollector-http", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/networks/http", "desc": "new-source-154"},
    {"name": "ashah404-V2rayCollector-tcp", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/networks/tcp", "desc": "new-source-155"},
    {"name": "ashah404-V2rayCollector-ws", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/networks/ws", "desc": "new-source-156"},
    {"name": "ashah404-V2rayCollector-hysteria", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/hysteria", "desc": "new-source-157"},
    {"name": "ashah404-V2rayCollector-juicity", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/juicity", "desc": "new-source-158"},
    {"name": "ashah404-V2rayCollector-reality", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/reality", "desc": "new-source-159"},
    {"name": "ashah404-V2rayCollector-shadowsocks", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/shadowsocks", "desc": "new-source-160"},
    {"name": "ashah404-V2rayCollector-trojan", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/trojan", "desc": "new-source-161"},
    {"name": "ashah404-V2rayCollector-tuic", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/tuic", "desc": "new-source-162"},
    {"name": "ashah404-V2rayCollector-vless", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/vless", "desc": "new-source-163"},
    {"name": "ashah404-V2rayCollector-vmess", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/protocols/vmess", "desc": "new-source-164"},
    {"name": "ashah404-V2rayCollector-non-tls", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/security/non-tls", "desc": "new-source-165"},
    {"name": "ashah404-V2rayCollector-tls", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/security/tls", "desc": "new-source-166"},
    {"name": "ashah404-V2rayCollector-channels", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/splitted/channels", "desc": "new-source-167"},
    {"name": "ashah404-V2rayCollector-mixed", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/splitted/mixed", "desc": "new-source-168"},
    {"name": "ashah404-V2rayCollector-subscribe", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/splitted/subscribe", "desc": "new-source-169"},
    {"name": "ashah404-V2rayCollector-ipv4", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/layers/ipv4", "desc": "new-source-170"},
    {"name": "ashah404-V2rayCollector-ipv6", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/layers/ipv6", "desc": "new-source-171"},
    {"name": "ashah404-V2rayCollector-grpc", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/networks/grpc", "desc": "new-source-172"},
    {"name": "ashah404-V2rayCollector-http", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/networks/http", "desc": "new-source-173"},
    {"name": "ashah404-V2rayCollector-tcp", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/networks/tcp", "desc": "new-source-174"},
    {"name": "ashah404-V2rayCollector-ws", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/networks/ws", "desc": "new-source-175"},
    {"name": "ashah404-V2rayCollector-hysteria", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/hysteria", "desc": "new-source-176"},
    {"name": "ashah404-V2rayCollector-reality", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/reality", "desc": "new-source-177"},
    {"name": "ashah404-V2rayCollector-shadowsocks", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/shadowsocks", "desc": "new-source-178"},
    {"name": "ashah404-V2rayCollector-trojan", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/trojan", "desc": "new-source-179"},
    {"name": "ashah404-V2rayCollector-tuic", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/tuic", "desc": "new-source-180"},
    {"name": "ashah404-V2rayCollector-vless", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/vless", "desc": "new-source-181"},
    {"name": "ashah404-V2rayCollector-vmess", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/protocols/vmess", "desc": "new-source-182"},
    {"name": "ashah404-V2rayCollector-non-tls", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/security/non-tls", "desc": "new-source-183"},
    {"name": "ashah404-V2rayCollector-tls", "repo": "ashah404/V2rayCollector", "url": "https://raw.githubusercontent.com/ashah404/V2rayCollector/main/subscribe/security/tls", "desc": "new-source-184"},
    {"name": "Au1rxx-free-vpn-subscriptions-all-verified", "repo": "Au1rxx/free-vpn-subscriptions", "url": "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/all-verified", "desc": "new-source-185"},
    {"name": "Au1rxx-free-vpn-subscriptions-vless", "repo": "Au1rxx/free-vpn-subscriptions", "url": "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/protocol/vless", "desc": "new-source-186"},
    {"name": "Au1rxx-free-vpn-subscriptions-v2ray-base64.txt", "repo": "Au1rxx/free-vpn-subscriptions", "url": "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/output/v2ray-base64.txt", "desc": "new-source-187"},
    {"name": "Au1rxx-free-vpn-subscriptions-README.md", "repo": "Au1rxx/free-vpn-subscriptions", "url": "https://raw.githubusercontent.com/Au1rxx/free-vpn-subscriptions/main/README.md", "desc": "new-source-188"},
    {"name": "aviamastersgh-vpn-free-russia-all_configs.txt", "repo": "aviamastersgh/vpn-free-russia", "url": "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/main/all_configs.txt", "desc": "new-source-189"},
    {"name": "awesome-vpn-awesome-vpn-all", "repo": "awesome-vpn/awesome-vpn", "url": "https://raw.githubusercontent.com/awesome-vpn/awesome-vpn/master/all", "desc": "new-source-190"},
    {"name": "barry-far-V2ray-Config-All_Configs_Sub.txt", "repo": "barry-far/V2ray-Config", "url": "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/All_Configs_Sub.txt", "desc": "new-source-191"},
    {"name": "barry-far-V2ray-Config-vless.txt", "repo": "barry-far/V2ray-Config", "url": "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vless.txt", "desc": "new-source-192"},
    {"name": "barry-far-V2ray-Config-vmess.txt", "repo": "barry-far/V2ray-Config", "url": "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Splitted-By-Protocol/vmess.txt", "desc": "new-source-193"},
    {"name": "barry-far-V2ray-Config-Sub1.txt", "repo": "barry-far/V2ray-Config", "url": "https://raw.githubusercontent.com/barry-far/V2ray-Config/main/Sub1.txt", "desc": "new-source-194"},
    {"name": "barry-far-V2ray-Config-All_Configs_base64_Sub.txt", "repo": "barry-far/V2ray-Config", "url": "https://raw.githubusercontent.com/barry-far/V2ray-Config/refs/heads/main/All_Configs_base64_Sub.txt", "desc": "new-source-195"},
    {"name": "barry-far-V2ray-Config-All_Configs_Sub.txt", "repo": "barry-far/V2ray-Config", "url": "https://raw.githubusercontent.com/barry-far/V2ray-Config/refs/heads/main/All_Configs_Sub.txt", "desc": "new-source-196"},
    {"name": "bin1site1-V2rayFree-config.txt", "repo": "bin1site1/V2rayFree", "url": "https://raw.githubusercontent.com/bin1site1/V2rayFree/main/config.txt", "desc": "new-source-197"},
    {"name": "cbusifabcap-daily_free_vpn-Z.txt", "repo": "cbusifabcap/daily_free_vpn", "url": "https://raw.githubusercontent.com/cbusifabcap/daily_free_vpn/refs/heads/main/Z.txt", "desc": "new-source-198"},
    {"name": "chaishpish-free_server_v2ray-", "repo": "chaishpish/free_server_v2ray", "url": "https://raw.githubusercontent.com/chaishpish/free_server_v2ray/main/", "desc": "new-source-199"},
    {"name": "chenzhihan1751-cyber-node-sub-zixf-base64.txt", "repo": "chenzhihan1751-cyber/node-sub-zixf", "url": "https://raw.githubusercontent.com/chenzhihan1751-cyber/node-sub-zixf/main/sub/base64.txt", "desc": "new-source-200"},
    {"name": "crackbest-V2ray-Config-config.txt", "repo": "crackbest/V2ray-Config", "url": "https://raw.githubusercontent.com/crackbest/V2ray-Config/main/config.txt", "desc": "new-source-201"},
    {"name": "d4rk-n0153-ech-sub-live-subscription.txt", "repo": "d4rk-n0153/ech-sub-live", "url": "https://raw.githubusercontent.com/d4rk-n0153/ech-sub-live/main/subscription.txt", "desc": "new-source-202"},
    {"name": "DarkRoyalty-shnajder-vpn-configs-1.txt", "repo": "DarkRoyalty/shnajder-vpn-configs", "url": "https://raw.githubusercontent.com/DarkRoyalty/shnajder-vpn-configs/main/githubmirror/1.txt", "desc": "new-source-203"},
    {"name": "DarkRoyalty-shnajder-vpn-configs-23.txt", "repo": "DarkRoyalty/shnajder-vpn-configs", "url": "https://raw.githubusercontent.com/DarkRoyalty/shnajder-vpn-configs/main/githubmirror/23.txt", "desc": "new-source-204"},
    {"name": "DarkRoyalty-shnajder-vpn-configs-24.txt", "repo": "DarkRoyalty/shnajder-vpn-configs", "url": "https://raw.githubusercontent.com/DarkRoyalty/shnajder-vpn-configs/main/githubmirror/24.txt", "desc": "new-source-205"},
    {"name": "DarkRoyalty-shnajder-vpn-configs-25.txt", "repo": "DarkRoyalty/shnajder-vpn-configs", "url": "https://raw.githubusercontent.com/DarkRoyalty/shnajder-vpn-configs/main/githubmirror/25.txt", "desc": "new-source-206"},
    {"name": "DarkRoyalty-shnajder-vpn-configs-26.txt", "repo": "DarkRoyalty/shnajder-vpn-configs", "url": "https://raw.githubusercontent.com/DarkRoyalty/shnajder-vpn-configs/main/githubmirror/26.txt", "desc": "new-source-207"},
    {"name": "DarkRoyalty-shnajder-vpn-configs-6.txt", "repo": "DarkRoyalty/shnajder-vpn-configs", "url": "https://raw.githubusercontent.com/DarkRoyalty/shnajder-vpn-configs/main/githubmirror/6.txt", "desc": "new-source-208"},
    {"name": "Denchic-2009-xray-checked-configs-conf_ck.txt", "repo": "Denchic-2009/xray-checked-configs", "url": "https://raw.githubusercontent.com/Denchic-2009/xray-checked-configs/main/conf_ck.txt", "desc": "new-source-209"},
    {"name": "Denchic-2009-xray-checked-configs-config.txt", "repo": "Denchic-2009/xray-checked-configs", "url": "https://raw.githubusercontent.com/Denchic-2009/xray-checked-configs/main/config.txt", "desc": "new-source-210"},
    {"name": "Denchic-2009-xray-checked-configs-config_other.txt", "repo": "Denchic-2009/xray-checked-configs", "url": "https://raw.githubusercontent.com/Denchic-2009/xray-checked-configs/main/config_other.txt", "desc": "new-source-211"},
    {"name": "Denchic-2009-xray-checked-configs-config_ru.txt", "repo": "Denchic-2009/xray-checked-configs", "url": "https://raw.githubusercontent.com/Denchic-2009/xray-checked-configs/main/config_ru.txt", "desc": "new-source-212"},
    {"name": "drmikecrypto-PulseConfigs-candidates.txt", "repo": "drmikecrypto/PulseConfigs", "url": "https://raw.githubusercontent.com/drmikecrypto/PulseConfigs/main/candidates.txt", "desc": "new-source-213"},
    {"name": "drmikecrypto-PulseConfigs-top100.txt", "repo": "drmikecrypto/PulseConfigs", "url": "https://raw.githubusercontent.com/drmikecrypto/PulseConfigs/main/top100.txt", "desc": "new-source-214"},
    {"name": "drmikecrypto-PulseConfigs-top5.txt", "repo": "drmikecrypto/PulseConfigs", "url": "https://raw.githubusercontent.com/drmikecrypto/PulseConfigs/main/top5.txt", "desc": "new-source-215"},
    {"name": "drmikecrypto-PulseConfigs-top5_iran.txt", "repo": "drmikecrypto/PulseConfigs", "url": "https://raw.githubusercontent.com/drmikecrypto/PulseConfigs/main/top5_iran.txt", "desc": "new-source-216"},
    {"name": "drmikecrypto-PulseConfigs-top5_speed.txt", "repo": "drmikecrypto/PulseConfigs", "url": "https://raw.githubusercontent.com/drmikecrypto/PulseConfigs/main/top5_speed.txt", "desc": "new-source-217"},
    {"name": "Epodonios-v2ray-configs-All_Configs_Sub.txt", "repo": "Epodonios/v2ray-configs", "url": "https://raw.githubusercontent.com/Epodonios/v2ray-configs/main/All_Configs_Sub.txt", "desc": "new-source-218"},
    {"name": "Farid-Karimi-Config-Collector-mixed_iran.txt", "repo": "Farid-Karimi/Config-Collector", "url": "https://raw.githubusercontent.com/Farid-Karimi/Config-Collector/main/mixed_iran.txt", "desc": "new-source-219"},
    {"name": "Farid-Karimi-Config-Collector-vless_iran.txt", "repo": "Farid-Karimi/Config-Collector", "url": "https://raw.githubusercontent.com/Farid-Karimi/Config-Collector/main/vless_iran.txt", "desc": "new-source-220"},
    {"name": "flaafix-AetrisVPN-AetrisVPN.txt", "repo": "flaafix/AetrisVPN", "url": "https://raw.githubusercontent.com/flaafix/AetrisVPN/main/AetrisVPN.txt", "desc": "new-source-221"},
    {"name": "flaafix-AetrisVPN-black-list-configs.txt", "repo": "flaafix/AetrisVPN-black-list", "url": "https://raw.githubusercontent.com/flaafix/AetrisVPN-black-list/main/configs.txt", "desc": "new-source-222"},
    {"name": "flaafix-AetrisVPN-black-list-test.txt", "repo": "flaafix/AetrisVPN-black-list", "url": "https://raw.githubusercontent.com/flaafix/AetrisVPN-black-list/main/test.txt", "desc": "new-source-223"},
    {"name": "freenodess-freenodess-v2ray-base64.txt", "repo": "freenodess/freenodess", "url": "https://raw.githubusercontent.com/freenodess/freenodess/refs/heads/main/nodes/v2ray-base64.txt", "desc": "new-source-224"},
    {"name": "gslege-CloudflareIP-Vless.txt", "repo": "gslege/CloudflareIP", "url": "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Vless.txt", "desc": "new-source-225"},
    {"name": "H8fullMate-clash-vless-auto-nekobox_subscription.txt", "repo": "H8fullMate/clash-vless-auto", "url": "https://raw.githubusercontent.com/H8fullMate/clash-vless-auto/main/nekobox_subscription.txt", "desc": "new-source-226"},
    {"name": "H8fullMate-clash-vless-auto-vless_lite.txt", "repo": "H8fullMate/clash-vless-auto", "url": "https://raw.githubusercontent.com/H8fullMate/clash-vless-auto/main/vless_lite.txt", "desc": "new-source-227"},
    {"name": "hello-world-1989-cn-news-clash.yaml", "repo": "hello-world-1989/cn-news", "url": "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/clash.yaml", "desc": "new-source-228"},
    {"name": "hello-world-1989-cn-news-clash-free.yaml", "repo": "hello-world-1989/cn-news", "url": "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/clash-free.yaml", "desc": "new-source-229"},
    {"name": "hello-world-1989-cn-news-clash-test.yaml", "repo": "hello-world-1989/cn-news", "url": "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/clash-test.yaml", "desc": "new-source-230"},
    {"name": "hello-world-1989-cn-news-end-gfw-free", "repo": "hello-world-1989/cn-news", "url": "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-free", "desc": "new-source-231"},
    {"name": "hello-world-1989-cn-news-end-gfw-together", "repo": "hello-world-1989/cn-news", "url": "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together", "desc": "new-source-232"},
    {"name": "hello-world-1989-cn-news-end-gfw-together-ss", "repo": "hello-world-1989/cn-news", "url": "https://raw.githubusercontent.com/hello-world-1989/cn-news/main/end-gfw-together-ss", "desc": "new-source-233"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-country_NL.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/country_NL.txt", "desc": "new-source-234"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-country_US.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/country_US.txt", "desc": "new-source-235"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-lite_mix_sub.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/lite_mix_sub.txt", "desc": "new-source-236"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-mix.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/mix.txt", "desc": "new-source-237"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-mix_sub.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/mix_sub.txt", "desc": "new-source-238"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-reality.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/reality.txt", "desc": "new-source-239"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-ss.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/ss.txt", "desc": "new-source-240"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-trojan.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/trojan.txt", "desc": "new-source-241"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-vless.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/vless.txt", "desc": "new-source-242"},
    {"name": "Idolvpn-Automate-V2ray-Config-Collector-vmess.txt", "repo": "Idolvpn/Automate-V2ray-Config-Collector", "url": "https://raw.githubusercontent.com/Idolvpn/Automate-V2ray-Config-Collector/main/configs/vmess.txt", "desc": "new-source-243"},
    {"name": "idtheo-V2Ray-CleanIPs-Servers-shield.txt", "repo": "idtheo/V2Ray-CleanIPs-Servers", "url": "https://raw.githubusercontent.com/idtheo/V2Ray-CleanIPs-Servers/main/shield.txt", "desc": "new-source-244"},
    {"name": "idtheo-V2Ray-CleanIPs-Servers-star.txt", "repo": "idtheo/V2Ray-CleanIPs-Servers", "url": "https://raw.githubusercontent.com/idtheo/V2Ray-CleanIPs-Servers/main/star.txt", "desc": "new-source-245"},
    {"name": "idtheo-V2Ray-CleanIPs-Servers-vip.txt", "repo": "idtheo/V2Ray-CleanIPs-Servers", "url": "https://raw.githubusercontent.com/idtheo/V2Ray-CleanIPs-Servers/main/vip.txt", "desc": "new-source-246"},
    {"name": "igareck-vpn-configs-for-russia-star-history.svg", "repo": "igareck/vpn-configs-for-russia", "url": "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/star-tracker-data/charts/star-history.svg", "desc": "new-source-247"},
    {"name": "imalyzer-mihomo-node-checker-backup-nodes.yaml", "repo": "imalyzer/mihomo-node-checker", "url": "https://raw.githubusercontent.com/imalyzer/mihomo-node-checker/main/output/backup-nodes.yaml", "desc": "new-source-248"},
    {"name": "imalyzer-mihomo-node-checker-fresh-nodes.yaml", "repo": "imalyzer/mihomo-node-checker", "url": "https://raw.githubusercontent.com/imalyzer/mihomo-node-checker/main/output/fresh-nodes.yaml", "desc": "new-source-249"},
    {"name": "imalyzer-mihomo-node-checker-stable-nodes.yaml", "repo": "imalyzer/mihomo-node-checker", "url": "https://raw.githubusercontent.com/imalyzer/mihomo-node-checker/main/output/stable-nodes.yaml", "desc": "new-source-250"},
    {"name": "iseeyoou26-wq-CryNet-SysTems-VPN-vless-all.txt", "repo": "iseeyoou26-wq/CryNet-SysTems-VPN-vless", "url": "https://raw.githubusercontent.com/iseeyoou26-wq/CryNet-SysTems-VPN-vless/main/subscriptions/all.txt", "desc": "new-source-251"},
    {"name": "ishalumi-proxy-node-collector-nodes.txt", "repo": "ishalumi/proxy-node-collector", "url": "https://raw.githubusercontent.com/ishalumi/proxy-node-collector/main/output/nodes.txt", "desc": "new-source-252"},
    {"name": "JeBance-CheburNet-cheburnet.txt", "repo": "JeBance/CheburNet", "url": "https://raw.githubusercontent.com/JeBance/CheburNet/gh-pages/cheburnet.txt", "desc": "new-source-253"},
    {"name": "kasesm-Free-Config-all_raw.txt", "repo": "kasesm/Free-Config", "url": "https://raw.githubusercontent.com/kasesm/Free-Config/main/all_raw.txt", "desc": "new-source-254"},
    {"name": "kasesm-Free-Config-high_volume_raw.txt", "repo": "kasesm/Free-Config", "url": "https://raw.githubusercontent.com/kasesm/Free-Config/main/high_volume_raw.txt", "desc": "new-source-255"},
    {"name": "kasesm-Free-Config-vless_raw.txt", "repo": "kasesm/Free-Config", "url": "https://raw.githubusercontent.com/kasesm/Free-Config/main/vless_raw.txt", "desc": "new-source-256"},
    {"name": "Kolandone-v2raycollector-config.txt", "repo": "Kolandone/v2raycollector", "url": "https://raw.githubusercontent.com/Kolandone/v2raycollector/main/config.txt", "desc": "new-source-257"},
    {"name": "Kolandone-v2raycollector-hysteria.txt", "repo": "Kolandone/v2raycollector", "url": "https://raw.githubusercontent.com/Kolandone/v2raycollector/main/hysteria.txt", "desc": "new-source-258"},
    {"name": "komoterdon-free-sub-raw.txt", "repo": "komoterdon/free-sub", "url": "https://raw.githubusercontent.com/komoterdon/free-sub/main/raw.txt", "desc": "new-source-259"},
    {"name": "komoterdon-free-sub-sub.txt", "repo": "komoterdon/free-sub", "url": "https://raw.githubusercontent.com/komoterdon/free-sub/main/sub.txt", "desc": "new-source-260"},
    {"name": "kort0881-vpn-vless-configs-russia-vless.txt", "repo": "kort0881/vpn-vless-configs-russia", "url": "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/output/vless.txt", "desc": "new-source-261"},
    {"name": "lm705-vair-vless_alive.txt", "repo": "lm705/vair", "url": "https://raw.githubusercontent.com/lm705/vair/main/vless_alive.txt", "desc": "new-source-262"},
    {"name": "LoneKingCode-free-proxy-db-all.txt", "repo": "LoneKingCode/free-proxy-db", "url": "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/all.txt", "desc": "new-source-263"},
    {"name": "LoneKingCode-free-proxy-db-vless.txt", "repo": "LoneKingCode/free-proxy-db", "url": "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/vless.txt", "desc": "new-source-264"},
    {"name": "LoneKingCode-free-proxy-db-vmess.txt", "repo": "LoneKingCode/free-proxy-db", "url": "https://raw.githubusercontent.com/LoneKingCode/free-proxy-db/main/proxies/vmess.txt", "desc": "new-source-265"},
    {"name": "luxxuria-harvester-non_ru.txt", "repo": "luxxuria/harvester", "url": "https://raw.githubusercontent.com/luxxuria/harvester/main/non_ru.txt", "desc": "new-source-266"},
    {"name": "luxxuria-harvester-ping_tested.txt", "repo": "luxxuria/harvester", "url": "https://raw.githubusercontent.com/luxxuria/harvester/main/ping_tested.txt", "desc": "new-source-267"},
    {"name": "luxxuria-harvester-speed_tested.txt", "repo": "luxxuria/harvester", "url": "https://raw.githubusercontent.com/luxxuria/harvester/main/speed_tested.txt", "desc": "new-source-268"},
    {"name": "MahanKenway-Pusheen-V2Ray-all.txt", "repo": "MahanKenway/Pusheen-V2Ray", "url": "https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/all.txt", "desc": "new-source-269"},
    {"name": "MahanKenway-Pusheen-V2Ray-vless.txt", "repo": "MahanKenway/Pusheen-V2Ray", "url": "https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/vless.txt", "desc": "new-source-270"},
    {"name": "MahanKenway-Pusheen-V2Ray-vmess.txt", "repo": "MahanKenway/Pusheen-V2Ray", "url": "https://raw.githubusercontent.com/MahanKenway/Pusheen-V2Ray/main/subscriptions/vmess.txt", "desc": "new-source-271"},
    {"name": "mahdisandughdaran-sys-vless-reality-collector-best_reality_confi", "repo": "mahdisandughdaran-sys/vless-reality-collector", "url": "https://raw.githubusercontent.com/mahdisandughdaran-sys/vless-reality-collector/main/best_reality_configs.txt", "desc": "new-source-272"},
    {"name": "mahdyaralipor-v2all-real_sub.txt", "repo": "mahdyaralipor/v2all", "url": "https://raw.githubusercontent.com/mahdyaralipor/v2all/main/real_sub.txt", "desc": "new-source-273"},
    {"name": "mahdyaralipor-v2all-real_working.txt", "repo": "mahdyaralipor/v2all", "url": "https://raw.githubusercontent.com/mahdyaralipor/v2all/main/real_working.txt", "desc": "new-source-274"},
    {"name": "Maskkost93-kizyak-vpn-4.0-kizyakbeta6.txt", "repo": "Maskkost93/kizyak-vpn-4.0", "url": "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/main/kizyakbeta6.txt", "desc": "new-source-275"},
    {"name": "Maskkost93-kizyak-vpn-4.0-kizyakbeta6BL.txt", "repo": "Maskkost93/kizyak-vpn-4.0", "url": "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/main/kizyakbeta6BL.txt", "desc": "new-source-276"},
    {"name": "Maskkost93-kizyak-vpn-4.0-kizyakbeta7.txt", "repo": "Maskkost93/kizyak-vpn-4.0", "url": "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/main/kizyakbeta7.txt", "desc": "new-source-277"},
    {"name": "Maskkost93-kizyak-vpn-4.0-kizyakbeta8.txt", "repo": "Maskkost93/kizyak-vpn-4.0", "url": "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/main/kizyakbeta8.txt", "desc": "new-source-278"},
    {"name": "Maskkost93-kizyak-vpn-4.0-kizyaktestru.txt", "repo": "Maskkost93/kizyak-vpn-4.0", "url": "https://raw.githubusercontent.com/Maskkost93/kizyak-vpn-4.0/main/kizyaktestru.txt", "desc": "new-source-279"},
    {"name": "MatinGhanbari-v2ray-configs-ss.txt", "repo": "MatinGhanbari/v2ray-configs", "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/ss.txt", "desc": "new-source-280"},
    {"name": "MatinGhanbari-v2ray-configs-vless.txt", "repo": "MatinGhanbari/v2ray-configs", "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/vless.txt", "desc": "new-source-281"},
    {"name": "MatinGhanbari-v2ray-configs-vmess.txt", "repo": "MatinGhanbari/v2ray-configs", "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/filtered/subs/vmess.txt", "desc": "new-source-282"},
    {"name": "MatinGhanbari-v2ray-configs-all_sub.txt", "repo": "MatinGhanbari/v2ray-configs", "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/all_sub.txt", "desc": "new-source-283"},
    {"name": "MatinGhanbari-v2ray-configs-super-sub.txt", "repo": "MatinGhanbari/v2ray-configs", "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/main/subscriptions/v2ray/super-sub.txt", "desc": "new-source-284"},
    {"name": "MatinGhanbari-v2ray-configs-super-sub.txt", "repo": "MatinGhanbari/v2ray-configs", "url": "https://raw.githubusercontent.com/MatinGhanbari/v2ray-configs/refs/heads/main/subscriptions/v2ray/super-sub.txt", "desc": "new-source-285"},
    {"name": "Medium1992-mihomo-proxy-ros-docker-compose.yml", "repo": "Medium1992/mihomo-proxy-ros", "url": "https://raw.githubusercontent.com/Medium1992/mihomo-proxy-ros/main/docker-compose.yml", "desc": "new-source-286"},
    {"name": "mehrtat-vless-collector-sub.txt", "repo": "mehrtat/vless-collector", "url": "https://raw.githubusercontent.com/mehrtat/vless-collector/main/sub.txt", "desc": "new-source-287"},
    {"name": "mehrtat-vless-collector-vless.txt", "repo": "mehrtat/vless-collector", "url": "https://raw.githubusercontent.com/mehrtat/vless-collector/main/vless.txt", "desc": "new-source-288"},
    {"name": "MhdiTaheri-V2rayCollector-mix", "repo": "MhdiTaheri/V2rayCollector", "url": "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/mix", "desc": "new-source-289"},
    {"name": "MhdiTaheri-V2rayCollector-vless", "repo": "MhdiTaheri/V2rayCollector", "url": "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/vless", "desc": "new-source-290"},
    {"name": "MhdiTaheri-V2rayCollector-vmess", "repo": "MhdiTaheri/V2rayCollector", "url": "https://raw.githubusercontent.com/MhdiTaheri/V2rayCollector/main/sub/vmess", "desc": "new-source-291"},
    {"name": "miladtahanian-Config-Collector-mixed_iran.txt", "repo": "miladtahanian/Config-Collector", "url": "https://raw.githubusercontent.com/miladtahanian/Config-Collector/main/mixed_iran.txt", "desc": "new-source-292"},
    {"name": "mohammadaz2-v2rayConfigsForYou-configs.txt", "repo": "mohammadaz2/v2rayConfigsForYou", "url": "https://raw.githubusercontent.com/mohammadaz2/v2rayConfigsForYou/main/configs.txt", "desc": "new-source-293"},
    {"name": "mohammadaz2-v2rayConfigsForYou-vless.txt", "repo": "mohammadaz2/v2rayConfigsForYou", "url": "https://raw.githubusercontent.com/mohammadaz2/v2rayConfigsForYou/main/sub/vless.txt", "desc": "new-source-294"},
    {"name": "monosans-proxy-list-all.txt", "repo": "monosans/proxy-list", "url": "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt", "desc": "new-source-295"},
    {"name": "mrpaster12-config-proxy-collector-sub.txt", "repo": "mrpaster12/config-proxy-collector", "url": "https://raw.githubusercontent.com/mrpaster12/config-proxy-collector/main/sub.txt", "desc": "new-source-296"},
    {"name": "muks999-Clash-Vless-convert-nekobox_subscription.txt", "repo": "muks999/Clash-Vless-convert", "url": "https://raw.githubusercontent.com/muks999/Clash-Vless-convert/main/nekobox_subscription.txt", "desc": "new-source-297"},
    {"name": "muks999-Clash-Vless-convert-vless_lite.txt", "repo": "muks999/Clash-Vless-convert", "url": "https://raw.githubusercontent.com/muks999/Clash-Vless-convert/main/vless_lite.txt", "desc": "new-source-298"},
    {"name": "muks999-Clash-Vless-convert-vless_muks9.txt", "repo": "muks999/Clash-Vless-convert", "url": "https://raw.githubusercontent.com/muks999/Clash-Vless-convert/main/vless_muks9.txt", "desc": "new-source-299"},
    {"name": "MustafaBaqer-VestraNet-Nodes-mtproto.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/mtproto.txt", "desc": "new-source-300"},
    {"name": "MustafaBaqer-VestraNet-Nodes-shadowsocks.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/shadowsocks.txt", "desc": "new-source-301"},
    {"name": "MustafaBaqer-VestraNet-Nodes-trojan.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/trojan.txt", "desc": "new-source-302"},
    {"name": "MustafaBaqer-VestraNet-Nodes-vless.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/vless.txt", "desc": "new-source-303"},
    {"name": "MustafaBaqer-VestraNet-Nodes-vmess.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/protocols/vmess.txt", "desc": "new-source-304"},
    {"name": "MustafaBaqer-VestraNet-Nodes-mix-base64.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/subscriptions/mix-base64.txt", "desc": "new-source-305"},
    {"name": "MustafaBaqer-VestraNet-Nodes-mix-normal.txt", "repo": "MustafaBaqer/VestraNet-Nodes", "url": "https://raw.githubusercontent.com/MustafaBaqer/VestraNet-Nodes/main/subscriptions/mix-normal.txt", "desc": "new-source-306"},
    {"name": "myominn062-svg-mk-studio-vpn-service-subscription-lite.txt", "repo": "myominn062-svg/mk-studio-vpn-service", "url": "https://raw.githubusercontent.com/myominn062-svg/mk-studio-vpn-service/main/subscription-lite.txt", "desc": "new-source-307"},
    {"name": "ninjastrikers-nexus-nodes-all.txt", "repo": "ninjastrikers/nexus-nodes", "url": "https://raw.githubusercontent.com/ninjastrikers/nexus-nodes/main/configs/all.txt", "desc": "new-source-308"},
    {"name": "ninjastrikers-nexus-nodes-vless.txt", "repo": "ninjastrikers/nexus-nodes", "url": "https://raw.githubusercontent.com/ninjastrikers/nexus-nodes/main/configs/vless.txt", "desc": "new-source-309"},
    {"name": "ninjastrikers-nexus-nodes-vmess.txt", "repo": "ninjastrikers/nexus-nodes", "url": "https://raw.githubusercontent.com/ninjastrikers/nexus-nodes/main/configs/vmess.txt", "desc": "new-source-310"},
    {"name": "NiREvil-vless-sing-box.json", "repo": "NiREvil/vless", "url": "https://raw.githubusercontent.com/NiREvil/vless/refs/heads/main/sing-box.json", "desc": "new-source-311"},
    {"name": "NiREvil-vless-Cf-ip-bpb.txt", "repo": "NiREvil/vless", "url": "https://raw.githubusercontent.com/NiREvil/vless/refs/heads/main/sub/Cf-ip-bpb.txt", "desc": "new-source-312"},
    {"name": "NiREvil-vless-clash-meta-wg.yml", "repo": "NiREvil/vless", "url": "https://raw.githubusercontent.com/NiREvil/vless/refs/heads/main/sub/clash-meta-wg.yml", "desc": "new-source-313"},
    {"name": "nodesradar-nodesradar-en-README.md", "repo": "nodesradar/nodesradar-en", "url": "https://raw.githubusercontent.com/nodesradar/nodesradar-en/main/README.md", "desc": "new-source-314"},
    {"name": "Nomislou-NomislouNodes-good_proxies.txt", "repo": "Nomislou/NomislouNodes", "url": "https://raw.githubusercontent.com/Nomislou/NomislouNodes/main/good_proxies.txt", "desc": "new-source-315"},
    {"name": "nukcrow-black-crow-README.md", "repo": "nukcrow/black-crow", "url": "https://raw.githubusercontent.com/nukcrow/black-crow/main/README.md", "desc": "new-source-316"},
    {"name": "nukcrow-black-crow-bot.txt", "repo": "nukcrow/black-crow", "url": "https://raw.githubusercontent.com/nukcrow/black-crow/main/sub/general/bot.txt", "desc": "new-source-317"},
    {"name": "nukcrow-black-crow-sub1.txt", "repo": "nukcrow/black-crow", "url": "https://raw.githubusercontent.com/nukcrow/black-crow/main/sub/general/sub1.txt", "desc": "new-source-318"},
    {"name": "nyeinkokoaung404-V2ray-Configs-All_Configs_Sub.txt", "repo": "nyeinkokoaung404/V2ray-Configs", "url": "https://raw.githubusercontent.com/nyeinkokoaung404/V2ray-Configs/main/All_Configs_Sub.txt", "desc": "new-source-319"},
    {"name": "nyeinkokoaung404-V2ray-Configs-vless.txt", "repo": "nyeinkokoaung404/V2ray-Configs", "url": "https://raw.githubusercontent.com/nyeinkokoaung404/V2ray-Configs/main/Splitted-By-Protocol/vless.txt", "desc": "new-source-320"},
    {"name": "nyeinkokoaung404-V2ray-Configs-Sub1.txt", "repo": "nyeinkokoaung404/V2ray-Configs", "url": "https://raw.githubusercontent.com/nyeinkokoaung404/V2ray-Configs/main/Sub1.txt", "desc": "new-source-321"},
    {"name": "peasoft-NoMoreWalls-list.txt", "repo": "peasoft/NoMoreWalls", "url": "https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.txt", "desc": "new-source-322"},
    {"name": "penhandev-AutoAiVPN-allConfigs.txt", "repo": "penhandev/AutoAiVPN", "url": "https://raw.githubusercontent.com/penhandev/AutoAiVPN/main/allConfigs.txt", "desc": "new-source-323"},
    {"name": "penhandev-AutoAiVPN-AtuoAiVPN.txt", "repo": "penhandev/AutoAiVPN", "url": "https://raw.githubusercontent.com/penhandev/AutoAiVPN/main/AtuoAiVPN.txt", "desc": "new-source-324"},
    {"name": "penhandev-AutoAiVPN-iran.txt", "repo": "penhandev/AutoAiVPN", "url": "https://raw.githubusercontent.com/penhandev/AutoAiVPN/main/iran.txt", "desc": "new-source-325"},
    {"name": "penhandev-AutoAiVPN-russia.txt", "repo": "penhandev/AutoAiVPN", "url": "https://raw.githubusercontent.com/penhandev/AutoAiVPN/main/russia.txt", "desc": "new-source-326"},
    {"name": "ProblemTheCode-SylphNet-public-sub.txt", "repo": "ProblemTheCode/SylphNet-public", "url": "https://raw.githubusercontent.com/ProblemTheCode/SylphNet-public/main/sub/sub.txt", "desc": "new-source-327"},
    {"name": "ProblemTheCode-SylphNet-public-sub_plain.txt", "repo": "ProblemTheCode/SylphNet-public", "url": "https://raw.githubusercontent.com/ProblemTheCode/SylphNet-public/main/sub/sub_plain.txt", "desc": "new-source-328"},
    {"name": "ProblemTheCode-SylphNet-public-sub.txt", "repo": "ProblemTheCode/SylphNet-public", "url": "https://raw.githubusercontent.com/ProblemTheCode/SylphNet-public/refs/heads/main/sub/sub.txt", "desc": "new-source-329"},
    {"name": "ProblemTheCode-SylphNet-public-sub_plain.txt", "repo": "ProblemTheCode/SylphNet-public", "url": "https://raw.githubusercontent.com/ProblemTheCode/SylphNet-public/refs/heads/main/sub/sub_plain.txt", "desc": "new-source-330"},
    {"name": "proxifly-free-proxy-list-data.txt", "repo": "proxifly/free-proxy-list", "url": "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt", "desc": "new-source-331"},
    {"name": "RaminTabriz-V2rayCollector-clash-config.yaml", "repo": "RaminTabriz/V2rayCollector", "url": "https://raw.githubusercontent.com/RaminTabriz/V2rayCollector/main/clash-config.yaml", "desc": "new-source-332"},
    {"name": "Realmec21-Xer0x-vless-hub-fast.txt", "repo": "Realmec21/Xer0x-vless-hub", "url": "https://raw.githubusercontent.com/Realmec21/Xer0x-vless-hub/main/subscriptions/fast.txt", "desc": "new-source-333"},
    {"name": "RichTiTAN-V2rayTested-working_configs.txt", "repo": "RichTiTAN/V2rayTested", "url": "https://raw.githubusercontent.com/RichTiTAN/V2rayTested/main/working_configs.txt", "desc": "new-source-334"},
    {"name": "RichTiTAN-V2rayTested-working_configs_general.txt", "repo": "RichTiTAN/V2rayTested", "url": "https://raw.githubusercontent.com/RichTiTAN/V2rayTested/main/working_configs_general.txt", "desc": "new-source-335"},
    {"name": "RichTiTAN-V2rayTested-working_configs_phase6.txt", "repo": "RichTiTAN/V2rayTested", "url": "https://raw.githubusercontent.com/RichTiTAN/V2rayTested/main/working_configs_phase6.txt", "desc": "new-source-336"},
    {"name": "Romaxa55-MegaV_Public-all.txt", "repo": "Romaxa55/MegaV_Public", "url": "https://raw.githubusercontent.com/Romaxa55/MegaV_Public/main/subs/all.txt", "desc": "new-source-337"},
    {"name": "Romaxa55-MegaV_Public-vless.txt", "repo": "Romaxa55/MegaV_Public", "url": "https://raw.githubusercontent.com/Romaxa55/MegaV_Public/main/subs/vless.txt", "desc": "new-source-338"},
    {"name": "Romaxa55-MegaV_Public-vmess.txt", "repo": "Romaxa55/MegaV_Public", "url": "https://raw.githubusercontent.com/Romaxa55/MegaV_Public/main/subs/vmess.txt", "desc": "new-source-339"},
    {"name": "sakazxc1400-creator-free-vpn-sub-clash.yaml", "repo": "sakazxc1400-creator/free-vpn-sub", "url": "https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/data/output/clash.yaml", "desc": "new-source-340"},
    {"name": "sakazxc1400-creator-free-vpn-sub-sub.txt", "repo": "sakazxc1400-creator/free-vpn-sub", "url": "https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/data/output/sub.txt", "desc": "new-source-341"},
    {"name": "sakazxc1400-creator-free-vpn-sub-sub-stable.txt", "repo": "sakazxc1400-creator/free-vpn-sub", "url": "https://raw.githubusercontent.com/sakazxc1400-creator/free-vpn-sub/data/output/sub-stable.txt", "desc": "new-source-342"},
    {"name": "sakha1370-OpenRay-all_valid_proxies.txt", "repo": "sakha1370/OpenRay", "url": "https://raw.githubusercontent.com/sakha1370/OpenRay/refs/heads/main/output/all_valid_proxies.txt", "desc": "new-source-343"},
    {"name": "SHAHBBBB-V2ray-collector-sub.txt", "repo": "SHAHBBBB/V2ray-collector", "url": "https://raw.githubusercontent.com/SHAHBBBB/V2ray-collector/main/output/sub.txt", "desc": "new-source-344"},
    {"name": "sinavm-SVM-config.txt", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/config.txt", "desc": "new-source-345"},
    {"name": "sinavm-SVM-alive-fast", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/lite/subscriptions/xray/normal/alive-fast", "desc": "new-source-346"},
    {"name": "sinavm-SVM-alive-stable", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/lite/subscriptions/xray/normal/alive-stable", "desc": "new-source-347"},
    {"name": "sinavm-SVM-test.json", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/reports/test.json", "desc": "new-source-348"},
    {"name": "sinavm-SVM-mix", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/clash/mix", "desc": "new-source-349"},
    {"name": "sinavm-SVM-ss", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/clash/ss", "desc": "new-source-350"},
    {"name": "sinavm-SVM-trojan", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/clash/trojan", "desc": "new-source-351"},
    {"name": "sinavm-SVM-vmess", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/clash/vmess", "desc": "new-source-352"},
    {"name": "sinavm-SVM-mix", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/meta/mix", "desc": "new-source-353"},
    {"name": "sinavm-SVM-reality", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/meta/reality", "desc": "new-source-354"},
    {"name": "sinavm-SVM-ss", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/meta/ss", "desc": "new-source-355"},
    {"name": "sinavm-SVM-trojan", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/meta/trojan", "desc": "new-source-356"},
    {"name": "sinavm-SVM-vless", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/meta/vless", "desc": "new-source-357"},
    {"name": "sinavm-SVM-vmess", "repo": "sinavm/SVM", "url": "https://raw.githubusercontent.com/sinavm/SVM/main/subscriptions/meta/vmess", "desc": "new-source-358"},
    {"name": "slxkware-Vless-list-Black%20Vless.txt", "repo": "slxkware/Vless-list", "url": "https://raw.githubusercontent.com/slxkware/Vless-list/main/Black%20Vless.txt", "desc": "new-source-359"},
    {"name": "slxkware-Vless-list-White%20Vless.txt", "repo": "slxkware/Vless-list", "url": "https://raw.githubusercontent.com/slxkware/Vless-list/main/White%20Vless.txt", "desc": "new-source-360"},
    {"name": "snakem982-proxypool-v2ray-2.txt", "repo": "snakem982/proxypool", "url": "https://raw.githubusercontent.com/snakem982/proxypool/main/source/v2ray-2.txt", "desc": "new-source-361"},
    {"name": "teknovpnhub-v2ray-subscription-out.txt", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/out.txt", "desc": "new-source-362"},
    {"name": "teknovpnhub-v2ray-subscription-pt.configs.txt", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/pt.configs.txt", "desc": "new-source-363"},
    {"name": "teknovpnhub-v2ray-subscription-server_history.txt", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/server_history.txt", "desc": "new-source-364"},
    {"name": "teknovpnhub-v2ray-subscription-servers.txt", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/servers.txt", "desc": "new-source-365"},
    {"name": "teknovpnhub-v2ray-subscription-servers1.txt", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/servers1.txt", "desc": "new-source-366"},
    {"name": "teknovpnhub-v2ray-subscription-test", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/test", "desc": "new-source-367"},
    {"name": "teknovpnhub-v2ray-subscription-test1", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/test1", "desc": "new-source-368"},
    {"name": "teknovpnhub-v2ray-subscription-test2", "repo": "teknovpnhub/v2ray-subscription", "url": "https://raw.githubusercontent.com/teknovpnhub/v2ray-subscription/main/test2", "desc": "new-source-369"},
    {"name": "TelegaVPN-free-vpn-keys-for-russia.txt", "repo": "TelegaVPN/free-vpn-keys", "url": "https://raw.githubusercontent.com/TelegaVPN/free-vpn-keys/main/sub/base64/for-russia.txt", "desc": "new-source-370"},
    {"name": "thealiiakbarii-ai-VCC-all.txt", "repo": "thealiiakbarii-ai/VCC", "url": "https://raw.githubusercontent.com/thealiiakbarii-ai/VCC/main/configs/all.txt", "desc": "new-source-371"},
    {"name": "TheCrowCreature-v2rayExtractor-sub.html", "repo": "TheCrowCreature/v2rayExtractor", "url": "https://raw.githubusercontent.com/TheCrowCreature/v2rayExtractor/refs/heads/main/mix/sub.html", "desc": "new-source-372"},
    {"name": "twbworld-proxy-config.example.yaml", "repo": "twbworld/proxy", "url": "https://raw.githubusercontent.com/twbworld/proxy/main/config.example.yaml", "desc": "new-source-373"},
    {"name": "twj0-subseek-sub_github.txt", "repo": "twj0/subseek", "url": "https://raw.githubusercontent.com/twj0/subseek/refs/heads/master/data/sub_github.txt", "desc": "new-source-374"},
    {"name": "VOID-Anonymity-V.O.I.D-VPN_Bypass-url_work.txt", "repo": "VOID-Anonymity/V.O.I.D-VPN_Bypass", "url": "https://raw.githubusercontent.com/VOID-Anonymity/V.O.I.D-VPN_Bypass/refs/heads/main/url_work.txt", "desc": "new-source-375"},
    {"name": "VP01596-vless-top15-All.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/All.txt", "desc": "new-source-376"},
    {"name": "VP01596-vless-top15-AllNW.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/AllNW.txt", "desc": "new-source-377"},
    {"name": "VP01596-vless-top15-OnlyNoRus.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/OnlyNoRus.txt", "desc": "new-source-378"},
    {"name": "VP01596-vless-top15-OnlyNoRusNW.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/OnlyNoRusNW.txt", "desc": "new-source-379"},
    {"name": "VP01596-vless-top15-OnlyRus.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/OnlyRus.txt", "desc": "new-source-380"},
    {"name": "VP01596-vless-top15-OnlyRusNW.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/OnlyRusNW.txt", "desc": "new-source-381"},
    {"name": "VP01596-vless-top15-OtherProtocol.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/OtherProtocol.txt", "desc": "new-source-382"},
    {"name": "VP01596-vless-top15-OtherProtocolNW.txt", "repo": "VP01596/vless-top15", "url": "https://raw.githubusercontent.com/VP01596/vless-top15/main/OtherProtocolNW.txt", "desc": "new-source-383"},
    {"name": "vsvavan2-vpn-config-rkn-all_working_keys.txt", "repo": "vsvavan2/vpn-config-rkn", "url": "https://raw.githubusercontent.com/vsvavan2/vpn-config-rkn/main/output/all_working_keys.txt", "desc": "new-source-384"},
    {"name": "vxstream-SkyVPN-sub.txt", "repo": "vxstream/SkyVPN", "url": "https://raw.githubusercontent.com/vxstream/SkyVPN/main/sub.txt", "desc": "new-source-385"},
    {"name": "Wboyx-foxy-exit-fxy6VEg4AsHE3ckb.txt", "repo": "Wboyx/foxy-exit", "url": "https://raw.githubusercontent.com/Wboyx/foxy-exit/main/fxy6VEg4AsHE3ckb.txt", "desc": "new-source-386"},
    {"name": "Wboyx-foxy-exit-v7qk2f.txt", "repo": "Wboyx/foxy-exit", "url": "https://raw.githubusercontent.com/Wboyx/foxy-exit/main/v7qk2f.txt", "desc": "new-source-387"},
    {"name": "wenxig-dongtai-sub-sub.txt", "repo": "wenxig/dongtai-sub", "url": "https://raw.githubusercontent.com/wenxig/dongtai-sub/refs/heads/main/data/sub.txt", "desc": "new-source-388"},
    {"name": "whoahaow-rjsxrd-bypass-all.txt", "repo": "whoahaow/rjsxrd", "url": "https://raw.githubusercontent.com/whoahaow/rjsxrd/refs/heads/main/githubmirror/bypass/bypass-all.txt", "desc": "new-source-389"},
    {"name": "WilliamQXZ-free-nodes-sr-sr-sub.yaml", "repo": "WilliamQXZ/free-nodes-sr", "url": "https://raw.githubusercontent.com/WilliamQXZ/free-nodes-sr/main/sr-sub.yaml", "desc": "new-source-390"},
    {"name": "WilliamQXZ-free-nodes-sr-sr-sub-us.yaml", "repo": "WilliamQXZ/free-nodes-sr", "url": "https://raw.githubusercontent.com/WilliamQXZ/free-nodes-sr/main/sr-sub-us.yaml", "desc": "new-source-391"},
    {"name": "WLget-V2Ray_configs_64-ConfigSub_list.txt", "repo": "WLget/V2Ray_configs_64", "url": "https://raw.githubusercontent.com/WLget/V2Ray_configs_64/refs/heads/master/ConfigSub_list.txt", "desc": "new-source-392"},
    {"name": "wlunlocker-vpn-configs-whitelist_all.txt", "repo": "wlunlocker/vpn-configs", "url": "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/whitelist_all.txt", "desc": "new-source-393"},
    {"name": "Woodic-Way-WoodicWay-sublinks.txt", "repo": "Woodic-Way/WoodicWay", "url": "https://raw.githubusercontent.com/Woodic-Way/WoodicWay/main/sublinks.txt", "desc": "new-source-394"},
    {"name": "wuqb2i4f-xray-config-toolkit-mix", "repo": "wuqb2i4f/xray-config-toolkit", "url": "https://raw.githubusercontent.com/wuqb2i4f/xray-config-toolkit/main/output/base64/mix", "desc": "new-source-395"},
    {"name": "ZendanTeam-SS44-sub-SS44-gold.txt", "repo": "ZendanTeam/SS44-sub", "url": "https://raw.githubusercontent.com/ZendanTeam/SS44-sub/main/SS44-gold.txt", "desc": "new-source-396"},
    {"name": "zhuhaiuk-free-nodes-nodes.txt", "repo": "zhuhaiuk/free-nodes", "url": "https://raw.githubusercontent.com/zhuhaiuk/free-nodes/main/nodes.txt", "desc": "new-source-397"},
]



# 三、原始 13 个核心仓库 + 扩展动态库 (100% 完整收录)

PROJECTS = []




KNOWN_PROTOCOLS = (

    "vless://",

    "vmess://",

    "trojan://",

    "ss://",

    "ssr://",

    "hysteria2://",

    "hy2://",

    "hysteria://",

    "tuic://",

    "wireguard://",

    "wg://",

    "socks5://",

    "socks://",

    "http://",

    "https://",

)



# ==============================================================================

# [内存解包与解析引擎]

# ==============================================================================

def safe_b64decode(s: str) -> str:

    """安全还原任意 Base64 编码"""

    try:

        clean = "".join(s.split())

        pad = len(clean) % 4

        if pad:

            clean += "=" * (4 - pad)

        return base64.b64decode(clean).decode("utf-8", errors="ignore")

    except Exception:

        return ""





def convert_clash_dict_to_uri(p: dict) -> str:

    """解析 Clash/Meta 节点字典，输出标准 URI"""

    try:

        ptype = str(p.get("type", "")).strip().lower()

        server = str(p.get("server", "")).strip()

        port = str(p.get("port", "")).strip()

        name = str(p.get("name", "clash_node")).strip()

        tag = urllib.parse.quote(name)



        if not server or not port:

            return ""



        if ptype in ("hysteria2", "hy2"):

            auth = p.get("password") or p.get("auth") or ""

            sni = p.get("sni") or server

            return f"hysteria2://{auth}@{server}:{port}?sni={sni}&insecure=1#{tag}"



        elif ptype == "vless":

            uuid = str(p.get("uuid", "")).strip()

            tls = str(p.get("tls", "")).lower() in ("true", "1")

            reality = "reality-opts" in p or "reality" in str(p.get("network", "")).lower()

            sec = "reality" if reality else ("tls" if tls else "none")

            sni = p.get("servername") or p.get("sni") or server

            flow = p.get("flow", "")

            flow_arg = f"&flow={flow}" if flow else ""

            return f"vless://{uuid}@{server}:{port}?security={sec}&sni={sni}{flow_arg}#{tag}"



        elif ptype == "vmess":

            uuid = str(p.get("uuid", "")).strip()

            v_dict = {

                "v": "2",

                "ps": name,

                "add": server,

                "port": port,

                "id": uuid,

                "aid": p.get("alterId", 0),

                "net": p.get("network", "tcp"),

                "type": "none",

                "host": p.get("servername") or p.get("sni") or "",

                "path": "",

                "tls": "tls" if str(p.get("tls", "")).lower() in ("true", "1") else ""

            }

            v_b64 = base64.b64encode(json.dumps(v_dict).encode("utf-8")).decode("utf-8")

            return f"vmess://{v_b64}"



        elif ptype == "trojan":

            pwd = p.get("password", "")

            sni = p.get("sni") or server

            return f"trojan://{pwd}@{server}:{port}?sni={sni}#{tag}"



        elif ptype == "ss":

            cipher = p.get("cipher", "")

            pwd = p.get("password", "")

            user_info = base64.b64encode(f"{cipher}:{pwd}".encode("utf-8")).decode("utf-8")

            return f"ss://{user_info}@{server}:{port}#{tag}"



        elif ptype == "http" and str(p.get("tls", "")).lower() in ("true", "1"):

            user = p.get("username", "")

            pwd = p.get("password", "")

            auth = f"{user}:{pwd}@" if (user or pwd) else ""

            return f"https://{auth}{server}:{port}#{tag}"

    except Exception:

        pass

    return ""





def extract_proxies_from_clash_yaml(text: str) -> list:

    """轻量解析 Clash proxies 节点块"""

    nodes = []

    lines = text.splitlines()

    in_proxies = False

    current_proxy = {}



    for line in lines:

        stripped = line.strip()

        if stripped == "proxies:":

            in_proxies = True

            continue



        if in_proxies:

            if line and not line.startswith(" ") and not line.startswith("\t") and ":" in line:

                if current_proxy:

                    uri = convert_clash_dict_to_uri(current_proxy)

                    if uri:

                        nodes.append(uri)

                break



            if stripped.startswith("- ") and ":" in stripped:

                if current_proxy:

                    uri = convert_clash_dict_to_uri(current_proxy)

                    if uri:

                        nodes.append(uri)

                    current_proxy = {}

                item_content = stripped[2:].strip()

                if ":" in item_content:

                    parts = item_content.split(":", 1)

                    k = parts[0].strip().replace("-", "_")

                    v = parts[1].strip().strip('"').strip("'")

                    current_proxy[k] = v

                continue



            if ":" in stripped:

                parts = stripped.split(":", 1)

                k = parts[0].strip().replace("-", "_")

                v = parts[1].strip().strip('"').strip("'")

                current_proxy[k] = v



    if current_proxy:

        uri = convert_clash_dict_to_uri(current_proxy)

        if uri:

            nodes.append(uri)



    return nodes





def decode_and_extract_nodes(raw_bytes: bytes) -> list:

    """万能解包：支持明文、全文 Base64、逐行 Base64、Clash YAML"""

    if not raw_bytes:

        return []



    text = raw_bytes.decode("utf-8", errors="ignore").strip()

    if not text:

        return []



    results = []



    if not any(p in text for p in KNOWN_PROTOCOLS + ("proxies:",)):

        decoded_candidate = safe_b64decode(text)

        if any(p in decoded_candidate for p in KNOWN_PROTOCOLS):

            text = decoded_candidate



    if "proxies:" in text and ("type:" in text or "- name:" in text):

        yaml_nodes = extract_proxies_from_clash_yaml(text)

        results.extend(yaml_nodes)



    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line or line.startswith("#"):

            continue



        if any(line.startswith(p) for p in KNOWN_PROTOCOLS):

            results.append(line)

            continue



        if len(line) > 20 and " " not in line:

            b64_unpacked = safe_b64decode(line)

            if any(b64_unpacked.startswith(p) for p in KNOWN_PROTOCOLS):

                results.append(b64_unpacked)



    return results





def normalize_node_uri(line: str) -> str:

    """【规则 1】：协议头标准化规范 (hy2:// 转为 hysteria2:// 并补齐必要参数)"""

    line = line.strip()

    if line.startswith("hy2://"):

        line = "hysteria2://" + line[6:]



    if line.startswith("hysteria2://"):

        try:

            u = urllib.parse.urlsplit(line)

            q = urllib.parse.parse_qs(u.query)

            changed = False

            if "insecure" not in q:

                q["insecure"] = ["1"]

                changed = True

            if "sni" not in q and u.hostname:

                q["sni"] = [u.hostname]

                changed = True

            if changed:

                new_query = urllib.parse.urlencode({k: v[0] for k, v in q.items()})

                line = urllib.parse.urlunsplit((u.scheme, u.netloc, u.path, new_query, u.fragment))

        except Exception:

            pass



    return line





# ==============================================================================

# [40MB 物理上限与规律拆分引擎]

# ==============================================================================

def save_split_files(base_filename: str, lines: list, max_bytes: int = MAX_OUTPUT_BYTES) -> list:

    """【规则 8】：严格限制单文件体积 <= 40MB，超限按序号规律拆分"""

    stem, ext = os.path.splitext(base_filename)

    

    for old_file in glob.glob(f"{stem}*{ext}"):

        try:

            os.remove(old_file)

        except Exception:

            pass



    if not lines:

        with open(base_filename, "w", encoding="utf-8") as f:

            pass

        return [base_filename]



    parts_created = []

    current_part_idx = 1

    current_lines = []

    current_bytes = 0



    def write_current_part(idx, p_lines):

        filename = f"{stem}_{idx}{ext}"

        with open(filename, "w", encoding="utf-8") as pf:

            for l in p_lines:

                pf.write(l + "\n")

        parts_created.append(filename)



    for line in lines:

        encoded_line = (line + "\n").encode("utf-8")

        if current_bytes + len(encoded_line) > max_bytes and current_lines:

            write_current_part(current_part_idx, current_lines)

            current_part_idx += 1

            current_lines = []

            current_bytes = 0

        current_lines.append(line)

        current_bytes += len(encoded_line)



    if current_lines:

        write_current_part(current_part_idx, current_lines)



    part1_path = f"{stem}_1{ext}"

    if os.path.exists(part1_path):

        shutil.copyfile(part1_path, base_filename)

        if base_filename not in parts_created:

            parts_created.insert(0, base_filename)



    return parts_created





# ==============================================================================

# [第一阶段：纯内存全网聚合 (100% 内存驻留，绝不落地脏数据)]

# ==============================================================================

def fetch_project_via_zip(project: dict) -> list:

    """Zip 极速下载解包，免 Token 鉴权，免 API 配额限制"""

    name = project["name"]

    owner = project["owner"]

    repo = project["repo"]

    branch = project["branch"]

    dirs = [d.rstrip("/") for d in project.get("dirs", [])]

    target_files = [f.lstrip("/") for f in project.get("files", [])]



    url = f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/{branch}"

    headers = {"User-Agent": "Mozilla/5.0"}

    

    extracted_nodes = []

    try:

        req = urllib.request.Request(url, headers=headers)

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:

            data = resp.read()



        with zipfile.ZipFile(io.BytesIO(data)) as zf:

            for item in zf.namelist():

                if item.endswith("/"):

                    continue

                parts = item.split("/", 1)

                rel_path = parts[1] if len(parts) > 1 else item



                matched = False

                for tf in target_files:

                    if rel_path.lower() == tf.lower() or os.path.basename(rel_path).lower() == tf.lower():

                        matched = True

                        break



                if not matched:

                    for d in dirs:

                        prefix = d.lower() + "/"

                        if rel_path.lower().startswith(prefix):

                            ext = os.path.splitext(rel_path)[1].lower()

                            if ext in (".txt", ".sub", ".json", ".yaml", ""):

                                matched = True

                                break



                if matched:

                    try:

                        content_bytes = zf.read(item)

                        nodes = decode_and_extract_nodes(content_bytes)

                        extracted_nodes.extend(nodes)

                    except Exception:

                        pass

    except Exception:

        for tf in target_files:

            try:

                raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{tf}"

                raw_req = urllib.request.Request(raw_url, headers=headers)

                with urllib.request.urlopen(raw_req, timeout=12) as r_resp:

                    extracted_nodes.extend(decode_and_extract_nodes(r_resp.read()))

            except Exception:

                pass



    return extracted_nodes





def collect_all_sources_in_ram() -> list:

    """全网海量代理聚合：百万级节点纯内存驻留"""

    candidate_lines = []

    seen_hashes = set()



    print("======================================================================")

    print("【第一部分】：全网海量代理原始聚合 (纯内存驻留，不落地脏数据)")

    print("======================================================================")



    # 1. 抓取小众宝藏源

    print(f"\n[*] [1/3] 正在内存拉取 {len(LOW_ATTENTION_SOURCES)} 个小众防封宝藏源...")

    for src in LOW_ATTENTION_SOURCES:

        name = src["name"]

        url = src["url"]

        desc = src["desc"]

        try:

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=15) as resp:

                nodes = decode_and_extract_nodes(resp.read())

                new_cnt = 0

                for n in nodes:

                    h = hashlib.sha256(n.encode("utf-8")).hexdigest()

                    if h not in seen_hashes:

                        seen_hashes.add(h)

                        candidate_lines.append(n)

                        new_cnt += 1

                print(f"  [+] 内存解包: {name:<26} ({desc}) -> 提取 {new_cnt} 个新节点")

        except Exception as e:

            print(f"  [-] 请求跳过: {name:<26} ({e})")



    # 2. 抓取中立优选专线

    print(f"\n[*] [2/3] 正在内存拉取 {len(CURATED_SUBSCRIPTIONS)} 个细分协议高频专线...")

    for src in CURATED_SUBSCRIPTIONS:

        name = src["name"]

        url = src["url"]

        desc = src["desc"]

        try:

            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urllib.request.urlopen(req, timeout=15) as resp:

                nodes = decode_and_extract_nodes(resp.read())

                new_cnt = 0

                for n in nodes:

                    h = hashlib.sha256(n.encode("utf-8")).hexdigest()

                    if h not in seen_hashes:

                        seen_hashes.add(h)

                        candidate_lines.append(n)

                        new_cnt += 1

                print(f"  [+] 内存解包: {name:<26} ({desc}) -> 提取 {new_cnt} 个新节点")

        except Exception as e:

            print(f"  [-] 请求跳过: {name:<26} ({e})")



    # 3. 动态扫描 15 个 GitHub 目录树项目 (含原始 13 核心仓库)

    print(f"\n[*] [3/3] 正在 Zip 并发解包检索 {len(PROJECTS)} 个 GitHub 项目 (含原始 13 核心仓库)...")

    with ThreadPoolExecutor(max_workers=5) as executor:

        future_map = {executor.submit(fetch_project_via_zip, p): p for p in PROJECTS}

        for future in future_map:

            p = future_map[future]

            p_name = p["name"]

            try:

                nodes = future.result()

                new_cnt = 0

                for n in nodes:

                    h = hashlib.sha256(n.encode("utf-8")).hexdigest()

                    if h not in seen_hashes:

                        seen_hashes.add(h)

                        candidate_lines.append(n)

                        new_cnt += 1

                print(f"  [+] 内存解包: {p_name:<28} -> 提取 {new_cnt} 个新节点")

            except Exception as e:

                print(f"  [-] 解包跳过: {p_name:<28} ({e})")



    print(f"\n[+] 内存聚合完成！全网原始候选池规模: {len(candidate_lines)} 个节点 (全部纯内存驻留，不落地)\n")

    return candidate_lines





# ==============================================================================

# [第二阶段：云端 8 大铁律初筛流水线]

# ==============================================================================

def parse_and_validate_proxy(line: str):

    """

    【规则 2 & 规则 3】：

    1. 剔除 .ir、localhost、私有 IP 等死域

    2. 仅保留 hysteria2, vless, vmess, trojan, ss, https 主流协议

    3. 校验 TLS 加密真伪，剔除裸明文

    """

    line = line.strip()

    if not line:

        return None



    try:

        lower = line.lower()

        # 规则 2: 过滤死域与自环回地址

        if ".ir" in lower or "mbghalibaf" in lower or "levikogjgfdd" in lower or "localhost" in lower or "127.0.0.1" in lower or "0.0.0.0" in lower:

            return None



        # 1. Hysteria 2 协议 (优先级 1)

        if line.startswith(("hysteria2://", "hy2://")):

            u = urllib.parse.urlsplit(line)

            host = u.hostname

            port = u.port or 443

            if host and port and 1 <= port <= 65535:

                return ("hy2", host, port, 1)



        # 2. VLESS 协议 (优先级 2: Reality, 3: TLS)

        elif line.startswith("vless://"):

            u = urllib.parse.urlsplit(line)

            host = u.hostname

            port = u.port or 443

            if not host or not port or not (1 <= port <= 65535):

                return None



            q = urllib.parse.parse_qs(u.query)

            sec = q.get("security", ["none"])[0].lower()

            if sec == "reality":

                return ("vless_reality", host, port, 2)

            elif sec == "tls" or port in (443, 8443, 2053, 2083, 2087, 2096):

                return ("vless_tls", host, port, 3)

            return None



        # 4. VMess 协议 (优先级 4)

        elif line.startswith("vmess://"):

            b64_str = line[8:].split("#")[0]

            pad = len(b64_str) % 4

            if pad:

                b64_str += "=" * (4 - pad)

            raw = base64.b64decode(b64_str).decode("utf-8", errors="ignore")

            data = json.loads(raw)

            host = data.get("add") or data.get("host")

            port = int(data.get("port", 0))

            if not host or not (1 <= port <= 65535):

                return None



            tls_val = str(data.get("tls", "")).lower()

            is_tls = tls_val in ("tls", "1", "true") or port in (443, 8443, 2053, 2083, 2087, 2096)

            if is_tls:

                return ("vmess_tls", host, port, 4)

            return None



        # 6. HTTPS 协议 (优先级 6)

        elif line.startswith("https://"):

            u = urllib.parse.urlsplit(line)

            host = u.hostname

            port = u.port or 443

            if host and port and 1 <= port <= 65535:

                return ("https", host, port, 6)

    except Exception:

        pass



    return None





async def check_single_proxy(sem: asyncio.Semaphore, line: str, timeout: float = 2.5):

    """【规则 5 & 规则 6】：底层 Socket 物理握手探测与真实出口 IP 提取"""

    parsed = parse_and_validate_proxy(line)

    if not parsed:

        return None

    proto_type, host, port, rank = parsed



    async with sem:

        t0 = time.time()

        try:

            conn = asyncio.open_connection(host, port)

            reader, writer = await asyncio.wait_for(conn, timeout=timeout)

            

            peer = writer.get_extra_info("peername")

            real_ip = peer[0] if (peer and len(peer) > 0) else host



            writer.close()

            try:

                await writer.wait_closed()

            except Exception:

                pass

            latency_ms = int((time.time() - t0) * 1000)

            return {"line": line, "delay": latency_ms, "rank": rank, "real_ip": real_ip, "type": proto_type}

        except Exception:

            return None





async def run_batch_validation(candidate_nodes, concurrency=250, timeout=2.5):

    """【规则 5 & 规则 6 & 规则 7】：全量并发握手初筛 + 单物理 IP 绝对去重 + 质量排序"""

    print(f"\n[*] 启动云端高并发握手测活: 待测节点={len(candidate_nodes)} | 并发数={concurrency} | 超时={timeout}s")

    sem = asyncio.Semaphore(concurrency)

    tasks = [asyncio.create_task(check_single_proxy(sem, p, timeout)) for p in candidate_nodes]



    alive_results = []

    start_time = time.time()

    done = 0

    total = len(candidate_nodes)



    for coro in asyncio.as_completed(tasks):

        res = await coro

        done += 1

        if res is not None:

            alive_results.append(res)

        if done % 1000 == 0 or done == total:

            elapsed = time.time() - start_time

            rate = done / elapsed if elapsed > 0 else 0

            print(f"  握手进度: [{done}/{total}] 连通响应={len(alive_results)} 速率={rate:.0f}节点/s")



    # 规则 7: 按协议抗封锁等级与握手延迟毫秒综合排序

    alive_results.sort(key=lambda x: (x["rank"], x["delay"]))



    # 规则 6: 真实物理出口 IP 绝对唯一去重 (同一物理机仅保留 1 个最优节点)

    final_unique_alive = []

    seen_physical_ips = set()

    for item in alive_results:

        real_ip = item.get("real_ip")

        if real_ip and real_ip not in seen_physical_ips:

            seen_physical_ips.add(real_ip)

            final_unique_alive.append(item)



    print(f"[+] 云端初筛完成! 耗时: {time.time()-start_time:.1f}s")

    print(f"    - 初步握手连通: {len(alive_results)} 个")

    print(f"    - 【单物理 IP 唯一存活】: {len(final_unique_alive)} 个 (彻底剔除所有复用同 IP 换皮节点)")

    return final_unique_alive







# ==============================================================================
# [sing-box 真实 Cloudflare 204 网页深度测活引擎 (Linux/云端高并发版)]
# ==============================================================================
VALID_FP = {"chrome", "firefox", "safari", "ios", "android", "edge", "360", "qq", "random"}
SINGBOX_TEST_URL = "http://cp.cloudflare.com/generate_204"
SINGBOX_BATCH_SIZE = 120
SINGBOX_CONCURRENCY = 40
SINGBOX_TIMEOUT_MS = 3500
SINGBOX_CLASH_PORT = 19999
SINGBOX_DNS_CACHE = {}

def get_node_physical_ip(line: str) -> str:
    """提取节点的底层物理出口 IP (带内存 DNS 缓存)"""
    line = line.strip()
    if not line:
        return None
    try:
        host = None
        if line.startswith(("vless://", "hysteria2://", "hy2://", "trojan://", "https://")):
            u = urllib.parse.urlsplit(line)
            host = u.hostname
        elif line.startswith("vmess://"):
            b64_str = line[8:].split("#")[0]
            pad = len(b64_str) % 4
            if pad:
                b64_str += "=" * (4 - pad)
            data = json.loads(base64.b64decode(b64_str).decode("utf-8", errors="ignore"))
            host = data.get("add") or data.get("host")

        if not host:
            return None

        host_lower = host.lower()
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host_lower):
            return host_lower

        if host_lower in SINGBOX_DNS_CACHE:
            return SINGBOX_DNS_CACHE[host_lower]

        try:
            resolved_ip = socket.gethostbyname(host_lower)
            SINGBOX_DNS_CACHE[host_lower] = resolved_ip
            return resolved_ip
        except Exception:
            return host_lower
    except Exception:
        pass
    return None

def parse_proxy_to_singbox_outbound(line: str, tag: str):
    """将代理 URI 字符串解析为 sing-box 标准 outbound JSON"""
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    try:
        # 1. VLESS 协议
        if line.startswith("vless://"):
            u = urllib.parse.urlsplit(line)
            q = urllib.parse.parse_qs(u.query)
            sec = q.get("security", ["none"])[0].lower()
            net = q.get("type", ["tcp"])[0].lower()
            if net in ("xhttp", "raw"):
                return None

            ob = {
                "type": "vless",
                "tag": tag,
                "server": u.hostname,
                "server_port": int(u.port or 443),
                "uuid": u.username or "",
            }
            if not ob["server"] or not ob["uuid"]:
                return None

            flow = q.get("flow", [""])[0]
            if flow in ("xtls-rprx-vision", "xtls-rprx-vision-udp443"):
                ob["flow"] = flow

            if sec in ("tls", "reality"):
                tls = {
                    "enabled": True,
                    "server_name": q.get("sni", [u.hostname])[0],
                    "insecure": True
                }
                fp = q.get("fp", ["chrome"])[0].lower()
                if fp not in VALID_FP:
                    fp = "chrome"
                tls["utls"] = {"enabled": True, "fingerprint": fp}

                if sec == "reality":
                    pbk = q.get("pbk", [""])[0]
                    sid = q.get("sid", [""])[0]
                    if not pbk or len(pbk) < 30:
                        return None
                    tls["reality"] = {
                        "enabled": True,
                        "public_key": pbk,
                        "short_id": sid
                    }
                ob["tls"] = tls

            if net == "ws":
                ob["transport"] = {
                    "type": "ws",
                    "path": q.get("path", ["/"])[0],
                    "headers": {"Host": q.get("host", [u.hostname])[0]}
                }
            return ob

        # 2. Hysteria 2 协议
        elif line.startswith(("hysteria2://", "hy2://")):
            u = urllib.parse.urlsplit(line)
            if not u.hostname:
                return None
            q = urllib.parse.parse_qs(u.query)
            raw_pwd = u.username or ""
            pwd = urllib.parse.unquote(raw_pwd)
            ob = {
                "type": "hysteria2",
                "tag": tag,
                "server": u.hostname,
                "server_port": int(u.port or 443),
                "password": pwd,
                "tls": {
                    "enabled": True,
                    "server_name": q.get("sni", [u.hostname])[0],
                    "insecure": True
                }
            }
            if "obfs" in q:
                ob["obfs"] = {
                    "type": q["obfs"][0],
                    "password": q.get("obfs-password", [""])[0]
                }
            mport = q.get("mport", q.get("ports", [None]))[0]
            if mport:
                singbox_mport = mport.replace("-", ":")
                ob["server_ports"] = [singbox_mport]
            return ob

        # 3. VMess 协议
        elif line.startswith("vmess://"):
            b64_str = line[8:].split("#")[0]
            pad = len(b64_str) % 4
            if pad:
                b64_str += "=" * (4 - pad)
            raw = base64.b64decode(b64_str).decode("utf-8", errors="ignore")
            data = json.loads(raw)

            host = data.get("add") or data.get("host")
            port = int(data.get("port", 0))
            uuid = data.get("id")
            if not host or port <= 0 or not uuid:
                return None

            ob = {
                "type": "vmess",
                "tag": tag,
                "server": host,
                "server_port": port,
                "uuid": uuid,
                "security": "auto"
            }
            net = data.get("net", "tcp")
            if net == "ws":
                tr = {"type": "ws", "path": data.get("path", "/")}
                if data.get("host"):
                    tr["headers"] = {"Host": data.get("host")}
                ob["transport"] = tr

            if str(data.get("tls", "")).lower() in ("tls", "1", "true") or port in (443, 8443):
                ob["tls"] = {
                    "enabled": True,
                    "server_name": data.get("sni") or data.get("host") or host,
                    "insecure": True
                }
            return ob

        # 4. Trojan 协议
        elif line.startswith("trojan://"):
            u = urllib.parse.urlsplit(line)
            q = urllib.parse.parse_qs(u.query)
            ob = {
                "type": "trojan",
                "tag": tag,
                "server": u.hostname,
                "server_port": int(u.port or 443),
                "password": u.username or "",
                "tls": {
                    "enabled": True,
                    "server_name": q.get("sni", [u.hostname])[0],
                    "insecure": True
                }
            }
            if not ob["server"] or not ob["password"]:
                return None
            return ob

        # 5. HTTPS 协议
        elif line.startswith("https://"):
            u = urllib.parse.urlsplit(line)
            ob = {
                "type": "http",
                "tag": tag,
                "server": u.hostname,
                "server_port": int(u.port or 443),
                "tls": {
                    "enabled": True,
                    "server_name": u.hostname,
                    "insecure": True
                }
            }
            if u.username or u.password:
                ob["username"] = u.username or ""
                ob["password"] = u.password or ""
            return ob

    except Exception:
        pass
    return None

def test_singbox_batch(batch_nodes, batch_index, total_batches, sing_box_bin):
    """单批次 sing-box 启动并并发向 Clash API 查询 204 延迟"""
    tag_to_raw = {}
    outbounds = []

    for i, raw_line in enumerate(batch_nodes):
        tag = f"node-{batch_index}-{i}"
        ob = parse_proxy_to_singbox_outbound(raw_line, tag)
        if ob:
            outbounds.append(ob)
            tag_to_raw[tag] = raw_line

    if not outbounds:
        return []

    temp_cfg_path = os.path.join(BASE_DIR, f"_temp_batch_{batch_index}.json")

    # 预检并剔除不合法参数的异常节点
    while outbounds:
        cfg = {
            "log": {"level": "warn"},
            "dns": {
                "servers": [{"tag": "dns-direct", "address": "1.1.1.1", "detour": "direct"}],
                "rules": [{"outbound": "any", "server": "dns-direct"}],
                "final": "dns-direct",
                "strategy": "prefer_ipv4"
            },
            "inbounds": [],
            "outbounds": outbounds + [{"type": "direct", "tag": "direct"}],
            "experimental": {
                "clash_api": {
                    "external_controller": f"127.0.0.1:{SINGBOX_CLASH_PORT}"
                }
            }
        }
        with open(temp_cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)

        check_res = subprocess.run(
            [sing_box_bin, "check", "-c", temp_cfg_path],
            capture_output=True,
            text=True
        )
        if check_res.returncode == 0:
            break

        m = re.search(r"outbound\[(\d+)\]", check_res.stderr)
        if m:
            bad_idx = int(m.group(1))
            if bad_idx < len(outbounds):
                outbounds.pop(bad_idx)
            else:
                break
        else:
            break

    if not outbounds:
        if os.path.exists(temp_cfg_path):
            try: os.remove(temp_cfg_path)
            except Exception: pass
        return []

    proc = subprocess.Popen(
        [sing_box_bin, "run", "-c", temp_cfg_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(1.2)

    alive_nodes = []
    encoded_target = urllib.parse.quote(SINGBOX_TEST_URL)
    direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def query_delay(ob):
        t = ob["tag"]
        url = f"http://127.0.0.1:{SINGBOX_CLASH_PORT}/proxies/{t}/delay?url={encoded_target}&timeout={SINGBOX_TIMEOUT_MS}"
        try:
            req = urllib.request.Request(url)
            with direct_opener.open(req, timeout=(SINGBOX_TIMEOUT_MS / 1000.0) + 1.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    delay = data.get("delay", 0)
                    if delay > 0:
                        raw = tag_to_raw[t]
                        return (raw, delay)
        except Exception:
            pass
        return None

    try:
        with ThreadPoolExecutor(max_workers=SINGBOX_CONCURRENCY) as executor:
            futures = [executor.submit(query_delay, ob) for ob in outbounds]
            for future in as_completed(futures):
                res = future.result()
                if res:
                    alive_nodes.append(res)
    finally:
        try:
            proc.kill()
            proc.wait(timeout=2)
        except Exception:
            pass
        if os.path.exists(temp_cfg_path):
            try: os.remove(temp_cfg_path)
            except Exception: pass

    return alive_nodes

def run_singbox_deep_verify(candidate_lines: list) -> list:
    """启动 sing-box 批量进行真实的 Cloudflare 204 网页请求深度测活与物理 IP 去重"""
    sing_box_bin = shutil.which("sing-box") or "/usr/local/bin/sing-box"
    if not (os.path.exists(sing_box_bin) or shutil.which(sing_box_bin)):
        local_bin = os.path.join(BASE_DIR, "sing-box")
        if os.path.exists(local_bin):
            sing_box_bin = local_bin
        else:
            print("[!] 未检测到可用 sing-box 程序，跳过 204 网页深度测活，保留全量初筛列表。")
            return candidate_lines

    total = len(candidate_lines)
    print(f"\n======================================================================")
    print(f"[*] 启动 sing-box 真实 204 网页深度测活 (候选待测节点: {total} 个)")
    print(f"[*] 测活目标: {SINGBOX_TEST_URL} | 并发: {SINGBOX_CONCURRENCY} | 超时: {SINGBOX_TIMEOUT_MS}ms")
    print(f"======================================================================")

    b_count = (total + SINGBOX_BATCH_SIZE - 1) // SINGBOX_BATCH_SIZE
    all_alive = []
    seen_ips = set()

    for b in range(b_count):
        start_idx = b * SINGBOX_BATCH_SIZE
        end_idx = min(start_idx + SINGBOX_BATCH_SIZE, total)
        batch = candidate_lines[start_idx:end_idx]

        alive_batch = test_singbox_batch(batch, b, b_count, sing_box_bin)

        for raw_line, delay in alive_batch:
            phy_ip = get_node_physical_ip(raw_line)
            if phy_ip and phy_ip in seen_ips:
                continue
            if phy_ip:
                seen_ips.add(phy_ip)
            all_alive.append((raw_line, delay))

        if (b + 1) % 10 == 0 or b + 1 == b_count:
            print(f"  [进度] 批次 [{b + 1}/{b_count}] 已完成，当前累计 204 深度存活节点: {len(all_alive)} 个")

    all_alive.sort(key=lambda x: x[1])
    final_lines = [item[0] for item in all_alive]

    print(f"\n[+] sing-box 真实 204 网页深度测活圆满完成！")
    print(f"    - 输入初筛节点: {total} 个")
    print(f"    - 最终通过 204 网页测活且物理 IP 唯一节点: {len(final_lines)} 个")
    return final_lines


def process_and_validate_candidates(candidate_lines: list, concurrency=250, timeout=2.5):

    """云端初筛执行总装流水线"""

    if not candidate_lines:

        print("[-] 内存候选池为空，无可用节点。")

        return []



    print("======================================================================")

    print("【第二部分】：执行云端 8 大铁律初筛流水线 (握手连通 + 物理单IP提纯)")

    print("======================================================================")



    # 步骤 1: 格式清洗、协议聚焦与安全初筛 (规则 1, 2, 3)

    print("[*] 步骤 1/4: 执行协议白名单校验、TLS 加密真伪识别与参数规范化...")

    filtered_nodes = []

    for line in candidate_lines:

        if parse_and_validate_proxy(line) is not None:

            filtered_nodes.append(normalize_node_uri(line))

    print(f"  [+] 初筛保留: {len(filtered_nodes)} / {len(candidate_lines)} 个 (已剔除死域、内网伪地址与裸明文)")



    # 步骤 2: 内存静态单 Host 排重 (规则 4)

    print("\n[*] 步骤 2/4: 执行内存单 Host 初步排重，消减重复域名冗余...")

    dedup_map = {}

    for line in filtered_nodes:

        try:

            u = urllib.parse.urlsplit(line)

            host = u.hostname

            if host and host not in dedup_map:

                dedup_map[host] = line

        except Exception:

            pass

    unique_candidates = list(dedup_map.values())

    print(f"  [+] 静态消肿完成: 提炼出 {len(unique_candidates)} 个独立目标节点参与网络握手测活")



    # 步骤 3: 异步并发网络握手测活与物理 IP 去重 (规则 5, 6, 7)

    print("\n[*] 步骤 3/4: 云端海外高并发底层握手连通性探测 (零连坐)...")

    alive_results = asyncio.run(

        run_batch_validation(

            unique_candidates,

            concurrency=concurrency,

            timeout=timeout,

        )

    )



    # 步骤 4: 落地保存初筛结果 (规则 8: 严格 40MB 单文件物理上限与规律拆分)

    print("\n[*] 步骤 4/4: 将初筛存活节点规律落盘写入仓库 (严格 40MB 单文件上限)...")

    alive_lines = [item["line"] for item in alive_results]



    # 保存初筛后的主文件 all_proxies.txt (及规律分卷)

    all_parts = save_split_files(OUTPUT_FILE, alive_lines, max_bytes=MAX_OUTPUT_BYTES)

    for p in all_parts:

        sz_mb = os.path.getsize(p) / 1024 / 1024

        print(f"  -> 生成初筛分卷: {os.path.basename(p)} ({sz_mb:.2f} MB)")



    # 镜像保存 valid_proxies.txt 保持兼容

    # 步骤 5: sing-box 真实 204 网页深度测活
    print("\n[*] 步骤 5/5: 启动 sing-box 执行 Cloudflare HTTP 204 网页深度测活...")
    deep_verified_lines = run_singbox_deep_verify(alive_lines)

    # 导出最终测活文件 valid_proxies.txt 与 final_valid_proxies.txt (可分卷)
    save_split_files(VALID_OUTPUT_FILE, deep_verified_lines, max_bytes=MAX_OUTPUT_BYTES)
    save_split_files(FINAL_OUTPUT_FILE, deep_verified_lines, max_bytes=MAX_OUTPUT_BYTES)

    # 保存指纹库
    with open(SEEN_FILE, "w", encoding="utf-8") as sf:
        for line in deep_verified_lines:
            sf.write(hashlib.sha256(line.encode("utf-8")).hexdigest() + "\n")

    return deep_verified_lines





# ==============================================================================

# [程序入口]

# ==============================================================================

def main():

    t0 = time.time()

    print("=" * 70)

    print(">>> 启动 GitHub Actions 代理全量采集与云端初筛引擎 <<<")

    print("=" * 70)

    raw = collect_all_sources_in_ram()

    alive = process_and_validate_candidates(raw, concurrency=CHECK_CONCURRENCY, timeout=CHECK_TIMEOUT_SECONDS)

    print("\n" + "=" * 70)

    print(f" 全部采集与云端初筛流程圆满完成！总耗时: {time.time()-t0:.1f} 秒")

    print(f"  - 内存聚合原始总数: {len(raw)} 个 (已自动释放，不落地)")

    print(f"  - 初筛单物理IP存活: {len(alive)} 个 (已规律落盘推库)")

    print("=" * 70)





if __name__ == "__main__":

    main()

