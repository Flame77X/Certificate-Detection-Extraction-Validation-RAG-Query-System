"""
External verification (Task 7).

Real check via the Open Badges standard (Credly, Accredible, Badgr and other
badge platforms host machine-readable assertions):
  1. Find verification URLs printed on the certificate.
  2. Fetch only HTTPS URLs on an allowlist of badge platforms (SSRF guard).
  3. Parse the Open Badges 2.0 assertion: revocation, expiry, issuer name.
Anything that cannot be checked this way is returned as Manual Verification
Required, with the URL (if any) for a human reviewer. Nothing is marked
Verified without a successful fetch.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from app.date_validation import normalize_issuer

REQUEST_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 1_000_000
MAX_FETCHES = 4  # assertion -> badge class -> issuer profile (+1 redirect)

# Hosts allowed to be fetched (exact host or subdomain). Badge/credential platforms only.
ALLOWED_HOSTS = (
    'credly.com', 'youracclaim.com', 'accredible.com', 'badgr.com', 'badgr.io',
    'openbadgepassport.com', 'badgecert.com',
)

URL_PATTERN = re.compile(r'https?://[^\s<>"\')\]]+', re.IGNORECASE)
CREDLY_BADGE_PAGE = re.compile(r'^/badges/([0-9a-f-]{36})', re.IGNORECASE)
CREDLY_ASSERTION_API = 'https://api.credly.com/v1/obi/v2/badge_assertions/{}'


class VerificationError(Exception):
    pass


def _host_allowed(url):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    return parsed.scheme == 'https' and any(host == h or host.endswith('.' + h) for h in ALLOWED_HOSTS)


def find_verification_urls(text):
    """Allowlisted HTTPS verification URLs printed on the certificate, in order of appearance."""
    urls = []
    for raw in URL_PATTERN.findall(text or ''):
        url = raw.rstrip('.,;:')
        if url.lower().startswith('http://'):
            url = 'https://' + url[7:]
        if _host_allowed(url) and url not in urls:
            urls.append(url)
    return urls


def to_assertion_url(url):
    """Map human-facing badge pages to their machine-readable assertion endpoint where known."""
    parsed = urlparse(url)
    if (parsed.hostname or '').lower().endswith(('credly.com', 'youracclaim.com')):
        match = CREDLY_BADGE_PAGE.match(parsed.path)
        if match:
            return CREDLY_ASSERTION_API.format(match.group(1))
    return url


def _fetch_json(url, budget):
    """GET an allowlisted URL as JSON with timeout, size cap and allowlist-checked redirects."""
    for _ in range(2):
        if budget[0] <= 0:
            raise VerificationError('Fetch budget exceeded')
        if not _host_allowed(url):
            raise VerificationError(f'Host not allowlisted: {urlparse(url).hostname}')
        budget[0] -= 1
        with requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=False, stream=True,
                          headers={'Accept': 'application/ld+json, application/json'}) as resp:
            if resp.is_redirect and resp.headers.get('Location'):
                url = requests.compat.urljoin(url, resp.headers['Location'])
                continue
            if resp.status_code == 404:
                raise VerificationError('Credential not found on issuer platform')
            if resp.status_code != 200:
                raise VerificationError(f'Issuer platform returned HTTP {resp.status_code}')
            body = resp.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
        if len(body) > MAX_RESPONSE_BYTES:
            raise VerificationError('Response too large')
        try:
            data = requests.models.complexjson.loads(body)
        except ValueError:
            raise VerificationError('Verification URL did not return machine-readable JSON')
        # Some APIs wrap the payload: {"data": {...}}
        return data.get('data', data) if isinstance(data, dict) else data
    raise VerificationError('Too many redirects')


def _resolve(node, budget):
    """Open Badges fields may be embedded objects or URLs to them."""
    if isinstance(node, str) and node.startswith('http'):
        return _fetch_json(node, budget)
    return node if isinstance(node, dict) else {}


def _parse_datetime(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def verify_open_badge(url, expected_issuer):
    """Return a verification result dict for one Open Badges 2.0 assertion URL."""
    budget = [MAX_FETCHES]
    assertion = _fetch_json(to_assertion_url(url), budget)
    if not isinstance(assertion, dict) or 'Assertion' not in str(assertion.get('type', '')):
        raise VerificationError('Not an Open Badges assertion')

    if assertion.get('revoked'):
        return {'status': 'Failed (Revoked)', 'reason': assertion.get('revocationReason') or 'Credential revoked',
                'verification_url': url}

    expires = _parse_datetime(assertion.get('expires')) if assertion.get('expires') else None
    if expires and expires < datetime.now(timezone.utc):
        return {'status': 'Failed (Expired)', 'reason': f'Credential expired {expires.date()}', 'verification_url': url}

    badge = _resolve(assertion.get('badge'), budget)
    issuer = _resolve(badge.get('issuer'), budget)
    platform_issuer = issuer.get('name')
    if not platform_issuer:
        raise VerificationError('Assertion has no issuer name')

    if expected_issuer and normalize_issuer(expected_issuer) not in normalize_issuer(platform_issuer) \
            and normalize_issuer(platform_issuer) not in normalize_issuer(expected_issuer):
        return {'status': 'Failed (Issuer mismatch)',
                'reason': f'Platform lists issuer "{platform_issuer}", certificate says "{expected_issuer}"',
                'verification_url': url}

    return {'status': 'Verified (Open Badges)',
            'reason': f'Active credential "{badge.get("name", "")}" issued by {platform_issuer}',
            'verification_url': url, 'platform_issuer': platform_issuer}


def verify_external_issuer(issuer_name, fields, text_content=''):
    """
    Task 7 entry point. Status contains 'Verified', 'Failed' or 'Manual' (callers match on these).
    """
    if not issuer_name:
        return {"status": "Manual Review Required", "reason": "Issuer name missing"}

    urls = find_verification_urls(text_content)
    if not urls:
        return {"status": "Manual Verification Required",
                "reason": "No supported verification URL on the certificate"}

    errors = []
    for url in urls:
        try:
            return verify_open_badge(url, issuer_name)
        except (VerificationError, requests.RequestException) as e:
            errors.append(f'{url}: {e}')

    return {"status": "Manual Verification Required",
            "reason": "Could not verify automatically: " + '; '.join(errors),
            "verification_url": urls[0]}
