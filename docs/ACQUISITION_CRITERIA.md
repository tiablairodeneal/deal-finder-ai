# Acquisition Criteria

This document reflects the criteria currently implemented in `acquisition_criteria.json`, `deal_finder_ai/scoring.py`, `deal_finder_ai/industry_assessment.py`, and the tests. Do not change this document without checking production code.

## Buy Box

- Location: New York State or fully online/remote.
- Asking price: `$1,000,000` to `$6,000,000`.
- Annual revenue: no minimum or maximum currently enforced.
- Cash flow/SDE/EBITDA: `$500,000` to `$2,000,000`.
- Seller financing: positive signal, not required.
- Must-have traits: none currently enforced.
- Promising score threshold: `75+`.
- Deal breakers: FedEx routes, FedEx P&D routes, pickup and delivery routes, Amazon FBA, FBA business, FBA brand.

Missing financial information is not guessed. Missing asking price or missing cash flow receives zero points for that category.

## Approved Industry and Sub-Industry Taxonomy

The current target list contains these approved labels:

- Business Services
- Commercial Laundry
- Conferences & Trade Shows
- Office Equipment Distribution
- Other Business Services
- Other Office
- Professional Services
- Other Professional Services
- Real Estate Services
- Security & Protection Services
- Staffing
- Construction & Building Services
- Building Materials & Supply
- Flooring
- Insulation & Coating
- Locksmiths
- Painting Business
- Specialty Trades
- Consumer Products & Services
- Clothing & Fashion
- Other Clothing & Fashion
- Personal Products & Services
- Other Personal Products & Services
- Education & Training
- Day Care & Child Care Centers
- Other Educational Services
- Schools
- Seminars
- Test Preparation
- Food & Beverage
- Agricultural Production
- Distilleries & Alcohol Production
- Food Production & Packaging
- Other Food & Beverage
- Vending Machines & Routes
- Healthcare & Wellness
- Behavioral Health
- Health Clubs, Gyms & Fitness Centers
- Other Health & Medical
- Physical Therapy
- Wellness & Supplements
- Home & Garden
- Household Maintenance
- Landscaping Services
- Nurseries & Garden Centers
- Other Home & Garden
- Hospitality, Entertainment & Leisure
- Art Galleries & Museums
- Other Entertainment & Leisure
- Sports Teams & Facilities
- Travel Agents
- Industrials & Manufacturing
- Industrial Services
- Manufacturing
- Textile & Materials Manufacturing
- Textiles
- Media & Communications
- Media & Content
- Other Media & Communications
- Print, Signage & Display
- Radio Stations
- Technology & Digital
- B2B
- E-Commerce & Digital
- E-Commerce & E-Tailers
- Internet Related
- Transportation & Logistics
- Auto Parts Recycling
- Other Transportation
- Parking
- Passenger Transport
- Taxi & Limousine

## Production Scoring Logic

The transparent buy-box score totals 100 points:

- Industry match: 20 points.
- Location match: 15 points.
- Asking price in range: 20 points.
- Cash flow/SDE/EBITDA in range: 25 points.
- Seller financing offered: 10 points.
- Core listing data completeness: 10 points.

A listing is marked `Promising` only when it reaches the configured threshold and passes core fit checks for industry, location, asking price, and cash flow/SDE/EBITDA.

Industry matching currently checks the listing’s broad `industry` value against the full target list. Sub-industry classification is used for industry assessment and Notion display, not as the only buy-box industry filter.

## Classifier Normalization

`deal_finder_ai/industry_assessment.py` now constrains `Sub-industry` output to the approved labels above. Examples:

- SaaS-like listings map to `Internet Related`.
- E-commerce brand listings map to `E-Commerce & E-Tailers`.
- Digital marketing agency listings map to `Other Business Services`.
- PR agency listings map to `Media & Content`.
- Specialty contractor listings map to `Specialty Trades`.
- Unknown fallback listings map conservatively to `Other Business Services` with low confidence.

## Mismatches and Limitations

- Annual revenue ranges are present in the criteria file as `null` min/max values but are not currently used in scoring.
- `must_have_traits` is an empty list and is not currently enforced.
- The `Industry` Notion property may still contain historical broad labels and option names. The production classifier writes approved labels to `Sub-industry`.
- Existing Notion rows created before classifier normalization may still contain older sub-industry labels until they are refreshed or backfilled.
- Industry matching uses simple substring logic against listing `industry`; it is intentionally transparent but not a full taxonomy engine.
