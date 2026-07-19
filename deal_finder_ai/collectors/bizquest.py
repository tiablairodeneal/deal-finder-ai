from __future__ import annotations

from deal_finder_ai.models import Listing


def collect_sample_listings() -> list[Listing]:
    """Return realistic sample listings for a safe first workflow demo.

    Live collection should only read public pages that allow automation. This
    starter keeps the workflow testable without bypassing login walls, paywalls,
    CAPTCHAs, or robots.txt.
    """

    return [
        Listing(
            title="Premier NYC Commercial Cleaning Empire - $3.46M+ Revenue",
            source="BizQuest",
            listing_url="https://www.bizquest.com/business-for-sale/nyc-commercial-cleaning-company-in-biz-since-1988/BW2244713/",
            industry="Business Services",
            location="New York County, NY",
            asking_price=2_100_000,
            annual_revenue=3_460_799,
            cash_flow=None,
            financing="Seller financing available; cash flow requires sign-in on source page.",
            seller_financing_offered=True,
            description="Public BizQuest listing. Cash flow is not visible without sign-in and is marked unavailable.",
            raw={"sample_id": "premier-nyc-commercial-cleaning"},
        ),
        Listing(
            title="11 Carveout FedEx P&D Routes - Eastern New York Area",
            source="BizQuest",
            listing_url="https://www.bizquest.com/business-for-sale/11-carveout-fedex-pandd-routes-eastern-new-york-area/BW2510731/",
            industry="Transportation & Logistics",
            location="Eastern New York",
            asking_price=1_119_000,
            annual_revenue=1_905_222,
            cash_flow=317_850,
            financing="Seller financing available up to 15% of purchase price; not SBA eligible.",
            seller_financing_offered=True,
            description="Public BizQuest listing for FedEx pickup and delivery routes.",
            raw={"sample_id": "fedex-routes-eastern-new-york"},
        ),
        Listing(
            title="Electrical Contractor (#22685)",
            source="BizQuest",
            listing_url="https://www.bizquest.com/business-for-sale/electrical-contractor-22685/BW2347600/",
            industry="Construction & Building Services",
            location="Nassau County, NY",
            asking_price=3_350_000,
            annual_revenue=5_341_789,
            cash_flow=None,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="Public BizQuest listing. Cash flow requires sign-in on source page and is marked unavailable.",
            raw={"sample_id": "electrical-contractor-22685"},
        ),
        Listing(
            title="Regional Restaurant Group - No Public Detail Listing Extracted",
            source="BizQuest",
            listing_url=None,
            industry="Food & Beverage",
            location="Pennsylvania",
            asking_price=4_500_000,
            annual_revenue=7_500_000,
            cash_flow=700_000,
            financing="No seller financing mentioned.",
            seller_financing_offered=False,
            description="Out-of-geography sample. No specific public detail URL was captured, so the listing URL is unavailable.",
            raw={"sample_id": "regional-restaurant-group"},
        ),
        Listing(
            title="Duplicate Premier NYC Commercial Cleaning Listing",
            source="BizQuest",
            listing_url="https://www.bizquest.com/business-for-sale/nyc-commercial-cleaning-company-in-biz-since-1988/BW2244713/?utm_source=newsletter",
            industry="Business Services",
            location="New York County, NY",
            asking_price=2_100_000,
            annual_revenue=3_460_799,
            cash_flow=None,
            financing="Seller financing available; cash flow requires sign-in on source page.",
            seller_financing_offered=True,
            description="Duplicate of the commercial cleaning listing with tracking parameters.",
            raw={"sample_id": "premier-nyc-commercial-cleaning"},
        ),
    ]
