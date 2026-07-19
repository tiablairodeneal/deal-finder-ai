from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from deal_finder_ai.models import Listing


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "msclkid"}


def normalize_url(url: str | None) -> str | None:
    if not url:
        return None

    parts = urlsplit(url.strip())
    netloc = parts.netloc.lower().removeprefix("www.")
    path = re.sub(r"/+$", "", parts.path)
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in TRACKING_KEYS and not key.startswith(TRACKING_PREFIXES)
    ]
    clean_query = urlencode(sorted(query_pairs))
    return urlunsplit((parts.scheme.lower() or "https", netloc, path, clean_query, ""))


def duplicate_key(listing: Listing) -> str:
    sample_id = listing.raw.get("sample_id")
    if sample_id:
        return f"{listing.source.lower().strip()}:{str(sample_id).lower().strip()}"

    normalized = normalize_url(listing.listing_url)
    if normalized:
        return normalized

    fallback = "|".join(
        [
            listing.source.lower().strip(),
            listing.title.lower().strip(),
            (listing.location or "unavailable").lower().strip(),
            str(listing.asking_price or "unavailable"),
        ]
    )
    return "fingerprint:" + hashlib.sha256(fallback.encode("utf-8")).hexdigest()[:20]


def is_duplicate(listing: Listing, seen_keys: set[str]) -> bool:
    return duplicate_key(listing) in seen_keys
