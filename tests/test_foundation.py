import unittest

from deal_finder_ai.collectors.marketplaces import active_marketplace_names, collect_priority_marketplace_samples
from deal_finder_ai.criteria import load_criteria
from deal_finder_ai.duplicates import duplicate_key, normalize_url
from deal_finder_ai.models import Listing
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


class PipelineTests(unittest.TestCase):
    def test_pipeline_removes_duplicate_sample_listing(self):
        criteria = load_criteria()
        listings = collect_priority_marketplace_samples()
        enriched = enrich_listings(listings, criteria)
        self.assertEqual(len(active_marketplace_names()), 9)
        self.assertEqual(len(listings), 14)
        self.assertEqual(len(enriched), 13)

    def test_pipeline_finds_qualified_sample_deals(self):
        criteria = load_criteria()
        enriched = enrich_listings(collect_priority_marketplace_samples(), criteria)
        qualified = qualified_listings(enriched, criteria)
        self.assertEqual(len(qualified), 10)
        self.assertTrue(all(item.score.score >= 75 for item in qualified))


if __name__ == "__main__":
    unittest.main()
