from __future__ import annotations

import html
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from deal_finder_ai.models import Listing


USER_AGENT = "deal-finder-ai/0.1 (+https://github.com/tiablairodeneal/deal-finder-ai)"
REQUEST_TIMEOUT_SECONDS = 20


@dataclass(frozen=True)
class CollectorResult:
    source: str
    listings: list[Listing]
    mode: str
    note: str


class LiveCollectionError(RuntimeError):
    pass


def collect_live_marketplace_listings(max_per_source: int = 10) -> list[CollectorResult]:
    return [
        _collect_acquisitions_direct(max_per_source),
        _collect_app_business_brokers(max_per_source),
        CollectorResult(
            source="Axial",
            listings=[],
            mode="skipped_login_gated",
            note="Axial requires a member login; the job does not automate login-gated pages.",
        ),
        _collect_bizbuysell(max_per_source),
        _collect_bizquest(max_per_source),
        _collect_firstchoice(max_per_source),
        _collect_merge(max_per_source),
        _collect_quietlight(max_per_source),
        _collect_website_closers(max_per_source),
    ]


def _collect_acquisitions_direct(max_per_source: int) -> CollectorResult:
    source = "AcquisitionsDirect"
    url = "https://acquisitionsdirect.com/buy-a-business/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    links = _listing_links(page.html, url, "/buy-a-business/")
    links = [link for link in links if _is_detail_path(link, "/buy-a-business/") and link.rstrip("/") != url.rstrip("/")]
    listings: list[Listing] = []
    for link in links[:max_per_source]:
        try:
            detail = _fetch_public_page(link)
        except LiveCollectionError:
            continue
        text = _visible_text(detail.html)
        title = _title_from_html(detail.html) or _title_from_url(link)
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_infer_industry(title + " " + text),
                location=_infer_location(title + " " + text),
                asking_price=_money_after(text, ["asking price", "price"]),
                annual_revenue=_money_after(text, ["revenue", "annual revenue"]),
                cash_flow=_money_after(text, ["sde", "cash flow", "ebitda", "profit"]),
                financing=_financing_note(text),
                seller_financing_offered="seller financing" in text.lower(),
                description=_shorten(text),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Checked public buy page; found {len(listings)} listing detail pages.")


def _collect_app_business_brokers(max_per_source: int) -> CollectorResult:
    source = "AppBusinessBrokers"
    url = "https://www.appbusinessbrokers.com/buy/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    links = [link for link in _listing_links(page.html, url, "/business/") if "appbusinessbrokers.com" in link]
    listings = [_listing_from_detail(source, link, url) for link in links[:max_per_source]]
    listings = [listing for listing in listings if listing is not None]
    return CollectorResult(source, listings, "live_public", f"Checked public buy page; found {len(listings)} listing detail pages.")


def _collect_bizbuysell(max_per_source: int) -> CollectorResult:
    source = "BizBuySell"
    url = "https://www.bizbuysell.com/new-york-businesses-for-sale/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped_blocked", str(error))

    links = _listing_links(page.html, url, "/business-opportunity/")
    listings = [_listing_from_detail(source, link, url) for link in links[:max_per_source]]
    listings = [listing for listing in listings if listing is not None]
    return CollectorResult(source, listings, "live_public", f"Found {len(listings)} listing detail pages.")


def _collect_bizquest(max_per_source: int) -> CollectorResult:
    source = "BizQuest"
    url = "https://www.bizquest.com/new-york-businesses-for-sale/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped_blocked", str(error))

    links = _listing_links(page.html, url, "/business-for-sale/")
    listings = [_listing_from_detail(source, link, url) for link in links[:max_per_source]]
    listings = [listing for listing in listings if listing is not None]
    return CollectorResult(source, listings, "live_public", f"Found {len(listings)} listing detail pages.")


def _collect_firstchoice(max_per_source: int) -> CollectorResult:
    source = "FirstChoice Business Brokers"
    url = "https://businessesforsaleinnewyorkcity.com/businesses-for-sale"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    links = [
        link
        for link in _listing_links(page.html, url, "/businesses-for-sale/")
        if "businessesforsaleinnewyorkcity.com" in link and _is_detail_path(link, "/businesses-for-sale/")
    ]
    listings = [_listing_from_detail(source, link, url) for link in links[:max_per_source]]
    listings = [listing for listing in listings if listing is not None]
    return CollectorResult(source, listings, "live_public", f"Checked public listings page; found {len(listings)} listing detail pages.")


def _collect_merge(max_per_source: int) -> CollectorResult:
    source = "Merge"
    url = "https://gomerge.com/agencies-for-sale/"
    try:
        page = _fetch_public_page(url, delay_seconds=10)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for card in _split_cards(page.html, '<div class="business-post-row'):
        if len(listings) >= max_per_source:
            break
        link = _first_match(card, r'data-link="([^"]+)"') or _first_href(card, "/agencies-for-sale/")
        title = _clean(_first_match(card, r"<h3>(.*?)</h3>"))
        if not link or not title:
            continue
        description = _clean(_first_match(card, r'<div class="business-post-desc">\s*(.*?)\s*</div>'))
        currency = _first_match(card, r"Valuation\s*<span>\s*([A-Z]{3})\s*[\d,]+")
        asking_price = _int_attr(card, "data-valuation") if currency in (None, "USD") else None
        annual_revenue = _int_attr(card, "data-revenue") if currency in (None, "USD") else None
        cash_flow = _int_attr(card, "data-ebitda") if currency in (None, "USD") else None
        text = _visible_text(card)
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_infer_industry(title + " " + description) or "Professional Services",
                location=_infer_location(title + " " + description + " " + text),
                asking_price=asking_price,
                annual_revenue=annual_revenue,
                cash_flow=cash_flow,
                financing=_financing_note(text),
                seller_financing_offered="seller financing available" in text.lower(),
                description=description,
                raw={"collection_mode": "live_public", "currency": currency or "USD", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} listing cards from the public page.")


def _collect_quietlight(max_per_source: int) -> CollectorResult:
    source = "QuietLight"
    url = "https://quietlight.com/listings/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for card in _split_cards(page.html, '<div class="listing-card grid-item'):
        if len(listings) >= max_per_source:
            break
        if "public-listing" not in card:
            continue
        link = _first_href(card, "/listings/")
        title = _clean(_first_match(card, r'<h3 class="listing-card__title[^"]*">(.*?)</h3>'))
        if not link or not title:
            continue
        price = _money_from_fragment(_clean(_first_match(card, r'<div class="listing-card__price">\s*(.*?)\s*</div>')))
        revenue = _int_attr(card, "data-revenue")
        income = _int_attr(card, "data-income")
        category = _clean(_first_match(card, r'<div class="listing-card__category-name">(.*?)</div>'))
        text = _visible_text(card)
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_map_quietlight_category(category, title),
                location=_infer_location(title + " " + text),
                asking_price=price,
                annual_revenue=revenue,
                cash_flow=income,
                financing=_financing_note(text),
                seller_financing_offered="seller financing" in text.lower(),
                description=_shorten(title),
                raw={"collection_mode": "live_public", "category": category, "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} listing cards from the public page.")


def _collect_website_closers(max_per_source: int) -> CollectorResult:
    source = "Website Closers"
    url = "https://www.websiteclosers.com/businesses-for-sale/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for card in _split_cards(page.html, '<div class="post_item">'):
        if len(listings) >= max_per_source:
            break
        title_match = re.search(r'<a class="post_title" href="([^"]+)"[^>]*>(.*?)</a>', card, re.DOTALL)
        if not title_match:
            continue
        link = html.unescape(title_match.group(1))
        title = _clean(title_match.group(2))
        text = _visible_text(card)
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_infer_industry(title + " " + text),
                location=_infer_location(title + " " + text) or "Remote",
                asking_price=_money_after(text, ["asking price"]),
                annual_revenue=_money_after(text, ["gross income", "revenue"]),
                cash_flow=_money_after(text, ["cash flow"]),
                financing=_financing_note(text),
                seller_financing_offered="seller financing" in text.lower(),
                description=_shorten(_clean(_first_match(card, r'<div class="the_content">\s*(.*?)\s*</div>'))),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} listing cards from the public page.")


@dataclass(frozen=True)
class Page:
    url: str
    html: str


def _fetch_public_page(url: str, delay_seconds: int = 0) -> Page:
    if not _robots_allows(url):
        raise LiveCollectionError(f"robots.txt does not allow fetching {url}")
    if delay_seconds:
        time.sleep(delay_seconds)
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
                raise LiveCollectionError(f"unsupported content type for {url}: {content_type}")
            return Page(url=url, html=response.read().decode("utf-8", "ignore"))
    except HTTPError as error:
        raise LiveCollectionError(f"{url} returned HTTP {error.code}") from error
    except URLError as error:
        raise LiveCollectionError(f"{url} could not be fetched: {error.reason}") from error


def _robots_allows(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    try:
        with urlopen(Request(robots_url, headers={"User-Agent": USER_AGENT}), timeout=REQUEST_TIMEOUT_SECONDS) as response:
            robots_text = response.read().decode("utf-8", "ignore")
    except Exception:
        raise LiveCollectionError(f"robots.txt could not be checked for {url}")
    return _robots_text_allows(robots_text, url)


def _robots_text_allows(robots_text: str, url: str) -> bool:
    parsed = urlparse(url)
    target = parsed.path or "/"
    if parsed.query:
        target += "?" + parsed.query
    applicable_rules: list[tuple[str, bool]] = []
    current_agents: list[str] = []

    for raw_line in robots_text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            current_agents = [value.lower()]
            continue
        if key not in {"allow", "disallow"}:
            continue
        if not any(agent == "*" or agent in USER_AGENT.lower() for agent in current_agents):
            continue
        if value == "":
            continue
        applicable_rules.append((value, key == "allow"))

    matched: tuple[int, bool] | None = None
    for pattern, allowed in applicable_rules:
        normalized = pattern.replace("*", "")
        if target.startswith(normalized):
            length = len(normalized)
            if matched is None or length > matched[0]:
                matched = (length, allowed)
    return matched[1] if matched else True


def _listing_from_detail(source: str, link: str, source_page: str) -> Listing | None:
    try:
        detail = _fetch_public_page(link)
    except LiveCollectionError:
        return None
    text = _visible_text(detail.html)
    title = _title_from_html(detail.html) or _title_from_url(link)
    return Listing(
        title=title,
        source=source,
        listing_url=link,
        industry=_infer_industry(title + " " + text),
        location=_infer_location(title + " " + text),
        asking_price=_money_after(text, ["asking price", "price"]),
        annual_revenue=_money_after(text, ["gross revenue", "annual revenue", "revenue"]),
        cash_flow=_money_after(text, ["cash flow", "sde", "ebitda", "income"]),
        financing=_financing_note(text),
        seller_financing_offered="seller financing" in text.lower(),
        description=_shorten(text),
        raw={"collection_mode": "live_public", "source_page": source_page},
    )


def _listing_links(markup: str, base_url: str, path_fragment: str) -> list[str]:
    links: list[str] = []
    for href in re.findall(r'href=["\']([^"\']+)["\']', markup, re.IGNORECASE):
        link = urljoin(base_url, html.unescape(href))
        if urlparse(link).fragment:
            link = link.split("#", 1)[0]
        if path_fragment in urlparse(link).path and link not in links:
            links.append(link)
    return links


def _is_detail_path(url: str, prefix: str) -> bool:
    path = urlparse(url).path
    if not path.startswith(prefix):
        return False
    slug = path[len(prefix) :].strip("/")
    return bool(slug)


def _split_cards(markup: str, marker: str) -> list[str]:
    return [marker + part for part in markup.split(marker)[1:]]


def _first_href(markup: str, path_fragment: str) -> str | None:
    match = re.search(r'href=["\']([^"\']*' + re.escape(path_fragment) + r'[^"\']*)["\']', markup)
    if not match:
        return None
    return html.unescape(match.group(1))


def _first_match(markup: str, pattern: str) -> str | None:
    match = re.search(pattern, markup, re.IGNORECASE | re.DOTALL)
    return match.group(1) if match else None


def _int_attr(markup: str, attr_name: str) -> int | None:
    value = _first_match(markup, rf'{re.escape(attr_name)}=["\'](\d+)["\']')
    return int(value) if value else None


def _money_after(text: str, labels: list[str]) -> int | None:
    for label in labels:
        match = re.search(rf"{re.escape(label)}\s*:?\s*(?:USD|US)?\s*\$?\s*([\d,]+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1).replace(",", ""))
    return None


def _money_from_fragment(fragment: str | None) -> int | None:
    if not fragment:
        return None
    match = re.search(r"\$ ?([\d,]+)", fragment)
    return int(match.group(1).replace(",", "")) if match else None


def _clean(value: str | None) -> str:
    if not value:
        return ""
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth and data.strip():
            self.parts.append(data.strip())


def _visible_text(markup: str) -> str:
    parser = _TextParser()
    parser.feed(markup)
    return re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts))).strip()


def _title_from_html(markup: str) -> str | None:
    h1 = _clean(_first_match(markup, r"<h1[^>]*>(.*?)</h1>"))
    if h1:
        return h1
    title = _clean(_first_match(markup, r"<title[^>]*>(.*?)</title>"))
    if title:
        return re.sub(r"\s*[|-]\s*(.+)$", "", title).strip()
    return None


def _title_from_url(url: str) -> str:
    slug = urlparse(url).path.strip("/").split("/")[-1]
    return slug.replace("-", " ").title()


def _shorten(text: str, max_length: int = 500) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _infer_location(text: str) -> str | None:
    lowered = text.lower()
    if any(term in lowered for term in ["fully remote", "remote", "online", "relocatable"]):
        return "Remote"
    if any(term in lowered for term in ["new york", "nyc", "richmond county", "nassau county"]):
        return "New York"
    return None


def _infer_industry(text: str) -> str | None:
    lowered = text.lower()
    if any(term in lowered for term in ["digital marketing", "seo", "lead generation", "agency", "business services"]):
        return "Business Services"
    if any(term in lowered for term in ["ecommerce", "e-commerce", "dtc", "amazon", "fba", "shopify"]):
        return "E-Commerce & Digital"
    if any(term in lowered for term in ["wellness", "supplement", "skincare", "pet health"]):
        return "Wellness & Supplements"
    if any(term in lowered for term in ["saas", "software", "app "]):
        return "Technology & Digital"
    if any(term in lowered for term in ["media", "content", "pr ", "public relations"]):
        return "Media & Content"
    if any(term in lowered for term in ["construction", "contractor", "home services"]):
        return "Construction & Building Services"
    return None


def _map_quietlight_category(category: str, title: str) -> str | None:
    lowered = (category + " " + title).lower()
    if "ecommerce" in lowered or "amazon" in lowered:
        return "E-Commerce & Digital"
    if "saas" in lowered:
        return "Technology & Digital"
    if "content" in lowered:
        return "Media & Content"
    if "membership" in lowered:
        return "Training & Education"
    return _infer_industry(lowered)


def _financing_note(text: str) -> str:
    lowered = text.lower()
    if "seller financing" in lowered:
        return "Seller financing mentioned in public listing."
    if "sba pre-qualified" in lowered or "sba pre qualified" in lowered:
        return "SBA pre-qualified; seller financing details unavailable."
    return "Financing details unavailable."
