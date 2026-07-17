"""Filesystem containment and SSRF-resistant public URL access."""

import ipaddress
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import urllib3

from mafuyu_ai.settings import WORKSPACE_DIR
from mafuyu_ai.tools.policy import BLOCKED_HOSTNAMES


def safe_path(rel_path: str) -> Path:
    """
    指定されたパスを sandboxed workspace 内の絶対パスへ解決する。

    `..` などで workspace の外へ出ようとした場合は例外にする。
    """
    path = Path(rel_path)
    if not path.is_absolute():
        path = WORKSPACE_DIR / rel_path

    resolved = path.resolve()
    workspace_root = WORKSPACE_DIR.resolve()

    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes workspace: {rel_path}") from exc

    return resolved


def resolve_public_url(url: str) -> dict[str, Any]:
    """
    公開URLとして扱ってよいか検証し、接続に必要な情報を返す。

    この段階では DNS を解決して、private / loopback / link-local などの
    内部向けアドレスが混ざっていないことを確認する。
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http:// and https:// URLs are allowed")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")

    host = parsed.hostname.lower()
    if host in BLOCKED_HOSTNAMES or host.endswith(".local"):
        raise ValueError(f"Blocked host: {host}")

    try:
        addrinfo = socket.getaddrinfo(
            host, parsed.port or None, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as exc:
        raise ValueError(f"Failed to resolve host: {host}") from exc

    public_ips = []
    for _, _, _, _, sockaddr in addrinfo:
        ip_text = sockaddr[0]
        ip = ipaddress.ip_address(ip_text)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ValueError(f"Blocked non-public address: {ip_text}")
        if ip_text not in public_ips:
            public_ips.append(ip_text)

    target = parsed.path or "/"
    if parsed.query:
        target += f"?{parsed.query}"

    return {
        "url": url,
        "parsed": parsed,
        "host": host,
        "port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "scheme": parsed.scheme,
        "target": target,
        "resolved_ips": public_ips,
    }


def validate_public_url(url: str) -> str:
    """URL 検証だけを行いたい呼び出し元向けの薄いラッパー。"""
    resolve_public_url(url)
    return url


def fetch_public_response(url: str) -> tuple[str, urllib3.response.BaseHTTPResponse]:
    """
    検証済みの public URL に対して実際に GET を行う。

    重要なのは、`requests.get(url)` のようにホスト名へ再解決しないこと。
    `resolve_public_url()` で得た IP に直接接続し、Host/SNI だけ元ホスト名を使う。
    これで redirect SSRF と DNS rebinding の両方を抑える。
    """
    resolved = resolve_public_url(url)
    headers = {
        "Host": resolved["host"],
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Mafuyu/1.0",
    }

    last_error: Exception | None = None
    for ip_text in resolved["resolved_ips"]:
        try:
            # HTTPS の場合は「接続先IP」と「証明書検証用ホスト名」を分ける。
            if resolved["scheme"] == "https":
                pool = urllib3.HTTPSConnectionPool(
                    host=ip_text,
                    port=resolved["port"],
                    assert_hostname=resolved["host"],
                    server_hostname=resolved["host"],
                )
            else:
                pool = urllib3.HTTPConnectionPool(
                    host=ip_text,
                    port=resolved["port"],
                )

            response = pool.request(
                "GET",
                resolved["target"],
                headers=headers,
                redirect=False,
                preload_content=False,
                timeout=urllib3.Timeout(connect=10.0, read=30.0),
                retries=False,
            )
            # redirect を許すと、検証済みの URL から内部URLへ飛ばされる。
            if 300 <= response.status < 400:
                location = response.headers.get("Location", "")
                raise ValueError(f"HTTP redirects are not allowed: {location}")
            if response.status >= 400:
                raise urllib3.exceptions.HTTPError(f"HTTP {response.status}")
            return resolved["url"], response
        except Exception as exc:
            last_error = exc
            continue

    if last_error is None:
        raise ValueError("No resolved public IPs were available")
    raise last_error


def _reject_oversized_response(
    resp: urllib3.response.BaseHTTPResponse, max_bytes: int
) -> None:
    """Content-Length が明示されている場合は、受信前に大きすぎる応答を拒否する。"""
    content_length = resp.headers.get("Content-Length")
    if not content_length:
        return

    try:
        expected_size = int(content_length)
    except ValueError:
        return

    if expected_size > max_bytes:
        raise ValueError(
            f"Response body too large: {expected_size} bytes (limit: {max_bytes})"
        )


def _read_limited_response_body(
    resp: urllib3.response.BaseHTTPResponse, max_bytes: int
) -> bytes:
    """
    応答本文をストリームで読み、展開後サイズに上限を掛ける。
    gzip などで圧縮された本文も decode_content=True で展開後サイズを数える。
    """
    _reject_oversized_response(resp, max_bytes)

    body = bytearray()
    for chunk in resp.stream(64 * 1024, decode_content=True):
        if not chunk:
            continue

        remaining = max_bytes - len(body)
        if remaining <= 0:
            raise ValueError(f"Response body exceeds {max_bytes} bytes")

        if len(chunk) > remaining:
            body.extend(chunk[:remaining])
            raise ValueError(f"Response body exceeds {max_bytes} bytes")

        body.extend(chunk)

    return bytes(body)
