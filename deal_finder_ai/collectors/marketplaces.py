from __future__ import annotations

from dataclasses import dataclass

from deal_finder_ai.collectors.bizquest import collect_sample_listings as collect_bizquest_samples
from deal_finder_ai.collectors.live import CollectorResult, collect_live_marketplace_listings
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
        collection_mode="live_public_when_listings_visible",
        notes="Public site; current buy page is checked for public listing detail links.",
    ),
    Marketplace(
        name="AppBusinessBrokers",
        url="https://www.appbusinessbrokers.com/buy/",
        collection_mode="live_public_when_listings_visible",
        notes="Public buy page is checked, but it may not expose listing detail pages in static HTML.",
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
        collection_mode="skipped_when_blocked",
        notes="Large marketplace. The job skips live collection if the site blocks automated public fetches.",
    ),
    Marketplace(
        name="BizQuest",
        url="https://www.bizquest.com/businesses-for-sale/?q=bHQ9MzAsNDAsODA%3D",
        collection_mode="skipped_when_blocked",
        notes="The job skips live collection if the site blocks automated public fetches.",
    ),
    Marketplace(
        name="FirstChoice Business Brokers",
        url="https://businessesforsaleinnewyorkcity.com",
        collection_mode="live_public_when_listings_visible",
        notes="New York-focused broker source; static page is checked for listing detail links.",
    ),
    Marketplace(
        name="Merge",
        url="https://gomerge.com/agencies-for-sale/",
        collection_mode="live_public",
        notes="Agency-focused source with public listing cards.",
    ),
    Marketplace(
        name="QuietLight",
        url="https://quietlight.com/listings/",
        collection_mode="live_public",
        notes="Curated online-business broker source with public listing cards.",
    ),
    Marketplace(
        name="Website Closers",
        url="https://www.websiteclosers.com/businesses-for-sale/",
        collection_mode="live_public",
        notes="Digital, e-commerce, SaaS, and internet business broker source with public listing cards.",
    ),
)


def collect_priority_marketplace_listings(max_per_source: int = 10) -> list[Listing]:
    results = collect_priority_marketplace_results(max_per_source=max_per_source)
    listings: list[Listing] = []
    for result in results:
        listings.extend(result.listings)
    return listings


def collect_priority_marketplace_results(max_per_source: int = 10) -> list[CollectorResult]:
    return collect_live_marketplace_listings(max_per_source=max_per_source)


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
            title="Established Health & Wellness Supplement Brand",
            source="AcquisitionsDirect",
            listing_url="https://acquisitionsdirect.com/buy-a-business/established-health-wellness-supplement-brand/",
            industry="Wellness & Supplements",
            location="Fully online",
            asking_price=1_800_000,
            annual_revenue=1_968_329,
            cash_flow=514_823,
            financing="Seller transition support mentioned; seller financing details unavailable.",
            seller_financing_offered=False,
            description="Public AcquisitionsDirect listing for a health and wellness supplement brand.",
            raw={"sample_id": "established-health-wellness-supplement-brand"},
        ),
        Listing(
            title="AppBusinessBrokers - No Public Detail Listing Extracted",
            source="AppBusinessBrokers",
            listing_url=None,
            industry="Technology & Digital",
            location="Unavailable",
            asking_price=None,
            annual_revenue=None,
            cash_flow=None,
            financing="No specific public listing detail URL was exposed in the static source page.",
            seller_financing_offered=False,
            description="Source placeholder only. Do not save as a qualified deal until a specific listing URL and financials are available.",
            raw={"sample_id": "appbusinessbrokers-no-public-detail"},
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
            raw={"sample_id": "axial-industrial-services-placeholder"},
        ),
        Listing(
            title="New York Specialty Trades Contractor",
            source="BizBuySell",
            listing_url="https://www.bizbuysell.com/business-opportunity/nyc-union-plumbing-contractor-900k-sde-team-fleet-backlog/2511895/",
            industry="Specialty Trades",
            location="Richmond County, NY",
            asking_price=1_795_000,
            annual_revenue=None,
            cash_flow=922_000,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="Public BizBuySell listing for a NYC union plumbing contractor.",
            raw={"sample_id": "nyc-union-plumbing-contractor"},
        ),
        Listing(
            title="FirstChoice Business Brokers - No Public Detail Listing Extracted",
            source="FirstChoice Business Brokers",
            listing_url=None,
            industry="Professional Services",
            location="New York City, NY",
            asking_price=None,
            annual_revenue=None,
            cash_flow=None,
            financing="No specific public listing detail URL was exposed in the static source page.",
            seller_financing_offered=False,
            description="Source placeholder only. Do not save as a qualified deal until a specific listing URL and financials are available.",
            raw={"sample_id": "firstchoice-no-public-detail"},
        ),
        Listing(
            title="Retainer-Based PR Agency with VC-Backed AI & Deep Tech Access",
            source="Merge",
            listing_url="https://gomerge.com/agencies-for-sale/retainer-based-pr-agency-with-vc-backed-ai-deep-tech-access/",
            industry="Media & Content",
            location="Fully remote",
            asking_price=5_000_000,
            annual_revenue=2_012_547,
            cash_flow=1_018_372,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="Public Merge listing for a remote PR agency serving AI and deep tech clients.",
            raw={"sample_id": "retainer-pr-agency-vc-ai-deep-tech"},
        ),
        Listing(
            title="SBA Pre-Qualified Pet Health & Wellness Brand",
            source="QuietLight",
            listing_url="https://quietlight.com/listings/18829047/",
            industry="Wellness & Supplements",
            location="Fully remote",
            asking_price=4_400_000,
            annual_revenue=4_649_698,
            cash_flow=1_266_931,
            financing="SBA pre-qualified; seller financing details unavailable.",
            seller_financing_offered=False,
            description="Public QuietLight listing for a pet health and wellness e-commerce brand.",
            raw={"sample_id": "pet-health-wellness-brand-18829047"},
        ),
        Listing(
            title="SBA Pre-Qualified Digital Marketing & Lead Generation Agency",
            source="Website Closers",
            listing_url="https://www.websiteclosers.com/businesses/sba-pre-qualified-digital-marketing-lead-generation-agency-home-services-100-recurring-revenue-269-active-clients-35-yoy-growth/119165/",
            industry="Business Services",
            location="Remote",
            asking_price=2_675_000,
            annual_revenue=1_158_441,
            cash_flow=713_790,
            financing="SBA pre-qualified; seller financing details unavailable.",
            seller_financing_offered=False,
            description="Public Website Closers listing for a home-services digital marketing and lead generation agency.",
            raw={"sample_id": "websiteclosers-119165"},
        ),
        Listing(
            title="Out-of-Range Online Marketplace Business - No Public Detail Listing Extracted",
            source="Website Closers",
            listing_url=None,
            industry="E-Commerce & Digital",
            location="Remote",
            asking_price=8_900_000,
            annual_revenue=12_500_000,
            cash_flow=2_900_000,
            financing="Financing details unavailable.",
            seller_financing_offered=False,
            description="Strong business but outside the current target price and SDE range. No specific public detail URL was captured.",
            raw={"sample_id": "out-of-range-marketplace"},
        ),
    ]
