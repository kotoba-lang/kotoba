"""Shared gov website fetch helpers.

Cloudflare edge proxy use is deliberately opt-in. Direct fetch remains the
first path; proxy fallback is only used when GOV_FETCH_PROXY_URL and
GOV_FETCH_HMAC are configured in the Zeebe worker environment.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import urllib.error as _u_err
import urllib.parse as _u_parse
import urllib.request as _u_req


DEFAULT_USER_AGENT = "GovBot/1.0"


def body_to_hash_text(body: bytes) -> tuple[str, str]:
    content_hash = hashlib.md5(body).hexdigest()
    text = re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace"))
    text = re.sub(r"\s+", " ", text).strip()[:300]
    return content_hash, text


def direct_fetch_hash(url: str, timeout: int = 10, user_agent: str = DEFAULT_USER_AGENT) -> tuple[str, str]:
    if not url or not url.startswith("http"):
        return "", ""
    try:
        req = _u_req.Request(url, headers={"User-Agent": user_agent})
        with _u_req.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
        return body_to_hash_text(body)
    except Exception:
        return "", ""


def _classify_fetch_error(exc: Exception) -> tuple[str, str]:
    message = str(exc).replace("\n", " ")[:300]
    if isinstance(exc, _u_err.HTTPError):
        return f"http_{int(exc.code)}", message
    if isinstance(exc, TimeoutError):
        return "timeout", message
    if isinstance(exc, _u_err.URLError):
        reason = str(getattr(exc, "reason", exc)).lower()
        if "name or service not known" in reason or "nodename nor servname" in reason:
            return "dns_error", message
        if "certificate" in reason or "ssl" in reason:
            return "tls_error", message
        if "timed out" in reason or "timeout" in reason:
            return "timeout", message
        return "url_error", message
    if isinstance(exc, OSError):
        return "os_error", message
    return exc.__class__.__name__, message


def direct_fetch_hash_status(
    url: str,
    timeout: int = 10,
    user_agent: str = DEFAULT_USER_AGENT,
) -> tuple[str, str, str, str]:
    if not url or not url.startswith("http"):
        return "", "", "invalid_url", "URL is empty or not HTTP(S)"
    try:
        req = _u_req.Request(url, headers={"User-Agent": user_agent})
        with _u_req.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
        content_hash, text = body_to_hash_text(body)
        return content_hash, text, "direct_ok", ""
    except Exception as exc:
        status, message = _classify_fetch_error(exc)
        return "", "", f"direct_{status}", message


def proxy_fetch_hash(url: str, timeout: int = 20) -> tuple[str, str]:
    proxy_base = os.environ.get("GOV_FETCH_PROXY_URL", "https://gov-fetch.etzhayyim.com/fetch").strip()
    secret = os.environ.get("GOV_FETCH_HMAC", "").strip()
    if not proxy_base or not secret or not url or not url.startswith("http"):
        return "", ""
    payload = f"GET\n{url}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    sep = "&" if "?" in proxy_base else "?"
    proxy_url = f"{proxy_base}{sep}url={_u_parse.quote(url, safe='')}"
    req = _u_req.Request(
        proxy_url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "etzhayyim-gov-coverage/1.0",
            "X-etzhayyim-Gov-Fetch-Auth": sig,
        },
        method="GET",
    )
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            if int(resp.status) >= 400:
                return "", ""
            body = resp.read(65536)
        return body_to_hash_text(body)
    except (_u_err.HTTPError, _u_err.URLError, TimeoutError, OSError):
        return "", ""


def proxy_fetch_hash_status(url: str, timeout: int = 20) -> tuple[str, str, str, str]:
    proxy_base = os.environ.get("GOV_FETCH_PROXY_URL", "https://gov-fetch.etzhayyim.com/fetch").strip()
    secret = os.environ.get("GOV_FETCH_HMAC", "").strip()
    if not proxy_base or not secret:
        return "", "", "proxy_not_configured", "GOV_FETCH_PROXY_URL or GOV_FETCH_HMAC is empty"
    if not url or not url.startswith("http"):
        return "", "", "invalid_url", "URL is empty or not HTTP(S)"
    payload = f"GET\n{url}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    sep = "&" if "?" in proxy_base else "?"
    proxy_url = f"{proxy_base}{sep}url={_u_parse.quote(url, safe='')}"
    req = _u_req.Request(
        proxy_url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "etzhayyim-gov-coverage/1.0",
            "X-etzhayyim-Gov-Fetch-Auth": sig,
        },
        method="GET",
    )
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            if int(resp.status) >= 400:
                return "", "", f"proxy_http_{int(resp.status)}", f"Proxy returned HTTP {int(resp.status)}"
            body = resp.read(65536)
        content_hash, text = body_to_hash_text(body)
        return content_hash, text, "proxy_ok", ""
    except (_u_err.HTTPError, _u_err.URLError, TimeoutError, OSError) as exc:
        status, message = _classify_fetch_error(exc)
        return "", "", f"proxy_{status}", message


def direct_then_proxy_fetch_hash(url: str, timeout: int = 10) -> tuple[str, str]:
    direct_hash, direct_text = direct_fetch_hash(url, timeout=timeout)
    if direct_hash:
        return direct_hash, direct_text
    return proxy_fetch_hash(url, timeout=max(timeout, 20))


def direct_then_proxy_fetch_hash_status(url: str, timeout: int = 10) -> tuple[str, str, str, str]:
    direct_hash, direct_text, direct_status, direct_error = direct_fetch_hash_status(url, timeout=timeout)
    if direct_hash:
        return direct_hash, direct_text, direct_status, direct_error
    proxy_hash, proxy_text, proxy_status, proxy_error = proxy_fetch_hash_status(url, timeout=max(timeout, 20))
    if proxy_hash:
        return proxy_hash, proxy_text, proxy_status, proxy_error
    return "", "", proxy_status, f"{direct_status}: {direct_error}; {proxy_status}: {proxy_error}"[:500]
