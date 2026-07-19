from __future__ import annotations

from deal_finder_ai.models import Listing, ScoreResult


def executive_summary(listing: Listing, score: ScoreResult) -> str:
    price = _money(listing.asking_price)
    cash_flow = _money(listing.cash_flow)
    revenue = _money(listing.annual_revenue)
    financing = listing.financing or "Financing details unavailable"
    seller_financing = "Seller financing is mentioned." if listing.seller_financing_offered else "Seller financing is not mentioned."

    return (
        f"{listing.title} is a {listing.industry or 'business'} listing in "
        f"{listing.location or 'an unavailable location'} from {listing.source}. "
        f"Asking price is {price}; annual revenue is {revenue}; cash flow/SDE/EBITDA is {cash_flow}. "
        f"{seller_financing} {financing}. "
        f"Score: {score.score}/100. {score.explanation}."
    )


def _money(value: int | None) -> str:
    if value is None:
        return "unavailable"
    return f"${value:,.0f}"

