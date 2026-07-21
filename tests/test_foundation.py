import unittest

from deal_finder_ai.collectors.marketplaces import active_marketplace_names, collect_priority_marketplace_samples
from deal_finder_ai.collectors.live import _robots_text_allows, _split_cards
from deal_finder_ai.criteria import load_criteria
from deal_finder_ai.duplicates import duplicate_key, normalize_url
from deal_finder_ai.models import EnrichedListing, Listing, ScoreResult
from deal_finder_ai.notion_sync import _page_properties
from deal_finder_ai.pipeline import enrich_listings, qualified_listings
from deal_finder_ai.scoring import score_listing


class DuplicateTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_parameters(self):
        first = normalize_url("https://www.bizquest.com/sample/deal?utm_source=x&b=2")
        second = normalize_url("https://bizquest.com/sample/deal?b=2")
        self.assertEqual(first, second)

    def test_duplicate_key_prefers_normalized_url(self):
        listing = Listing(title="Deal", source="BizQuest", listing_url="https://www.bizquest.com/sample/deal?utm_source=x")
        self.assertEqual(duplicate_key(listing), "https://bizquest.com/sample/deal")

    def test_duplicate_key_prefers_sample_id_when_present(self):
        listing = Listing(
            title="Sample Deal",
            source="BizQuest",
            listing_url="https://www.bizquest.com/businesses-for-sale/",
            raw={"sample_id": "sample-deal"},
        )
        self.assertEqual(duplicate_key(listing), "bizquest:sample-deal")


class ScoringTests(unittest.TestCase):
    def test_strong_new_york_seller_financed_listing_scores_promising(self):
        criteria = load_criteria()
        listing = Listing(
            title="Strong Services Deal",
            source="BizQuest",
            listing_url="https://example.com/deal",
            industry="Business Services",
            location="New York",
            asking_price=2_000_000,
            cash_flow=700_000,
            seller_financing_offered=True,
        )
        result = score_listing(listing, criteria)
        self.assertGreaterEqual(result.score, 75)
        self.assertEqual(result.status, "Promising")

    def test_missing_financials_are_not_guessed(self):
        criteria = load_criteria()
        listing = Listing(
            title="Missing Cash Flow",
            source="BizQuest",
            listing_url="https://example.com/missing",
            industry="Business Services",
            location="New York",
            asking_price=2_000_000,
            cash_flow=None,
        )
        result = score_listing(listing, criteria)
        self.assertLess(result.score, 75)
        self.assertIn("unavailable", result.explanation)

    def test_fedex_routes_are_excluded_by_deal_breaker(self):
        criteria = load_criteria()
        listing = Listing(
            title="11 Carveout FedEx P&D Routes",
            source="BizQuest",
            listing_url="https://example.com/fedex-routes",
            industry="Transportation & Logistics",
            location="Eastern New York",
            asking_price=1_119_000,
            cash_flow=600_000,
            description="FedEx pickup and delivery routes.",
        )
        result = score_listing(listing, criteria)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.status, "Excluded")
        self.assertIn("deal breaker", result.explanation)

    def test_amazon_fba_businesses_are_excluded_by_deal_breaker(self):
        criteria = load_criteria()
        listing = Listing(
            title="Turnkey Amazon FBA Business - Proven Consumer Brand",
            source="AcquisitionsDirect",
            listing_url="https://example.com/amazon-fba-business",
            industry="E-Commerce & Digital",
            location="Fully online",
            asking_price=2_500_000,
            cash_flow=750_000,
            description="Amazon FBA brand with strong marketplace history.",
        )
        result = score_listing(listing, criteria)
        self.assertEqual(result.score, 0)
        self.assertEqual(result.status, "Excluded")
        self.assertIn("Amazon FBA", result.explanation)


class PipelineTests(unittest.TestCase):
    def test_pipeline_removes_duplicate_sample_listing(self):
        criteria = load_criteria()
        listings = collect_priority_marketplace_samples()
        enriched = enrich_listings(listings, criteria)
        self.assertEqual(len(active_marketplace_names()), 9)
        self.assertEqual(len(listings), 14)
        self.assertEqual(len(enriched), 12)
        self.assertTrue(all("fedex" not in item.listing.title.lower() for item in enriched))

    def test_pipeline_finds_qualified_sample_deals(self):
        criteria = load_criteria()
        enriched = enrich_listings(collect_priority_marketplace_samples(), criteria)
        qualified = qualified_listings(enriched, criteria)
        self.assertEqual(len(qualified), 5)
        self.assertTrue(all(item.score.score >= 75 for item in qualified))
        self.assertTrue(all(item.listing.listing_url for item in qualified))

    def test_sample_listings_do_not_use_generic_source_pages_as_listing_urls(self):
        generic_urls = {
            "https://www.appbusinessbrokers.com/buy/",
            "https://businessesforsaleinnewyorkcity.com/",
            "https://businessesforsaleinnewyorkcity.com/businesses-for-sale",
            "https://www.websiteclosers.com/businesses-for-sale/",
            "https://www.bizquest.com/restaurants-for-sale/",
        }
        listings = collect_priority_marketplace_samples()
        urls = {listing.listing_url for listing in listings if listing.listing_url}
        self.assertTrue(generic_urls.isdisjoint(urls))


class LiveCollectorTests(unittest.TestCase):
    def test_robot_parser_allows_normal_path_when_query_urls_are_blocked(self):
        robots = """
        User-agent: *
        Disallow: /?
        Disallow: /wp-admin/
        Allow: /wp-admin/admin-ajax.php
        """
        self.assertTrue(_robots_text_allows(robots, "https://example.com/businesses-for-sale/"))
        self.assertFalse(_robots_text_allows(robots, "https://example.com/?s=listing"))

    def test_quietlight_card_split_ignores_nested_card_classes(self):
        markup = """
        <div class="listing-card grid-item match-grid public-listing all ecommerce">
          <a href="https://quietlight.com/listings/123/" class="listing-card__link"></a>
          <div class="listing-card__price">$1,250,000</div>
          <div class="listing-card__profit-item" data-revenue="2000000"></div>
        </div>
        """
        cards = _split_cards(markup, '<div class="listing-card grid-item')
        self.assertEqual(len(cards), 1)
        self.assertIn("listing-card__price", cards[0])


class NotionSyncTests(unittest.TestCase):
    def test_update_payload_clears_unavailable_listing_url_and_financials(self):
        item = EnrichedListing(
            listing=Listing(
                title="No Detail URL",
                source="AppBusinessBrokers",
                listing_url=None,
                location="Unavailable",
                financing="Unavailable",
            ),
            duplicate_key="appbusinessbrokers:no-detail",
            score=ScoreResult(
                score=25,
                explanation="No public detail URL.",
                matched_criteria=[],
                missed_criteria=[],
                status="Needs Review",
            ),
            executive_summary="Placeholder only.",
        )
        properties = _page_properties(item, include_date_found=False)
        self.assertEqual(properties["Listing URL"], {"url": None})
        self.assertEqual(properties["Asking Price"], {"number": None})
        self.assertEqual(properties["Annual Revenue"], {"number": None})
        self.assertEqual(properties["Cash Flow / SDE / EBITDA"], {"number": None})


if __name__ == "__main__":
    unittest.main()
