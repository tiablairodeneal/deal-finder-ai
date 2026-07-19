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
            title="New York Commercial Cleaning and Facility Services Company",
            source="BizQuest",
            listing_url="https://www.bizquest.com/sample/new-york-commercial-cleaning",
            industry="Business Services",
            location="New York State",
            asking_price=2_800_000,
            annual_revenue=4_200_000,
            cash_flow=850_000,
            financing="Seller financing available for qualified buyer.",
            seller_financing_offered=True,
            description="Recurring commercial clients, stable crew, and owner transition support.",
        ),
        Listing(
            title="Remote E-Commerce Wellness Brand",
            source="BizQuest",
            listing_url="https://www.bizquest.com/sample/remote-ecommerce-wellness",
            industry="E-Commerce & Digital",
            location="Fully remote",
            asking_price=1_750_000,
            annual_revenue=3_100_000,
            cash_flow=620_000,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="Direct-to-consumer wellness products with outsourced fulfillment.",
        ),
        Listing(
            title="Passenger Transportation Business in Queens",
            source="BizQuest",
            listing_url="https://www.bizquest.com/sample/queens-passenger-transport",
            industry="Passenger Transport",
            location="Queens, NY",
            asking_price=5_900_000,
            annual_revenue=None,
            cash_flow=1_950_000,
            financing="Seller will consider partial seller note.",
            seller_financing_offered=True,
            description="Fleet-based service business with local contracts. Revenue not provided.",
        ),
        Listing(
            title="Regional Restaurant Group",
            source="BizQuest",
            listing_url="https://www.bizquest.com/sample/regional-restaurant-group?utm_source=test",
            industry="Food & Beverage",
            location="Pennsylvania",
            asking_price=4_500_000,
            annual_revenue=7_500_000,
            cash_flow=700_000,
            financing="No seller financing mentioned.",
            seller_financing_offered=False,
            description="Multi-unit restaurant group outside target geography.",
        ),
        Listing(
            title="Duplicate Commercial Cleaning Listing",
            source="BizQuest",
            listing_url="https://www.bizquest.com/sample/new-york-commercial-cleaning?utm_source=newsletter",
            industry="Business Services",
            location="New York State",
            asking_price=2_800_000,
            annual_revenue=4_200_000,
            cash_flow=850_000,
            financing="Seller financing available for qualified buyer.",
            seller_financing_offered=True,
            description="Same listing URL after tracking parameters are removed.",
        ),
    ]

