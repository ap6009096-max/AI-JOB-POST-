from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = "AIJobPostSourceBot/0.1 (+https://github.com; professional-source-analysis)"
TIMEOUT_SECONDS = 10.0
MAX_BODY_BYTES = 512_000
MAX_REDIRECTS = 3

LINKEDIN_HOSTS = {"linkedin.com", "www.linkedin.com", "lnkd.in"}
GITHUB_HTML_HOSTS = {"github.com", "www.github.com"}
GITHUB_API_HOSTS = {"api.github.com", "raw.githubusercontent.com"}

CAPTCHA_MARKERS = (
    "g-recaptcha",
    "h-captcha",
    "cf-challenge",
    "cf-turnstile",
    "captcha",
    "challenge-platform",
)
LOGIN_MARKERS = (
    "sign in to continue",
    "log in to continue",
    "login required",
    "please sign in",
    "please log in",
    "auth0",
    "okta",
)


class FetchSkipped(Exception):
    def __init__(self, fetch_status: str, skip_reason: str) -> None:
        super().__init__(skip_reason)
        self.fetch_status = fetch_status
        self.skip_reason = skip_reason


@dataclass
class FetchResult:
    ok: bool
    url: str = ""
    status_code: int = 0
    body: str = ""
    content_type: str = ""
    fetch_status: str = ""
    skip_reason: str = ""


def is_linkedin_host(host: str | None) -> bool:
    hostname = (host or "").lower().rstrip(".")
    if not hostname:
        return False
    return hostname in LINKEDIN_HOSTS or hostname.endswith(".linkedin.com")


def is_github_host(host: str | None) -> bool:
    hostname = (host or "").lower().rstrip(".")
    return hostname in GITHUB_HTML_HOSTS or hostname.endswith(".github.com")


def is_github_api_host(host: str | None) -> bool:
    hostname = (host or "").lower().rstrip(".")
    return hostname in GITHUB_API_HOSTS


def html_to_text(html: str, *, limit: int = 20_000) -> str:
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    text = "\n".join(extractor.chunks)
    if len(text) > limit:
        return text[:limit]
    return text


def fetch_public(url: str, *, client: httpx.Client | None = None) -> FetchResult:
    try:
        parsed = _require_http_url(url)
        if is_linkedin_host(parsed.hostname):
            raise FetchSkipped("skipped_linkedin_policy", "linkedin_requires_authorized_api")
        _assert_public_host(parsed.hostname)
        if not _robots_allows(parsed, client=client):
            raise FetchSkipped("skipped_robots", "robots_disallow")
        response = _get(str(parsed.geturl()), client=client, check_robots=False)
        return FetchResult(
            ok=True,
            url=str(response.url),
            status_code=response.status_code,
            body=response.text,
            content_type=response.headers.get("content-type", ""),
            fetch_status="ok",
        )
    except FetchSkipped as exc:
        logger.info("source_fetch_skipped status=%s reason=%s", exc.fetch_status, exc.skip_reason)
        return FetchResult(ok=False, url=url, fetch_status=exc.fetch_status, skip_reason=exc.skip_reason)
    except Exception:
        logger.info("source_fetch_failed")
        return FetchResult(ok=False, url=url, fetch_status="failed", skip_reason="fetch_failed")


def github_api_get(url: str, *, token: str | None = None, client: httpx.Client | None = None) -> FetchResult:
    try:
        parsed = _require_http_url(url)
        if not is_github_api_host(parsed.hostname):
            raise FetchSkipped("skipped_invalid_url", "github_api_host_required")
        _assert_public_host(parsed.hostname)
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        response = _get(str(parsed.geturl()), client=client, headers=headers, check_robots=False)
        return FetchResult(
            ok=True,
            url=str(response.url),
            status_code=response.status_code,
            body=response.text,
            content_type=response.headers.get("content-type", ""),
            fetch_status="ok",
        )
    except FetchSkipped as exc:
        logger.info("github_fetch_skipped status=%s reason=%s", exc.fetch_status, exc.skip_reason)
        return FetchResult(ok=False, url=url, fetch_status=exc.fetch_status, skip_reason=exc.skip_reason)
    except Exception:
        logger.info("github_fetch_failed")
        return FetchResult(ok=False, url=url, fetch_status="failed", skip_reason="fetch_failed")


def _require_http_url(url: str):
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FetchSkipped("skipped_invalid_url", "http_https_required")
    return parsed


def _assert_public_host(hostname: str | None) -> None:
    host = (hostname or "").strip().rstrip(".")
    if not host:
        raise FetchSkipped("skipped_invalid_url", "host_required")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        raise FetchSkipped("skipped_invalid_url", "host_unresolved") from None
    if not infos:
        raise FetchSkipped("skipped_invalid_url", "host_unresolved")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_blocked_ip(ip):
            raise FetchSkipped("skipped_ssrf", "private_or_reserved_ip")


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _robots_allows(parsed, *, client: httpx.Client | None) -> bool:
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        response = _get(robots_url, client=client, check_robots=False, allow_missing=True)
    except FetchSkipped as exc:
        if exc.fetch_status == "skipped_private":
            return False
        raise
    if response.status_code == 404:
        return True
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    return bool(parser.can_fetch(USER_AGENT, parsed.geturl()))


def _get(
    url: str,
    *,
    client: httpx.Client | None,
    headers: dict[str, str] | None = None,
    check_robots: bool = True,
    allow_missing: bool = False,
) -> httpx.Response:
    parsed = _require_http_url(url)
    if is_linkedin_host(parsed.hostname):
        raise FetchSkipped("skipped_linkedin_policy", "linkedin_requires_authorized_api")
    _assert_public_host(parsed.hostname)
    if check_robots and not _robots_allows(parsed, client=client):
        raise FetchSkipped("skipped_robots", "robots_disallow")

    request_headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/json;q=0.9,*/*;q=0.8"}
    if headers:
        request_headers.update(headers)

    current = url
    owns_client = client is None
    http = client or httpx.Client(timeout=TIMEOUT_SECONDS, follow_redirects=False)
    try:
        for _ in range(MAX_REDIRECTS + 1):
            parsed_current = _require_http_url(current)
            if is_linkedin_host(parsed_current.hostname):
                raise FetchSkipped("skipped_linkedin_policy", "linkedin_requires_authorized_api")
            _assert_public_host(parsed_current.hostname)
            response = http.get(current, headers=request_headers)
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                if not location:
                    raise FetchSkipped("failed", "redirect_missing_location")
                current = urljoin(current, location)
                continue
            _raise_for_status(response, allow_missing=allow_missing)
            _raise_for_challenge(response)
            body = response.content[: MAX_BODY_BYTES + 1]
            if len(body) > MAX_BODY_BYTES:
                raise FetchSkipped("failed", "body_too_large")
            return response
        raise FetchSkipped("failed", "too_many_redirects")
    finally:
        if owns_client:
            http.close()


def _raise_for_status(response: httpx.Response, *, allow_missing: bool) -> None:
    if response.status_code == 404 and allow_missing:
        return
    if response.status_code in {401, 403, 404}:
        raise FetchSkipped("skipped_private", f"http_{response.status_code}")
    if response.status_code >= 400:
        raise FetchSkipped("failed", f"http_{response.status_code}")


def _raise_for_challenge(response: httpx.Response) -> None:
    if response.headers.get("www-authenticate"):
        raise FetchSkipped("skipped_login", "www_authenticate")
    content_type = (response.headers.get("content-type") or "").lower()
    if "html" not in content_type and "text" not in content_type:
        return
    sample = (response.text or "")[:8000].lower()
    if any(marker in sample for marker in CAPTCHA_MARKERS):
        raise FetchSkipped("skipped_captcha", "captcha_detected")
    if any(marker in sample for marker in LOGIN_MARKERS):
        raise FetchSkipped("skipped_login", "login_wall")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = " ".join(data.split())
        if text:
            self.chunks.append(text)
