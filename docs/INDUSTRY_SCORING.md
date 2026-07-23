# Industry Scoring

The industry assessment methodology is implemented in `deal_finder_ai/industry_assessment.py` as `eta-industry-v1`.

## 100-Point Methodology

The internal industry score is 0 to 100:

- Industry Outlook: 40 points.
- Porter’s Five Forces: 30 points.
- ETA Operating and Acquisition Quality: 30 points.

The component dimensions and weights are:

Industry Outlook:

- Long-term demand: 12.
- Current momentum: 8.
- Regulatory/policy environment: 8.
- Structural tailwinds: 4.
- Cyclicality/resilience: 4.
- Disruption/obsolescence: 4.

Porter’s Five Forces:

- Threat of new entrants: 6.
- Buyer power: 6.
- Supplier power: 6.
- Threat of substitutes: 6.
- Competitive rivalry: 6.

ETA Operating and Acquisition Quality:

- Recurring/repeatable revenue: 8.4.
- Economics/cash conversion: 8.4.
- Transferability/operational risk: 7.2.
- Fragmentation/acquisition supply: 6.

Each dimension uses a 1-to-5 rating multiplied by its weight.

## A-D Thresholds

The base grade thresholds are:

- `A`: 80+.
- `B`: 65 to 79.
- `C`: 45 to 64.
- `D`: below 45.

Guardrails can cap the grade:

- An `A` requires at least 28/40 for Industry Outlook, 21/30 for Porter’s Five Forces, and 21/30 for ETA Quality.
- Any Porter force rated `1` prevents an `A`.
- A severe structural problem prevents an `A`.
- Low-confidence research prevents an `A`.
- Broad or uncertain classification cannot receive `A` or `B`; it is capped at `C`.
- Provisional fallback assessments are capped at `C`.

## Classification Confidence

The classifier scans listing title, description, broad industry, and raw source fields. Specific keyword matches receive medium confidence. Broad fallback mappings receive low confidence and are marked broad or uncertain.

The classifier’s `Sub-industry` output must be one of the approved labels in `acquisition_criteria.json`. Tests enforce this.

## Evidence Standards

Live research requires structured evidence with:

- Normalized sub-industry.
- Regulatory geography.
- Research timestamp.
- Current direction.
- Confidence.
- Assessment.
- At least one authoritative source.
- Required source metadata: title, publisher, publication date, data period, URL, and source type.
- All required weighted dimensions with 1-to-5 ratings, findings, and rationales.

The live provider currently fetches public authoritative sources such as BLS, Census, BEA, Federal Register, and relevant New York regulatory pages when geography requires it. Marketplace listings are not treated as industry research evidence.

If live research is not enabled or fails, the system uses conservative static/provisional fallback behavior rather than failing the whole batch. Invalid live responses are not cached as verified research.

## Geography Handling

Most sub-industries use `United States` as regulatory geography.

The system uses `New York` when a listing appears to be in New York and belongs to a regulated category such as:

- Behavioral Health
- Day Care & Child Care Centers
- Other Transportation
- Physical Therapy
- Taxi & Limousine

Taxi and limousine listings in New York City use `New York City`.

## Caching and Freshness

Research records are cached in `.deal_finder_cache/industry_research_cache.json`, keyed by normalized sub-industry, regulatory geography, and methodology version.

A cached record is valid only when:

- The scoring methodology version matches.
- The next review date has not passed.
- Regulatory and news checks are present.
- Regulatory and news checks are no more than seven days old.

Stale records trigger fresh assessment. Cache files are ignored by git.

## Notion Outputs

Only three industry-assessment fields are written to Notion:

- `Sub-industry`: approved taxonomy label.
- `Industry Score`: one letter, `A`, `B`, `C`, or `D`.
- `Industry Assessment`: one concise sentence, capped at 35 words.

Internal numeric scores, components, source notes, confidence, dates, and cache metadata stay in code/runtime artifacts and are not written to Notion.

Note: older documentation or Notion column language may casually call the industry letter grade “Score.” The current Notion property name is `Industry Score`.
