from __future__ import annotations

from dataclasses import dataclass

from deal_finder_ai.collectors.bizquest import collect_sample_listings as collect_bizquest_samples
from deal_finder_ai.models import Listing


@dataclass(frozen=True)
class Marketplace:
    name: str
    url: str
    collection_mode: str
    notes: str


PRIORITY_MARKETPLACES: tuple[Marketplace, ...] = (
    Marketplace(
        name="AcquisitionsDirect",
        url="https://acquisitionsdirect.com/buy/",
        collection_mode="sample_data_for_v1",
        notes="Public site with visible featured listings; live extraction should be added carefully.",
    ),
    Marketplace(
        name="AppBusinessBrokers",
        url="https://www.appbusinessbrokers.com/buy/",
        collection_mode="sample_data_for_v1",
        notes="Public buy page, but financial fields may be sparse or unavailable.",
    ),
    Marketplace(
        name="Axial",
        url="https://network.axial.net/received-deals/new",
        collection_mode="login_gated_skip_live_collection",
        notes="Requires a member login. Do not automate without an official export, API, or explicit permitted workflow.",
    ),
    Marketplace(
        name="BizBuySell",
        url="https://www.bizbuysell.com/",
        collection_mode="sample_data_for_v1",
        notes="Large public marketplace. Respect robots.txt crawl delay and avoid member/broker areas.",
    ),
    Marketplace(
        name="BizQuest",
        url="https://www.bizquest.com/businesses-for-sale/?q=bHQ9MzAsNDAsODA%3D",
        collection_mode="sample_data_for_v1",
        notes="Initial v1 source with broad public listing coverage.",
    ),
    Marketplace(
        name="FirstChoice Business Brokers",
        url="https://businessesforsaleinnewyorkcity.com",
        collection_mode="sample_data_for_v1",
        notes="New York-focused broker source.",
    ),
    Marketplace(
        name="Merge",
        url="https://gomerge.com/agencies-for-sale/",
        collection_mode="sample_data_for_v1",
        notes="Agency-focused source; useful for professional services and digital agencies.",
    ),
    Marketplace(
        name="QuietLight",
        url="https://quietlight.com/listings/",
        collection_mode="sample_data_for_v1",
        notes="Curated online-business broker source.",
    ),
    Marketplace(
        name="Website Closers",
        url="https://www.websiteclosers.com/businesses-for-sale/",
        collection_mode="sample_data_for_v1",
        notes="Digital, e-commerce, SaaS, and internet business broker source.",
    ),
)


def collect_priority_marketplace_samples() -> list[Listing]:
    listings: list[Listing] = []
    listings.extend(collect_bizquest_samples())
    listings.extend(_sample_listings_from_priority_sources())
    return listings


def active_marketplace_names() -> list[str]:
    return [marketplace.name for marketplace in PRIORITY_MARKETPLACES]


def _sample_listings_from_priority_sources() -> list[Listing]:
    return [
        Listing(
            title="SBA Pre-Qualified Natural Wellness E-Commerce Brand",
            source="AcquisitionsDirect",
            listing_url="https://acquisitionsdirect.com/sample/natural-wellness-ecommerce-brand",
            industry="Wellness & Supplements",
            location="Fully online",
            asking_price=1_650_000,
            annual_revenue=None,
            cash_flow=540_000,
            financing="SBA pre-qualified; seller financing details unavailable.",
            seller_financing_offered=False,
            description="Online wellness brand. Revenue was not available in the sample record.",
        ),
        Listing(
            title="Mobile App Portfolio With Subscription Revenue",
            source="AppBusinessBrokers",
            listing_url="https://www.appbusinessbrokers.com/sample/mobile-app-portfolio",
            industry="Technology & Digital",
            location="World / remote",
            asking_price=1_250_000,
            annual_revenue=1_900_000,
            cash_flow=510_000,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="App portfolio with recurring subscription revenue and remote operations.",
        ),
        Listing(
            title="Axial Member Deal Placeholder - Industrial Services",
            source="Axial",
            listing_url="https://network.axial.net/received-deals/new",
            industry="Industrial Services",
            location="New York",
            asking_price=None,
            annual_revenue=None,
            cash_flow=None,
            financing="Unavailable. Axial is login-gated and should use an approved export/API.",
            seller_financing_offered=False,
            description="Placeholder showing why login-gated sources are not live-collected in v1.",
        ),
        Listing(
            title="New York Specialty Trades Contractor",
            source="BizBuySell",
            listing_url="https://www.bizbuysell.com/sample/new-york-specialty-trades-contractor",
            industry="Specialty Trades",
            location="New York, NY",
            asking_price=3_200_000,
            annual_revenue=5_400_000,
            cash_flow=925_000,
            financing="Seller financing available for a qualified buyer.",
            seller_financing_offered=True,
            description="Specialty contractor with repeat commercial accounts.",
        ),
        Listing(
            title="NYC Professional Services Firm",
            source="FirstChoice Business Brokers",
            listing_url="https://businessesforsaleinnewyorkcity.com/sample/professional-services-firm",
            industry="Professional Services",
            location="New York City, NY",
            asking_price=2_350_000,
            annual_revenue=3_600_000,
            cash_flow=690_000,
            financing="Seller financing details unavailable.",
            seller_financing_offered=False,
            description="Professional services firm serving small business clients.",
        ),
        Listing(
            title="Remote B2B Content Marketing Agency",
            source="Merge",
            listing_url="https://gomerge.com/sample/b2b-content-marketing-agency",
            industry="Media & Content",
            location="Remote",
            asking_price=1_850_000,
            annual_revenue=2_700_000,
            cash_flow=640_000,
            financing="Seller will consider transition support; financing unavailable.",
            seller_financing_offered=False,
            description="Remote agency with retainer-based client relationships.",
        ),
        Listing(
            title="Remote Education Content Business",
            source="QuietLight",
            listing_url="https://quietlight.com/sample/education-content-business",
            industry="Training & Education",
            location="Fully remote",
            asking_price=4_800_000,
            annual_revenue=6_200_000,
            cash_flow=1_450_000,
            financing="Seller financing unavailable in listing.",
            seller_financing_offered=False,
            description="Digital education content business with evergreen traffic.",
        ),
        Listing(
            title="Healthcare E-Commerce Brand",
            source="Website Closers",
            listing_url="https://www.websiteclosers.com/sample/healthcare-ecommerce-brand",
            industry="Healthcare",
            location="Online / relocatable",
            asking_price=5_500_000,
            annual_revenue=8_400_000,
            cash_flow=1_700_000,
            financing="Partial seller note may be available.",
            seller_financing_offered=True,
            description="Healthcare e-commerce brand with outsourced fulfillment.",
        ),
        Listing(
            title="Out-of-Range Online Marketplace Business",
            source="Website Closers",
            listing_url="https://www.websiteclosers.com/sample/out-of-range-marketplace",
            industry="E-Commerce & Digital",
            location="Remote",
            asking_price=8_900_000,
            annual_revenue=12_500_000,
            cash_flow=2_900_000,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="Strong business but outside the current target price and SDE range.",
        ),
    ]
