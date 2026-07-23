from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from deal_finder_ai.models import EnrichedListing


NOTION_API_VERSION = "2022-06-28"


class NotionSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotionSyncResult:
    created_urls: list[str]
    updated_pages: int

    @property
    def created_pages(self) -> int:
        return len(self.created_urls)


def sync_to_notion(items: list[EnrichedListing], database_id: str | None = None) -> list[str]:
    return sync_to_notion_with_counts(items, database_id=database_id).created_urls


def sync_to_notion_with_counts(items: list[EnrichedListing], database_id: str | None = None) -> NotionSyncResult:
    token = os.getenv("NOTION_TOKEN")
    target_database_id = database_id or os.getenv("NOTION_DEALS_DATABASE_ID")
    if not token:
        raise NotionSyncError("NOTION_TOKEN is not set.")
    if not target_database_id:
        raise NotionSyncError("NOTION_DEALS_DATABASE_ID is not set.")

    existing_pages = _load_existing_pages_by_duplicate_key(token, target_database_id)
    created_urls: list[str] = []
    updated_pages = 0
    for item in items:
        if item.duplicate_key in existing_pages:
            _update_page(token, existing_pages[item.duplicate_key], item)
            updated_pages += 1
            continue
        page = _create_page(token, target_database_id, item)
        created_urls.append(page.get("url", ""))
        existing_pages[item.duplicate_key] = page["id"]
    return NotionSyncResult(created_urls=created_urls, updated_pages=updated_pages)


def _load_existing_pages_by_duplicate_key(token: str, database_id: str) -> dict[str, str]:
    pages: dict[str, str] = {}
    payload: dict[str, Any] = {"page_size": 100}
    while True:
        response = _notion_request(token, f"https://api.notion.com/v1/databases/{database_id}/query", payload)
        for page in response.get("results", []):
            rich_text = page.get("properties", {}).get("Duplicate Key", {}).get("rich_text", [])
            if rich_text:
                pages[rich_text[0].get("plain_text", "")] = page["id"]
        if not response.get("has_more") or not response.get("next_cursor"):
            return pages
        payload["start_cursor"] = response["next_cursor"]


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
        "Seller Financing Offered": {"checkbox": listing.seller_financing_offered},
        "Buy Box Score": {"rich_text": [{"text": {"content": item.score.explanation[:1900]}}]},
        "Status": {"status": {"name": "Not started"}},
        "Duplicate Key": {"rich_text": [{"text": {"content": item.duplicate_key}}]},
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
    if item.industry_assessment:
        properties.update(
            {
                "Sub-industry": {"rich_text": [{"text": {"content": item.industry_assessment.subindustry}}]},
                "Industry Score": {"select": {"name": item.industry_assessment.grade}},
                "Industry Assessment": {"rich_text": [{"text": {"content": item.industry_assessment.assessment}}]},
            }
        )
    return properties


def _notion_request(token: str, url: str, payload: dict[str, Any], method: str = "POST") -> dict[str, Any]:
    timeout = int(os.getenv("DEAL_FINDER_NOTION_TIMEOUT_SECONDS", "30"))
    retries = int(os.getenv("DEAL_FINDER_NOTION_RETRIES", "2"))
    for attempt in range(retries + 1):
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
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            body = error.read().decode("utf-8")
            if error.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                raise NotionSyncError(f"Notion API request failed: {body}") from error
        except (URLError, TimeoutError) as error:
            if attempt >= retries:
                raise NotionSyncError(f"Notion API request failed after retries: {error}") from error
        time.sleep(min(2**attempt, 8))
    raise NotionSyncError("Notion API request failed after retries.")
