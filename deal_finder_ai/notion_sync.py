from __future__ import annotations

import json
import os
from datetime import date
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from deal_finder_ai.models import EnrichedListing


NOTION_API_VERSION = "2022-06-28"


class NotionSyncError(RuntimeError):
    pass


def sync_to_notion(items: list[EnrichedListing], database_id: str | None = None) -> list[str]:
    token = os.getenv("NOTION_TOKEN")
    target_database_id = database_id or os.getenv("NOTION_DEALS_DATABASE_ID")
    if not token:
        raise NotionSyncError("NOTION_TOKEN is not set.")
    if not target_database_id:
        raise NotionSyncError("NOTION_DEALS_DATABASE_ID is not set.")

    existing_pages = _load_existing_pages_by_duplicate_key(token, target_database_id)
    created_urls: list[str] = []
    for item in items:
        if item.duplicate_key in existing_pages:
            _update_page(token, existing_pages[item.duplicate_key], item)
            continue
        page = _create_page(token, target_database_id, item)
        created_urls.append(page.get("url", ""))
        existing_pages[item.duplicate_key] = page["id"]
    return created_urls


def _load_existing_pages_by_duplicate_key(token: str, database_id: str) -> dict[str, str]:
    response = _notion_request(
        token,
        f"https://api.notion.com/v1/databases/{database_id}/query",
        {"page_size": 100},
    )
    pages: dict[str, str] = {}
    for page in response.get("results", []):
        rich_text = page.get("properties", {}).get("Duplicate Key", {}).get("rich_text", [])
        if rich_text:
            pages[rich_text[0].get("plain_text", "")] = page["id"]
    return pages


def _create_page(token: str, database_id: str, item: EnrichedListing) -> dict[str, Any]:
    return _notion_request(
        token,
        "https://api.notion.com/v1/pages",
        {"parent": {"database_id": database_id}, "properties": _page_properties(item, include_date_found=True)},
    )


def _update_page(token: str, page_id: str, item: EnrichedListing) -> dict[str, Any]:
    return _notion_request(
        token,
        f"https://api.notion.com/v1/pages/{page_id}",
        {"properties": _page_properties(item, include_date_found=False)},
        method="PATCH",
    )


def _page_properties(item: EnrichedListing, include_date_found: bool) -> dict[str, Any]:
    listing = item.listing
    today = date.today().isoformat()
    properties: dict[str, Any] = {
        "Deal Name": {"title": [{"text": {"content": listing.title}}]},
        "Source": {"select": {"name": listing.source}},
        "Location": {"rich_text": [{"text": {"content": listing.location or "Unavailable"}}]},
        "Financing": {"rich_text": [{"text": {"content": listing.financing or "Unavailable"}}]},
        "Seller Financing Offered": {"checkbox": listing.seller_financing_offered},
        "Score": {"number": item.score.score},
        "Score Explanation": {"rich_text": [{"text": {"content": item.score.explanation[:1900]}}]},
        "Status": {"status": {"name": "Not started"}},
        "Duplicate Key": {"rich_text": [{"text": {"content": item.duplicate_key}}]},
        "Executive Summary": {"rich_text": [{"text": {"content": item.executive_summary[:1900]}}]},
        "Last Seen": {"date": {"start": today}},
    }
    if include_date_found:
        properties["Date Found"] = {"date": {"start": today}}
    if listing.industry:
        properties["Industry"] = {"multi_select": [{"name": listing.industry.replace("Print, Signage", "Print Signage")}]}
    if listing.listing_url or not include_date_found:
        properties["Listing URL"] = {"url": listing.listing_url}
    if listing.asking_price is not None or not include_date_found:
        properties["Asking Price"] = {"number": listing.asking_price}
    if listing.annual_revenue is not None or not include_date_found:
        properties["Annual Revenue"] = {"number": listing.annual_revenue}
    if listing.cash_flow is not None or not include_date_found:
        properties["Cash Flow / SDE / EBITDA"] = {"number": listing.cash_flow}
    return properties


def _notion_request(token: str, url: str, payload: dict[str, Any], method: str = "POST") -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_API_VERSION,
        },
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8")
        raise NotionSyncError(f"Notion API request failed: {body}") from error
