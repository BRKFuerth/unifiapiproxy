import ipaddress
import logging
import re
from typing import Optional, Dict, Any, Tuple

import yaml
import requests
from flask import Flask, request, Response, jsonify

CONFIG_PATH = "config.yaml"

def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

CFG = load_config(CONFIG_PATH)

ALLOWED_IPS = set(CFG["firewall"]["allowed_source_ips"])
EXTERNAL_KEY = CFG["auth"]["external_api_key"]

UNIFI_BASE = CFG["unifi"]["base_url"].rstrip("/")
UNIFI_KEY = CFG["unifi"]["api_key"]
UNIFI_KEY_HEADER = CFG["unifi"].get("api_key_header", "X-API-KEY")
UNIFI_VERIFY_TLS = bool(CFG["unifi"].get("verify_tls", True))
UNIFI_TIMEOUT = float(CFG["unifi"].get("timeout_seconds", 20))

TRUST_PROXY = bool(CFG["server"].get("trust_proxy_headers", False))
REAL_IP_HEADER = (CFG["server"].get("real_ip_header") or "x-forwarded-for").lower()

UNKNOWN_LOG_PATH = CFG.get("logging", {}).get("unknown_paths_log", "unknown_paths.log")

app = Flask(__name__)

logger = logging.getLogger("unifi_api_firewall")
logger.setLevel(logging.INFO)

unknown_logger = logging.getLogger("unifi_unknown_paths")
unknown_logger.setLevel(logging.INFO)
fh = logging.FileHandler(UNKNOWN_LOG_PATH)
fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
unknown_logger.addHandler(fh)

sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(sh)

ALLOWED_RULES: Tuple[Tuple[str, re.Pattern], ...] = (
    ("GET",  re.compile(r"^/proxy/network/integration/v1/sites$")),
    ("GET",  re.compile(r"^/proxy/network/integration/v1/sites/[^/]+/devices$")),
    ("GET",  re.compile(r"^/proxy/network/integration/v1/sites/[^/]+/clients/[^/]+$")),
    ("POST", re.compile(r"^/proxy/network/integration/v1/sites/[^/]+/clients/[^/]+/actions$")),
)

def get_client_ip() -> str:
    if TRUST_PROXY:
        hdr = request.headers.get(REAL_IP_HEADER)
        if hdr:
            return hdr.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"

def is_ip_allowed(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return str(ip) in ALLOWED_IPS

def get_supplied_external_key() -> Optional[str]:
    supplied = request.headers.get("x-api-key") or request.headers.get("authorization")
    if not supplied:
        return None
    if supplied.lower().startswith("bearer "):
        supplied = supplied.split(" ", 1)[1].strip()
    return supplied

def is_allowed_path_and_method(method: str, path: str) -> bool:
    for m, pat in ALLOWED_RULES:
        if m == method and pat.match(path):
            return True
    return False

def filter_incoming_headers() -> Dict[str, str]:
    """
    Welche Header vom Client überhaupt upstream sinnvoll sind:
    - Wir entfernen auth header (external key) und hop-by-hop headers.
    - Wir setzen/überschreiben UniFi API-Key Header.
    """
    hop_by_hop = {
        "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailers", "transfer-encoding", "upgrade"
    }

    out = {}
    for k, v in request.headers.items():
        lk = k.lower()
        if lk in hop_by_hop:
            continue
        if lk in {"x-api-key", "authorization"}:
            continue
        if lk == "content-length":
            continue
        out[k] = v

    out[UNIFI_KEY_HEADER] = UNIFI_KEY
    return out

def forward_to_unifi() -> Response:
    path = request.full_path
    if path.endswith("?"):
        path = path[:-1]

    url = f"{UNIFI_BASE}{path}"
    headers = filter_incoming_headers()

    data = request.get_data()
    resp = requests.request(
        method=request.method,
        url=url,
        headers=headers,
        data=data if data else None,
        params=None,
        timeout=UNIFI_TIMEOUT,
        verify=UNIFI_VERIFY_TLS,
        allow_redirects=False,
    )

    excluded = {"content-encoding", "transfer-encoding", "connection"}
    response_headers = []
    for k, v in resp.headers.items():
        if k.lower() in excluded:
            continue
        response_headers.append((k, v))

    return Response(resp.content, status=resp.status_code, headers=response_headers)

@app.before_request
def firewall_gate():
    ip = get_client_ip()
    if not is_ip_allowed(ip):
        return jsonify({"detail": f"Source IP not allowed: {ip}"}), 403

    supplied = get_supplied_external_key()
    if not supplied:
        return jsonify({"detail": "Missing API key"}), 401
    if supplied != EXTERNAL_KEY:
        return jsonify({"detail": "Invalid API key"}), 403

    if not is_allowed_path_and_method(request.method, request.path):
        unknown_logger.info(
            'ip=%s method=%s path="%s" query="%s" ua="%s"',
            ip,
            request.method,
            request.path,
            request.query_string.decode("utf-8", errors="replace"),
            request.headers.get("user-agent", ""),
        )
        return jsonify({"detail": "Not found"}), 404

@app.get("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/proxy/network/integration/v1/<path:rest>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def proxy_integration(rest: str):
    return forward_to_unifi()

@app.route("/proxy/network/integration/v1/sites", methods=["GET"])
def proxy_sites():
    return forward_to_unifi()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
