import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from unittest.mock import patch

from deal_finder_ai.collectors.marketplaces import active_marketplace_names, collect_priority_marketplace_samples
from deal_finder_ai.collectors.live import _robots_text_allows, _split_cards
from deal_finder_ai.criteria import load_criteria
from deal_finder_ai.duplicates import duplicate_key, normalize_url
from deal_finder_ai.industry_assessment import (
    SCORING_METHODOLOGY_VERSION,
    IndustryResearchCache,
    IndustryResearchInput,
    LiveIndustryResearchProvider,
    ProviderConfigurationError,
    SourceDocument,
    SubindustryClassification,
    assess_listing_industries,
    build_research_from_evidence,
    build_cache_key,
    classify_subindustry,
    configured_research_provider,
    score_industry,
)
from deal_finder_ai.models import EnrichedListing, IndustryAssessment, Listing, ScoreResult
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

    def test_pipeline_adds_industry_assessment_to_existing_enrichment(self):
        criteria = load_criteria()
        enriched = enrich_listings(collect_priority_marketplace_samples(), criteria)
        assessed = [item for item in enriched if item.industry_assessment]
        self.assertEqual(len(assessed), len(enriched))
        self.assertTrue(all(item.industry_assessment.grade in {"A", "B", "C", "D"} for item in assessed))


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

    def test_industry_assessment_populates_exact_three_notion_fields(self):
        item = EnrichedListing(
            listing=Listing(
                title="Commercial Laundry Route",
                source="BizQuest",
                listing_url="https://example.com/laundry",
                industry="Business Services",
                location="New York",
            ),
            duplicate_key="https://example.com/laundry",
            score=ScoreResult(80, "Deal score stays internal.", [], [], "Promising"),
            executive_summary="Summary.",
            industry_assessment=IndustryAssessment(
                subindustry="Commercial Laundry",
                grade="B",
                assessment="Contracted repeat demand supports retention; equipment needs and local price competition temper the opportunity.",
                cache_key="commercial_laundry | United States | eta-industry-v1",
                internal_score=78,
            ),
        )
        properties = _page_properties(item, include_date_found=True)
        self.assertEqual(properties["Sub-industry"], {"rich_text": [{"text": {"content": "Commercial Laundry"}}]})
        self.assertEqual(properties["Industry Score"], {"select": {"name": "B"}})
        self.assertEqual(
            properties["Industry Assessment"],
            {
                "rich_text": [
                    {
                        "text": {
                            "content": "Contracted repeat demand supports retention; equipment needs and local price competition temper the opportunity."
                        }
                    }
                ]
            },
        )
        forbidden = {
            "Industry Outlook",
            "Porter's Five Forces",
            "ETA Quality",
            "Industry Numeric Score",
            "Confidence",
            "Sources",
            "Research Date",
            "Regulatory Geography",
            "Financing",
        }
        self.assertTrue(forbidden.isdisjoint(properties))
        self.assertEqual(
            set(["Sub-industry", "Industry Score", "Industry Assessment"]) & set(properties),
            {"Sub-industry", "Industry Score", "Industry Assessment"},
        )
        self.assertIn(properties["Industry Score"]["select"]["name"], {"A", "B", "C", "D"})
        self.assertLessEqual(len(properties["Industry Assessment"]["rich_text"][0]["text"]["content"].split()), 35)


class IndustryAssessmentTests(unittest.TestCase):
    def test_default_provider_is_live_and_requires_explicit_enablement(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = configured_research_provider()
            with self.assertRaises(ProviderConfigurationError):
                provider.research(IndustryResearchInput("Commercial Laundry", "Commercial Laundry", "United States", date(2026, 7, 23)))

    def test_static_provider_is_explicit_and_not_current_verified_research(self):
        with patch.dict("os.environ", {"DEAL_FINDER_RESEARCH_PROVIDER": "static"}, clear=True):
            provider = configured_research_provider()
            research = provider.research(IndustryResearchInput("Commercial Laundry", "Commercial Laundry", "United States", date(2026, 7, 23)))
            self.assertEqual(research["provider"], "static")
            self.assertEqual(research["research_status"], "static_template")

    def test_live_evidence_is_converted_to_structured_research(self):
        research_input = IndustryResearchInput("Commercial Laundry", "Commercial Laundry", "United States", date(2026, 7, 23))
        research = build_research_from_evidence(research_input, _source_documents())
        self.assertEqual(research["provider"], "live")
        self.assertEqual(research["normalized_subindustry"], "Commercial Laundry")
        self.assertEqual(research["regulatory_geography"], "United States")
        self.assertIn("industry_outlook_scores", research)
        self.assertIn("porters_force_scores", research)
        self.assertIn("eta_quality_scores", research)
        self.assertTrue(all(source["url"].startswith("https://") for source in research["sources"]))

    def test_live_sources_and_dates_are_retained(self):
        research = build_research_from_evidence(
            IndustryResearchInput("Commercial Laundry", "Commercial Laundry", "United States", date(2026, 7, 23)),
            _source_documents(),
        )
        first = research["sources"][0]
        self.assertEqual(first["title"], "BLS Outlook")
        self.assertEqual(first["publisher"], "U.S. Bureau of Labor Statistics")
        self.assertEqual(first["publication_date"], "2026-04-01")
        self.assertEqual(first["data_period"], "2024-2034")

    def test_missing_required_evidence_lowers_confidence(self):
        research = build_research_from_evidence(
            IndustryResearchInput("Commercial Laundry", "Commercial Laundry", "United States", date(2026, 7, 23)),
            [_source_documents()[0]],
        )
        self.assertEqual(research["confidence"], "low")
        self.assertTrue(research["missing_evidence"])

    def test_invalid_live_response_is_not_cached(self):
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            result = assess_listing_industries(
                [Listing(title="Commercial laundry route", source="A")],
                process_date=date(2026, 7, 23),
                cache_path=cache_path,
                research_provider=InvalidLiveProvider(),
            )
            assessment = next(iter(result.values()))
            self.assertIn(assessment.grade, {"C", "D"})
            self.assertEqual(IndustryResearchCache(cache_path)._read(), {})

    def test_live_provider_uses_fetcher_and_returns_structured_research(self):
        provider = LiveIndustryResearchProvider(fetcher=FakeFetcher(_source_documents()), enabled=True)
        research = provider.research(IndustryResearchInput("Commercial Laundry", "Commercial Laundry", "United States", date(2026, 7, 23)))
        self.assertEqual(research["provider"], "live")
        self.assertEqual(research["research_status"], "verified")

    def test_equivalent_listings_receive_same_normalized_subindustry(self):
        first = Listing(title="Commercial laundry route", source="A", description="linen service")
        second = Listing(title="Uniform rental and linen route", source="B", description="commercial laundry")
        self.assertEqual(classify_subindustry(first).name, "Commercial Laundry")
        self.assertEqual(classify_subindustry(second).name, "Commercial Laundry")

    def test_broad_or_uncertain_classification_cannot_receive_a_or_b(self):
        classification = SubindustryClassification("B2B Services", "B2B Services", "low", broad_or_uncertain=True)
        record = score_industry(classification, "United States", _research_with_ratings(5), date(2026, 7, 23))
        self.assertEqual(record["industry_grade"], "C")

    def test_component_and_total_scores_are_capped(self):
        classification = SubindustryClassification("SaaS", "SaaS", "medium")
        record = score_industry(classification, "United States", _research_with_ratings(9), date(2026, 7, 23))
        self.assertLessEqual(record["industry_outlook_score"], 40)
        self.assertLessEqual(record["porters_five_forces_score"], 30)
        self.assertLessEqual(record["eta_acquisition_quality_score"], 30)
        self.assertLessEqual(record["industry_score"], 100)

    def test_a_requires_component_minimums(self):
        classification = SubindustryClassification("SaaS", "SaaS", "medium")
        research = _research_with_ratings(5)
        for score in research["eta_quality_scores"].values():
            score["rating"] = 2
        record = score_industry(classification, "United States", research, date(2026, 7, 23))
        self.assertNotEqual(record["industry_grade"], "A")

    def test_any_porter_force_rated_one_prevents_a(self):
        classification = SubindustryClassification("SaaS", "SaaS", "medium")
        research = _research_with_ratings(5)
        research["porters_force_scores"]["buyer_power"]["rating"] = 1
        record = score_industry(classification, "United States", research, date(2026, 7, 23))
        self.assertNotEqual(record["industry_grade"], "A")

    def test_entry_barriers_capex_fragmentation_and_labor_are_distinct(self):
        research = _research_with_ratings(3)
        research["porters_force_scores"]["threat_of_new_entrants"] = {
            "rating": 5,
            "weight": 6,
            "rationale": "High capital requirements deter new entrants.",
        }
        research["eta_quality_scores"]["economics_cash_conversion"] = {
            "rating": 2,
            "weight": 8.4,
            "rationale": "High capex weakens cash conversion.",
        }
        research["eta_quality_scores"]["fragmentation_acquisition_supply"] = {
            "rating": 5,
            "weight": 6,
            "rationale": "Fragmentation improves acquisition supply.",
        }
        research["porters_force_scores"]["competitive_rivalry"] = {
            "rating": 2,
            "weight": 6,
            "rationale": "Fragmentation still creates bidding pressure.",
        }
        research["porters_force_scores"]["supplier_power"] = {
            "rating": 2,
            "weight": 6,
            "rationale": "Labor scarcity increases supplier power.",
        }
        research["eta_quality_scores"]["transferability_operational_risk"] = {
            "rating": 2,
            "weight": 7.2,
            "rationale": "Labor scarcity increases transferability risk.",
        }
        record = score_industry(SubindustryClassification("Commercial Laundry", "Commercial Laundry", "medium"), "United States", research)
        self.assertEqual(record["porters_force_scores"]["threat_of_new_entrants"]["rating"], 5)
        self.assertEqual(record["eta_quality_scores"]["economics_cash_conversion"]["rating"], 2)
        self.assertEqual(record["eta_quality_scores"]["fragmentation_acquisition_supply"]["rating"], 5)
        self.assertEqual(record["porters_force_scores"]["competitive_rivalry"]["rating"], 2)
        self.assertNotEqual(
            record["porters_force_scores"]["supplier_power"]["rationale"],
            record["eta_quality_scores"]["transferability_operational_risk"]["rationale"],
        )

    def test_matching_listings_trigger_one_research_operation(self):
        with TemporaryDirectory() as tmpdir:
            provider = CountingResearchProvider(_research_with_ratings(4))
            listings = [
                Listing(title="Commercial laundry route", source="A", listing_url="https://example.com/a"),
                Listing(title="Commercial laundry and linen service", source="B", listing_url="https://example.com/b"),
            ]
            result = assess_listing_industries(
                listings,
                process_date=date(2026, 7, 23),
                cache_path=Path(tmpdir) / "cache.json",
                research_provider=provider,
            )
            self.assertEqual(provider.call_count, 1)
            self.assertEqual(len(result), 2)

    def test_concurrent_processing_does_not_create_duplicate_cache_records(self):
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            provider = CountingResearchProvider(_research_with_ratings(4))

            def run_once():
                return assess_listing_industries(
                    [Listing(title="Commercial laundry route", source="A")],
                    process_date=date(2026, 7, 23),
                    cache_path=cache_path,
                    research_provider=provider,
                )

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: run_once(), range(2)))

            self.assertEqual(provider.call_count, 1)
            self.assertEqual(len(IndustryResearchCache(cache_path)._read()), 1)
            self.assertEqual([next(iter(result.values())).subindustry for result in results], ["Commercial Laundry", "Commercial Laundry"])

    def test_valid_cache_entry_is_revalidated_and_reused(self):
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache_key = build_cache_key("Commercial Laundry", "United States")
            record = score_industry(
                SubindustryClassification("Commercial Laundry", "Commercial Laundry", "medium"),
                "United States",
                _research_with_ratings(4),
                date(2026, 7, 23),
            )
            record["next_review_date"] = "2026-07-30"
            record["last_regulatory_check_at"] = datetime(2026, 7, 23, tzinfo=UTC).isoformat()
            record["last_news_check_at"] = datetime(2026, 7, 23, tzinfo=UTC).isoformat()
            IndustryResearchCache(cache_path).set(cache_key, record)
            provider = CountingResearchProvider(_research_with_ratings(2))
            assess_listing_industries(
                [Listing(title="Commercial laundry", source="A")],
                process_date=date(2026, 7, 24),
                cache_path=cache_path,
                research_provider=provider,
            )
            self.assertEqual(provider.call_count, 0)

    def test_stale_cache_and_methodology_mismatch_refresh(self):
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache_key = build_cache_key("Commercial Laundry", "United States")
            old_record = score_industry(
                SubindustryClassification("Commercial Laundry", "Commercial Laundry", "medium"),
                "United States",
                _research_with_ratings(2),
                date(2026, 7, 1),
            )
            old_record["next_review_date"] = "2026-07-02"
            old_record["last_regulatory_check_at"] = (datetime(2026, 7, 1, tzinfo=UTC) - timedelta(days=9)).isoformat()
            old_record["last_news_check_at"] = (datetime(2026, 7, 1, tzinfo=UTC) - timedelta(days=9)).isoformat()
            old_record["scoring_methodology_version"] = "old"
            IndustryResearchCache(cache_path).set(cache_key, old_record)
            provider = CountingResearchProvider(_research_with_ratings(4))
            assess_listing_industries(
                [Listing(title="Commercial laundry", source="A")],
                process_date=date(2026, 7, 23),
                cache_path=cache_path,
                research_provider=provider,
            )
            self.assertEqual(provider.call_count, 1)

    def test_regulatory_changes_trigger_rescoring(self):
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache_key = build_cache_key("Commercial Laundry", "United States")
            record = score_industry(
                SubindustryClassification("Commercial Laundry", "Commercial Laundry", "medium"),
                "United States",
                _research_with_ratings(2),
                date(2026, 7, 23),
            )
            record["next_review_date"] = "2026-07-30"
            record["last_regulatory_check_at"] = datetime(2026, 7, 23, tzinfo=UTC).isoformat()
            record["last_news_check_at"] = datetime(2026, 7, 23, tzinfo=UTC).isoformat()
            record["material_development_requires_rescore"] = True
            IndustryResearchCache(cache_path).set(cache_key, record)
            provider = CountingResearchProvider(_research_with_ratings(4))
            assess_listing_industries(
                [Listing(title="Commercial laundry", source="A")],
                process_date=date(2026, 7, 23),
                cache_path=cache_path,
                research_provider=provider,
            )
            self.assertEqual(provider.call_count, 1)

    def test_live_failure_uses_valid_cache_when_regulatory_batch_check_fails(self):
        with TemporaryDirectory() as tmpdir:
            cache_path = Path(tmpdir) / "cache.json"
            cache_key = build_cache_key("Physical Therapy", "New York")
            record = score_industry(
                SubindustryClassification("Physical Therapy", "Physical Therapy", "medium"),
                "New York",
                _research_with_ratings(4),
                date(2026, 7, 23),
            )
            record["next_review_date"] = "2026-07-30"
            record["last_regulatory_check_at"] = datetime(2026, 7, 23, tzinfo=UTC).isoformat()
            record["last_news_check_at"] = datetime(2026, 7, 23, tzinfo=UTC).isoformat()
            IndustryResearchCache(cache_path).set(cache_key, record)
            result = assess_listing_industries(
                [Listing(title="Physical therapy clinic", source="A", location="New York")],
                process_date=date(2026, 7, 23),
                cache_path=cache_path,
                research_provider=FailingResearchProvider(),
            )
            self.assertEqual(next(iter(result.values())).subindustry, "Physical Therapy")

    def test_different_regulatory_geographies_create_separate_cache_records(self):
        with TemporaryDirectory() as tmpdir:
            provider = CountingResearchProvider(_research_with_ratings(4))
            listings = [
                Listing(title="Physical therapy clinic", source="A", location="New York"),
                Listing(title="Physical therapy clinic", source="B", location="Remote"),
            ]
            assess_listing_industries(
                listings,
                process_date=date(2026, 7, 23),
                cache_path=Path(tmpdir) / "cache.json",
                research_provider=provider,
            )
            self.assertEqual(provider.call_count, 2)

    def test_company_financials_do_not_alter_industry_grade(self):
        with TemporaryDirectory() as tmpdir:
            provider = CountingResearchProvider(_research_with_ratings(4))
            cache_path = Path(tmpdir) / "cache.json"
            listings = [
                Listing(title="Commercial laundry", source="A", asking_price=1, cash_flow=1),
                Listing(title="Commercial laundry", source="B", asking_price=6_000_000, cash_flow=2_000_000),
            ]
            result = assess_listing_industries(listings, process_date=date(2026, 7, 23), cache_path=cache_path, research_provider=provider)
            self.assertEqual(len({assessment.grade for assessment in result.values()}), 1)

    def test_research_failure_does_not_fail_batch(self):
        with TemporaryDirectory() as tmpdir:
            result = assess_listing_industries(
                [Listing(title="Unknown niche service", source="A")],
                process_date=date(2026, 7, 23),
                cache_path=Path(tmpdir) / "cache.json",
                research_provider=FailingResearchProvider(),
            )
            assessment = next(iter(result.values()))
            self.assertIn(assessment.grade, {"C", "D"})
            self.assertIn("Limited current evidence", assessment.assessment)


class CountingResearchProvider:
    def __init__(self, response):
        self.response = response
        self.call_count = 0
        self.lock = Lock()

    def research(self, research_input: IndustryResearchInput):
        with self.lock:
            self.call_count += 1
        return self.response


class FailingResearchProvider:
    def research(self, research_input: IndustryResearchInput):
        raise RuntimeError("research unavailable")


def _research_with_ratings(rating: int):
    research = {
        "provider": "live",
        "normalized_industry": "Mock Industry",
        "normalized_subindustry": "Mock Subindustry",
        "regulatory_geography": "United States",
        "research_timestamp": datetime(2026, 7, 23, tzinfo=UTC).isoformat(),
        "current_direction": "stable",
        "assessment": "Recurring demand and favorable supply dynamics support quality; competition and labor availability remain the primary risks.",
        "confidence": "medium",
        "research_status": "verified",
        "missing_evidence": [],
        "recent_developments": [],
        "sources": [
            {
                "title": "Mock authoritative source",
                "publisher": "U.S. Government",
                "publication_date": "2026-01-01",
                "data_period": "2025",
                "source_type": "government_dataset",
                "url": "https://example.gov/source",
            }
        ],
        "industry_outlook_scores": {
            "long_term_demand": {"rating": rating, "weight": 12, "finding": "Demand outlook.", "rationale": "Demand outlook."},
            "current_momentum": {"rating": rating, "weight": 8, "finding": "Current momentum.", "rationale": "Current momentum."},
            "regulatory_policy": {"rating": rating, "weight": 8, "finding": "Regulation.", "rationale": "Regulation."},
            "structural_tailwinds": {"rating": rating, "weight": 4, "finding": "Tailwinds.", "rationale": "Tailwinds."},
            "cyclicality_resilience": {"rating": rating, "weight": 4, "finding": "Resilience.", "rationale": "Resilience."},
            "disruption_obsolescence": {"rating": rating, "weight": 4, "finding": "Disruption.", "rationale": "Disruption."},
        },
        "porters_force_scores": {
            "threat_of_new_entrants": {"rating": rating, "weight": 6, "finding": "Entrants.", "rationale": "Entrants."},
            "buyer_power": {"rating": rating, "weight": 6, "finding": "Buyer power.", "rationale": "Buyer power."},
            "supplier_power": {"rating": rating, "weight": 6, "finding": "Supplier power.", "rationale": "Supplier power."},
            "threat_of_substitutes": {"rating": rating, "weight": 6, "finding": "Substitutes.", "rationale": "Substitutes."},
            "competitive_rivalry": {"rating": rating, "weight": 6, "finding": "Rivalry.", "rationale": "Rivalry."},
        },
        "eta_quality_scores": {
            "recurring_repeatable_revenue": {"rating": rating, "weight": 8.4, "finding": "Repeat demand.", "rationale": "Repeat demand."},
            "economics_cash_conversion": {"rating": rating, "weight": 8.4, "finding": "Economics.", "rationale": "Economics."},
            "transferability_operational_risk": {"rating": rating, "weight": 7.2, "finding": "Transferability.", "rationale": "Transferability."},
            "fragmentation_acquisition_supply": {"rating": rating, "weight": 6, "finding": "Supply.", "rationale": "Supply."},
        },
    }
    return research


class InvalidLiveProvider:
    def research(self, research_input: IndustryResearchInput):
        return {"provider": "live", "confidence": "high"}


class FakeFetcher:
    def __init__(self, documents):
        self.documents = documents

    def fetch(self, research_input: IndustryResearchInput):
        return self.documents


def _source_documents():
    return [
        SourceDocument(
            title="BLS Outlook",
            publisher="U.S. Bureau of Labor Statistics",
            publication_date="2026-04-01",
            data_period="2024-2034",
            source_type="government_dataset",
            url="https://www.bls.gov/ooh/",
            text="Employment outlook projected to grow with recurring demand, wages and labor shortage pressure.",
        ),
        SourceDocument(
            title="Census Quarterly Services",
            publisher="U.S. Census Bureau",
            publication_date="2026-06-01",
            data_period="latest four quarters",
            source_type="government_dataset",
            url="https://www.census.gov/services/index.html",
            text="Quarter revenue and annual services data show growth and stable current momentum.",
        ),
        SourceDocument(
            title="Federal Register Search",
            publisher="Federal Register",
            publication_date="2026-07-01",
            data_period="latest rules",
            source_type="regulator",
            url="https://www.federalregister.gov/",
            text="Final rule and licensing regulation evidence reviewed for compliance exposure.",
        ),
        SourceDocument(
            title="BEA Industry Data",
            publisher="U.S. Bureau of Economic Analysis",
            publication_date="2026-05-01",
            data_period="latest annual",
            source_type="government_dataset",
            url="https://www.bea.gov/data",
            text="Competition, market share concentration, barriers, automation and digital substitutes are considered.",
        ),
    ]


if __name__ == "__main__":
    unittest.main()
