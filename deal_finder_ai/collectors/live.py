from __future__ import annotations

import html
import json
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
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
        _collect_businessbroker(max_per_source),
        _collect_businessesforsale(max_per_source),
        _collect_businessexits(max_per_source),
        _collect_businessmart(max_per_source),
        _collect_firstchoice(max_per_source),
        _collect_link_business(max_per_source),
        _collect_merge(max_per_source),
        _collect_quietlight(max_per_source),
        _collect_smergers(max_per_source),
        _collect_transferslot(max_per_source),
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


def _collect_businessbroker(max_per_source: int) -> CollectorResult:
    source = "BusinessBroker"
    url = "https://www.businessbroker.net/state/new-york-businesses-for-sale.aspx"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for link, text in _anchors_with_text(page.html, url):
        if len(listings) >= max_per_source:
            break
        if "/business-for-sale/" not in urlparse(link).path or "asking price" not in text.lower():
            continue
        listings.append(
            Listing(
                title=_businessbroker_title(text),
                source=source,
                listing_url=link,
                industry=_infer_industry(text),
                location=_infer_location(text),
                asking_price=_money_after(text, ["asking price"]),
                annual_revenue=_money_after(text, ["annual sales", "sales", "revenue"]),
                cash_flow=_money_after(text, ["cash flow", "sde", "ebitda", "owner earnings", "net"]),
                financing=_financing_note(text),
                seller_financing_offered="owner finance" in text.lower() or "seller financing" in text.lower(),
                description=_shorten(text),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} New York listing links from the public page.")


def _collect_businessesforsale(max_per_source: int) -> CollectorResult:
    source = "BusinessesForSale"
    url = "https://us.businessesforsale.com/us/search/businesses-for-sale-in-new-york"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for item in _jsonld_listing_items(page.html):
        if len(listings) >= max_per_source:
            break
        title = str(item.get("name") or "").strip()
        link = str(item.get("url") or "").strip()
        if not title or not link:
            continue
        properties = _jsonld_properties(item)
        offer = item.get("offers") if isinstance(item.get("offers"), dict) else {}
        address = {}
        place = offer.get("availableAtOrFrom") if isinstance(offer, dict) else {}
        if isinstance(place, dict):
            address = place.get("address") if isinstance(place.get("address"), dict) else {}
        location = ", ".join(str(value) for value in [address.get("addressLocality"), address.get("addressRegion")] if value)
        description = str(item.get("description") or "")
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_infer_industry(title + " " + description),
                location=location or _infer_location(title + " " + description),
                asking_price=_money_value(properties.get("Asking Price")) or _jsonld_price(offer),
                annual_revenue=_money_value(properties.get("Revenue")),
                cash_flow=_money_value(properties.get("Cash Flow")),
                financing=_financing_note(description),
                seller_financing_offered="seller financing" in description.lower(),
                description=_shorten(description),
                raw={"collection_mode": "live_public_jsonld", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} listings from public structured data.")


def _collect_businessexits(max_per_source: int) -> CollectorResult:
    source = "BusinessExits"
    url = "https://businessexits.com/listings/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for link, text in _anchors_with_text(page.html, url):
        if len(listings) >= max_per_source:
            break
        if "/listing/" not in urlparse(link).path or "listing price" not in text.lower():
            continue
        listings.append(
            Listing(
                title=_text_before_label(text, "Listing Price") or _title_from_url(link),
                source=source,
                listing_url=link,
                industry=_infer_industry(text),
                location=_infer_location(text),
                asking_price=_money_after(text, ["listing price"]),
                annual_revenue=_money_after(text, ["revenue"]),
                cash_flow=_money_after(text, ["income", "sde", "ebitda", "cash flow"]),
                financing=_financing_note(text),
                seller_financing_offered="seller financing" in text.lower(),
                description=_shorten(text),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} listing links from the public page.")


def _collect_businessmart(max_per_source: int) -> CollectorResult:
    source = "BusinessMart"
    url = "https://www.businessmart.com/businesses-for-sale.php"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    row_pattern = re.compile(
        r"<tr[^>]*>\s*<td[^>]*>\s*<a\s+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a></td>\s*"
        r"<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>",
        re.IGNORECASE | re.DOTALL,
    )
    for match in row_pattern.finditer(page.html):
        if len(listings) >= max_per_source:
            break
        link = urljoin(url, html.unescape(match.group(1)))
        title = _clean(match.group(2))
        if not title or "/business-for-sale/bid/" not in urlparse(link).path:
            continue
        asking = _clean(match.group(3))
        cash_flow = _clean(match.group(4))
        location = _clean(match.group(5))
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_infer_industry(title),
                location=location,
                asking_price=_money_value(asking),
                annual_revenue=None,
                cash_flow=_money_value(cash_flow),
                financing=_financing_note(title),
                seller_financing_offered=False,
                description=_shorten(f"{title} {location}"),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} table rows from the public page.")


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


def _collect_link_business(max_per_source: int) -> CollectorResult:
    source = "LINK"
    url = "https://linkbusiness.com/businesses-for-sale/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    detail_pattern = re.compile(r'href=["\'](/businesses-for-sale/[^"\']+/[^"\']+)["\']', re.IGNORECASE)
    matches = list(detail_pattern.finditer(page.html))
    listings: list[Listing] = []
    seen_links: set[str] = set()
    for index, match in enumerate(matches):
        if len(listings) >= max_per_source:
            break
        link = urljoin(url, html.unescape(match.group(1)))
        if not _is_link_business_detail(link):
            continue
        if link in seen_links:
            continue
        seen_links.add(link)
        end = matches[index + 1].start() if index + 1 < len(matches) else match.end() + 3500
        fragment = page.html[match.start() : end]
        text = _visible_text(fragment)
        title = _title_from_url(link)
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=link,
                industry=_link_industry(fragment) or _infer_industry(title + " " + text),
                location=_link_location(fragment) or _infer_location(title + " " + text),
                asking_price=_link_metric(fragment, "listingPrice"),
                annual_revenue=_link_metric(fragment, "sales"),
                cash_flow=_link_metric(fragment, "sde"),
                financing=_financing_note(text),
                seller_financing_offered="seller financing" in text.lower(),
                description=_shorten(title + " " + text),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} listing cards from the public page.")


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


def _collect_smergers(max_per_source: int) -> CollectorResult:
    source = "SMERGERS"
    url = "https://www.smergers.com/businesses-for-sale-and-investment-opportunities/t2b/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for card in _split_cards(page.html, '<div class="listing-card listing-item-wrapper'):
        if len(listings) >= max_per_source:
            break
        link = _first_href(card, "/business/")
        title = _clean(_first_match(card, r"<h2[^>]*>.*?<a[^>]*>(.*?)</a>"))
        if not link or not title:
            continue
        text = _visible_text(card)
        sales = _smergers_metric(card, "Run Rate Sales")
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=urljoin(url, link),
                industry=_infer_industry(title + " " + text),
                location=_infer_location(title + " " + text),
                asking_price=None,
                annual_revenue=sales,
                cash_flow=None,
                financing=_financing_note(text),
                seller_financing_offered=False,
                description=_shorten(text),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} public listing cards; asking price is not exposed on cards.")


def _collect_transferslot(max_per_source: int) -> CollectorResult:
    source = "Transferslot"
    url = "https://transferslot.com/"
    try:
        page = _fetch_public_page(url)
    except LiveCollectionError as error:
        return CollectorResult(source, [], "skipped", str(error))

    listings: list[Listing] = []
    for card in _split_cards(page.html, '<li class="product"'):
        if len(listings) >= max_per_source:
            break
        link = _first_href(card, "/products/")
        title = _clean(_first_match(card, r"<h2>(.*?)</h2>"))
        if not link or not title:
            continue
        text = _visible_text(card)
        listings.append(
            Listing(
                title=title,
                source=source,
                listing_url=urljoin(url, link),
                industry=_infer_industry(title + " " + text) or "Technology & Digital",
                location="Remote",
                asking_price=_int_attr(card, "data-price") or _money_after(text, ["asking price"]),
                annual_revenue=_annualized_mrr(_int_attr(card, "data-mrr")),
                cash_flow=_money_after(text, ["profits"]),
                financing=_financing_note(text),
                seller_financing_offered=False,
                description=_shorten(text),
                raw={"collection_mode": "live_public", "source_page": url},
            )
        )
    return CollectorResult(source, listings, "live_public", f"Parsed {len(listings)} public product cards.")


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


def _anchors_with_text(markup: str, base_url: str) -> list[tuple[str, str]]:
    anchors: list[tuple[str, str]] = []
    for match in re.finditer(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", markup, re.IGNORECASE | re.DOTALL):
        link = urljoin(base_url, html.unescape(match.group(1))).split("#", 1)[0]
        text = _clean(match.group(2))
        if text:
            anchors.append((link, text))
    return anchors


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
        match = re.search(rf"{re.escape(label)}\s*:?\s*(?:USD|US)?\s*\$?\s*([\d,.]+)\s*(m|mm|million|k)?", text, re.IGNORECASE)
        if match:
            return _money_value(match.group(0))
    return None


def _money_from_fragment(fragment: str | None) -> int | None:
    if not fragment:
        return None
    match = re.search(r"\$ ?([\d,]+)", fragment)
    return int(match.group(1).replace(",", "")) if match else None


def _money_value(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value)
    if any(term in text.lower() for term in ["undisclosed", "open to offers", "not disclosed", "n/a"]):
        return None
    match = re.search(r"\$?\s*((?:\d[\d,]*)(?:\.\d+)?)\s*(m|mm|million|k)?", text, re.IGNORECASE)
    if not match:
        return None
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    if suffix in {"m", "mm", "million"}:
        number *= 1_000_000
    elif suffix == "k":
        number *= 1_000
    return int(number)


def _annualized_mrr(value: int | None) -> int | None:
    return value * 12 if value is not None else None


def _jsonld_listing_items(markup: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for script in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        markup,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            document = json.loads(html.unescape(script.strip()))
        except json.JSONDecodeError:
            continue
        _collect_jsonld_items(document, items)
    return items


def _collect_jsonld_items(value: object, items: list[dict[str, object]]) -> None:
    if isinstance(value, list):
        for item in value:
            _collect_jsonld_items(item, items)
        return
    if not isinstance(value, dict):
        return
    item_type = value.get("@type")
    item_types = set(item_type) if isinstance(item_type, list) else {item_type}
    if item_types & {"Product", "Thing"} and value.get("url") and value.get("name"):
        items.append(value)
    for key in ("itemListElement", "item", "@graph", "mainEntity"):
        child = value.get(key)
        if child is not None:
            _collect_jsonld_items(child, items)


def _jsonld_properties(item: dict[str, object]) -> dict[str, str]:
    properties: dict[str, str] = {}
    values = item.get("additionalProperty")
    if not isinstance(values, list):
        return properties
    for value in values:
        if isinstance(value, dict) and value.get("name") and value.get("value"):
            properties[str(value["name"])] = str(value["value"])
    return properties


def _jsonld_price(offer: object) -> int | None:
    if isinstance(offer, dict):
        return _money_value(offer.get("price"))
    return None


def _text_before_label(text: str, label: str) -> str | None:
    index = text.lower().find(label.lower())
    if index <= 0:
        return None
    return text[:index].strip(" -:")


def _businessbroker_title(text: str) -> str:
    title = re.sub(r"^Asking Price:\s*\$?\s*[\d,.]+\s*(?:m|mm|million|k)?\s*", "", text, flags=re.IGNORECASE)
    title = re.split(r"\s+(?:Not Disclosed|[A-Z][a-z]+,\s*(?:NY|New York)|[A-Z][a-z]+ County)\b", title, maxsplit=1)[0]
    return title.strip(" -") or "BusinessBroker Listing"


def _link_metric(fragment: str, metric: str) -> int | None:
    match = re.search(rf"/businesses-for-sale/{re.escape(metric)}\?range=\{{([^}}]+)\}}", fragment, re.IGNORECASE)
    return _money_value(match.group(1)) if match else None


def _is_link_business_detail(link: str) -> bool:
    parts = [part for part in urlparse(link).path.split("/") if part]
    return len(parts) >= 3 and parts[0] == "businesses-for-sale" and bool(re.search(r"\d", parts[1]))


def _link_location(fragment: str) -> str | None:
    match = re.search(r"/businesses-for-sale/location/([^\"']+)", fragment, re.IGNORECASE)
    return unquote(match.group(1)).replace("-", " ") if match else None


def _link_industry(fragment: str) -> str | None:
    match = re.search(r"/businesses-for-sale/industry/([^\"']+)", fragment, re.IGNORECASE)
    if not match:
        return None
    return _infer_industry(unquote(match.group(1)).replace("-", " "))


def _smergers_metric(fragment: str, label: str) -> int | None:
    pattern = (
        rf"{re.escape(label)}.*?<div[^>]*text-right[^>]*>\s*"
        r"(?:<span[^>]*>\s*USD\s*</span>)?\s*([\d,.]+)\s*(million|m|k)?"
    )
    match = re.search(pattern, fragment, re.IGNORECASE | re.DOTALL)
    return _money_value(" ".join(part for part in match.groups() if part)) if match else None


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
    if any(term in lowered for term in ["commercial laundry", "linen", "uniform rental"]):
        return "Commercial Laundry"
    if any(term in lowered for term in ["conference", "trade show", "expo ", "event production"]):
        return "Conferences & Trade Shows"
    if any(term in lowered for term in ["office equipment", "copier", "printer leasing"]):
        return "Office Equipment Distribution"
    if any(term in lowered for term in ["security guard", "security services", "alarm", "protection services"]):
        return "Security & Protection Services"
    if any(term in lowered for term in ["staffing", "recruiting", "employment agency", "talent agency"]):
        return "Staffing"
    if any(term in lowered for term in ["flooring", "floor covering"]):
        return "Flooring"
    if any(term in lowered for term in ["insulation", "coating", "spray foam"]):
        return "Insulation & Coating"
    if "locksmith" in lowered:
        return "Locksmiths"
    if any(term in lowered for term in ["painting business", "painting contractor", "paint contractor"]):
        return "Painting Business"
    if any(term in lowered for term in ["plumbing", "electrical contractor", "hvac", "roofing"]):
        return "Specialty Trades"
    if any(term in lowered for term in ["clothing", "fashion", "apparel", "footwear"]):
        return "Clothing & Fashion"
    if any(term in lowered for term in ["personal care", "beauty", "salon", "spa "]):
        return "Personal Products & Services"
    if any(term in lowered for term in ["day care", "daycare", "child care", "childcare"]):
        return "Day Care & Child Care Centers"
    if any(term in lowered for term in ["school", "academy", "tutoring", "test prep", "test preparation", "seminar"]):
        return "Education & Training"
    if any(term in lowered for term in ["farm", "agriculture", "agricultural"]):
        return "Agricultural Production"
    if any(term in lowered for term in ["distillery", "brewery", "winery", "alcohol production"]):
        return "Distilleries & Alcohol Production"
    if any(term in lowered for term in ["food manufacturing", "food production", "food packaging", "co-packing", "copacking"]):
        return "Food Production & Packaging"
    if any(term in lowered for term in ["vending", "micro market"]):
        return "Vending Machines & Routes"
    if any(term in lowered for term in ["behavioral health", "mental health", "aba therapy", "addiction"]):
        return "Behavioral Health"
    if any(term in lowered for term in ["health club", "gym", "fitness center", "fitness studio"]):
        return "Health Clubs, Gyms & Fitness Centers"
    if any(term in lowered for term in ["physical therapy", "physiotherapy", "pt clinic"]):
        return "Physical Therapy"
    if any(term in lowered for term in ["wellness", "supplement", "skincare", "pet health"]):
        return "Wellness & Supplements"
    if any(term in lowered for term in ["landscaping", "lawn care", "grounds maintenance"]):
        return "Landscaping Services"
    if any(term in lowered for term in ["home maintenance", "household maintenance", "home repair"]):
        return "Household Maintenance"
    if any(term in lowered for term in ["nursery", "garden center"]):
        return "Nurseries & Garden Centers"
    if any(term in lowered for term in ["art gallery", "museum"]):
        return "Art Galleries & Museums"
    if any(term in lowered for term in ["sports facility", "sports team", "recreation facility"]):
        return "Sports Teams & Facilities"
    if any(term in lowered for term in ["travel agency", "travel agent"]):
        return "Travel Agents"
    if any(term in lowered for term in ["industrial services", "industrial equipment", "equipment maintenance"]):
        return "Industrial Services"
    if any(term in lowered for term in ["manufacturing", "manufacturer", "machine shop"]):
        return "Manufacturing"
    if any(term in lowered for term in ["textile", "fabric", "materials manufacturing"]):
        return "Textile & Materials Manufacturing"
    if any(term in lowered for term in ["printing", "signage", "display graphics", "print shop"]):
        return "Print, Signage & Display"
    if any(term in lowered for term in ["radio station", "broadcast radio"]):
        return "Radio Stations"
    if any(term in lowered for term in ["media", "content", "pr ", "public relations", "newsletter", "publication"]):
        return "Media & Content"
    if any(term in lowered for term in ["b2b", "business-to-business"]):
        return "B2B"
    if any(term in lowered for term in ["ecommerce", "e-commerce", "dtc", "amazon", "fba", "shopify"]):
        return "E-Commerce & Digital"
    if any(term in lowered for term in ["saas", "software", "app ", "internet business", "online marketplace"]):
        return "Technology & Digital"
    if any(term in lowered for term in ["auto parts recycling", "salvage yard"]):
        return "Auto Parts Recycling"
    if any(term in lowered for term in ["parking lot", "parking garage", "parking management"]):
        return "Parking"
    if any(term in lowered for term in ["taxi", "limousine", "black car"]):
        return "Taxi & Limousine"
    if any(term in lowered for term in ["passenger transport", "shuttle", "transportation"]):
        return "Passenger Transport"
    if any(term in lowered for term in ["digital marketing", "seo", "lead generation", "agency", "business services"]):
        return "Business Services"
    if any(term in lowered for term in ["construction", "contractor", "home services"]):
        return "Construction & Building Services"
    if any(term in lowered for term in ["real estate", "property management"]):
        return "Real Estate Services"
    if any(term in lowered for term in ["restaurant", "food service", "cafe", "bakery"]):
        return "Food & Beverage"
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
        return "Education & Training"
    return _infer_industry(lowered)


def _financing_note(text: str) -> str:
    lowered = text.lower()
    if "seller financing" in lowered:
        return "Seller financing mentioned in public listing."
    if "sba pre-qualified" in lowered or "sba pre qualified" in lowered:
        return "SBA pre-qualified; seller financing details unavailable."
    return "Financing details unavailable."
