"""
remit-lens — remittance comparison engine.

Compares corridors (USD→KES, GBP→KES, EUR→KES, CAD→KES) across providers
and surfaces the true cost: fee + exchange rate spread + transfer time.

Provider data is fetched from public rate APIs where available,
or from manually maintained rate tables updated daily. All data is
clearly timestamped and labelled ESTIMATED until verified against live quotes.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import urllib.request
import json


# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class Quote:
    """A single provider's quote for a transfer."""
    provider: str               # e.g. "Wise", "Remitly", "WorldRemit"
    send_currency: str          # "USD"
    receive_currency: str       # "KES"
    send_amount: float          # amount sender pays
    receive_amount: float       # amount recipient gets (in KES)
    fee: float                  # explicit fee in send_currency
    exchange_rate: float        # rate applied (KES per send_currency unit)
    mid_market_rate: float      # real mid-market rate at time of quote
    spread_percent: float       # (mid_market_rate - exchange_rate) / mid_market_rate * 100
    transfer_time: str          # "instant", "minutes", "1-3 hours", "1-3 days"
    delivery_method: str        # "M-Pesa", "Bank deposit", "Cash pickup"
    estimated: bool = True      # True = rate-table estimate; False = live API quote
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    url: str = ""               # deep link to initiate transfer on provider website

    @property
    def true_cost_percent(self) -> float:
        """Total cost as % of send amount: fee + exchange spread."""
        fee_percent = (self.fee / self.send_amount) * 100 if self.send_amount > 0 else 0
        return round(fee_percent + self.spread_percent, 2)

    @property
    def kes_per_dollar_effective(self) -> float:
        """Effective rate including fee (what you'd get if fee were charged in KES)."""
        if self.send_amount <= 0:
            return 0.0
        net_send = self.send_amount - self.fee
        return round(self.receive_amount / net_send, 2) if net_send > 0 else 0.0

    def __repr__(self) -> str:
        return (
            f"Quote({self.provider}: send {self.send_currency} {self.send_amount:.2f} "
            f"→ KES {self.receive_amount:,.0f}, "
            f"fee={self.fee:.2f}, spread={self.spread_percent:.1f}%, "
            f"true_cost={self.true_cost_percent:.2f}%, "
            f"time={self.transfer_time})"
        )


@dataclass
class Comparison:
    """Result of comparing multiple providers for a given corridor and amount."""
    send_currency: str
    receive_currency: str
    send_amount: float
    mid_market_rate: float
    quotes: list[Quote]
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def best_rate(self) -> Quote | None:
        """Provider with highest receive_amount (best for recipient)."""
        return max(self.quotes, key=lambda q: q.receive_amount) if self.quotes else None

    @property
    def fastest(self) -> Quote | None:
        """Provider with fastest transfer (instant or minutes preferred)."""
        order = {"instant": 0, "minutes": 1, "1-3 hours": 2, "hours": 3, "1-3 days": 4, "days": 5}
        if not self.quotes:
            return None
        return min(self.quotes, key=lambda q: order.get(q.transfer_time, 99))

    @property
    def most_trusted(self) -> Quote | None:
        """Provider score: best true_cost among providers with M-Pesa delivery."""
        mpesa_quotes = [q for q in self.quotes if "M-Pesa" in q.delivery_method]
        if not mpesa_quotes:
            return self.best_rate
        return min(mpesa_quotes, key=lambda q: q.true_cost_percent)

    def ranked(self) -> list[Quote]:
        """All quotes sorted by true cost (ascending = best deal first)."""
        return sorted(self.quotes, key=lambda q: q.true_cost_percent)


# ── Exchange rate fetching ────────────────────────────────────────────────────

def get_mid_market_rate(from_currency: str, to_currency: str = "KES") -> float:
    """Fetch mid-market exchange rate from Open Exchange Rates (free, no key needed via Frankfurter).

    Uses api.frankfurter.app — ECB rates, updated daily, free, no API key.
    Falls back to a hardcoded recent rate if the API is unavailable.
    """
    FALLBACKS = {
        ("USD", "KES"): 129.50,
        ("GBP", "KES"): 164.20,
        ("EUR", "KES"): 140.80,
        ("CAD", "KES"): 95.30,
        ("AED", "KES"): 35.25,
        ("AUD", "KES"): 84.60,
    }
    try:
        url = f"https://api.frankfurter.app/latest?from={from_currency}&to={to_currency}"
        req = urllib.request.Request(url, headers={"User-Agent": "remit-lens/0.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        rate = data["rates"].get(to_currency)
        if rate and isinstance(rate, (int, float)) and rate > 0:
            return float(rate)
    except Exception:
        pass
    return FALLBACKS.get((from_currency, to_currency), 0.0)


# ── Provider rate tables ──────────────────────────────────────────────────────
# Rates are estimated from publicly listed provider rates, updated manually.
# Each entry: (spread_percent, fixed_fee_usd_equiv, transfer_time, delivery_methods)
# spread_percent = how much worse than mid-market their exchange rate typically is
# These are ESTIMATES. Always verify on the provider website before sending money.

_PROVIDER_PROFILES: dict[str, dict] = {
    "Wise": {
        "spread_pct": 0.55,          # Wise is known for near-mid-market rates
        "fee_type": "percent+fixed",
        "fee_pct": 0.41,             # ~0.41% of send amount
        "fee_fixed": 0.0,
        "time": "minutes",
        "delivery": ["M-Pesa", "Bank deposit"],
        "url_template": "https://wise.com/send#payInMethod=CARD&sendAmount={amount}&sourceCurrency={from}&targetCurrency=KES",
        "notes": "Best rate, M-Pesa delivery, slightly slower than instant",
    },
    "Remitly": {
        "spread_pct": 1.2,
        "fee_type": "tiered",
        "fee_pct": 0.0,
        "fee_fixed": 3.99,           # Varies by tier; economy is cheaper, express costs more
        "time": "instant",
        "delivery": ["M-Pesa", "Bank deposit"],
        "url_template": "https://www.remitly.com/us/en/kenya",
        "notes": "Instant to M-Pesa. Economy tier is cheaper but slower.",
    },
    "WorldRemit": {
        "spread_pct": 1.8,
        "fee_type": "fixed",
        "fee_pct": 0.0,
        "fee_fixed": 3.99,
        "time": "minutes",
        "delivery": ["M-Pesa", "Bank deposit", "Cash pickup"],
        "url_template": "https://www.worldremit.com/en/send-money/to-kenya",
        "notes": "Wider network, cash pickup at major towns",
    },
    "Western Union": {
        "spread_pct": 3.5,
        "fee_type": "tiered",
        "fee_pct": 0.0,
        "fee_fixed": 5.00,           # Can be higher; varies by payment method
        "time": "minutes",
        "delivery": ["M-Pesa", "Cash pickup", "Bank deposit"],
        "url_template": "https://www.westernunion.com/us/en/send-money/app/start",
        "notes": "High spread; useful mainly for cash pickup in remote areas",
    },
    "Sendwave": {
        "spread_pct": 1.0,
        "fee_type": "zero",
        "fee_pct": 0.0,
        "fee_fixed": 0.0,            # No fees; makes money entirely on spread
        "time": "instant",
        "delivery": ["M-Pesa"],
        "url_template": "https://www.sendwave.com/",
        "notes": "Zero fee, instant M-Pesa. Spread slightly wider than Wise.",
    },
    "Mukuru": {
        "spread_pct": 2.1,
        "fee_type": "fixed",
        "fee_pct": 0.0,
        "fee_fixed": 4.50,
        "time": "1-3 hours",
        "delivery": ["Cash pickup", "Bank deposit"],
        "url_template": "https://www.mukuru.com/ke/",
        "notes": "Strong East Africa footprint; popular for cash collection",
    },
    "LemFi": {
        "spread_pct": 0.8,
        "fee_type": "percent",
        "fee_pct": 0.5,
        "fee_fixed": 0.0,
        "time": "minutes",
        "delivery": ["M-Pesa", "Bank deposit"],
        "url_template": "https://lemfi.com/",
        "notes": "Newer provider; competitive rates for diaspora Africans",
    },
}


# ── Comparison engine ─────────────────────────────────────────────────────────

def compare(
    send_amount: float,
    from_currency: str = "USD",
    to_currency: str = "KES",
    providers: list[str] | None = None,
) -> Comparison:
    """Compare remittance providers for a given send amount and corridor.

    Args:
        send_amount: Amount to send in from_currency.
        from_currency: ISO 4217 code (USD, GBP, EUR, CAD, AED, AUD).
        to_currency: Always KES for current version.
        providers: Optional subset of providers to compare (default: all).

    Returns:
        Comparison with ranked quotes. Check .best_rate, .fastest, .most_trusted.

    Example:
        result = compare(200, from_currency="USD")
        for q in result.ranked():
            print(q)
    """
    mid_rate = get_mid_market_rate(from_currency, to_currency)
    if mid_rate <= 0:
        raise ValueError(f"Could not get exchange rate for {from_currency}→{to_currency}")

    active_providers = providers or list(_PROVIDER_PROFILES.keys())
    quotes = []

    for name in active_providers:
        if name not in _PROVIDER_PROFILES:
            continue
        p = _PROVIDER_PROFILES[name]

        # Calculate fee in from_currency
        if p["fee_type"] == "zero":
            fee = 0.0
        elif p["fee_type"] == "percent":
            fee = send_amount * p["fee_pct"] / 100
        elif p["fee_type"] == "percent+fixed":
            fee = (send_amount * p["fee_pct"] / 100) + p["fee_fixed"]
        else:  # fixed or tiered
            fee = p["fee_fixed"]

        # Their exchange rate (spread below mid-market)
        their_rate = mid_rate * (1 - p["spread_pct"] / 100)

        # Recipient gets
        net_send = send_amount - fee
        receive_amount = net_send * their_rate if net_send > 0 else 0.0

        quotes.append(Quote(
            provider=name,
            send_currency=from_currency,
            receive_currency=to_currency,
            send_amount=send_amount,
            receive_amount=round(receive_amount, 2),
            fee=round(fee, 2),
            exchange_rate=round(their_rate, 4),
            mid_market_rate=round(mid_rate, 4),
            spread_percent=round(p["spread_pct"], 2),
            transfer_time=p["time"],
            delivery_method=", ".join(p["delivery"]),
            url=p.get("url_template", "").format(
                amount=int(send_amount), **{"from": from_currency}
            ),
            estimated=True,
        ))

    return Comparison(
        send_currency=from_currency,
        receive_currency=to_currency,
        send_amount=send_amount,
        mid_market_rate=mid_rate,
        quotes=quotes,
    )
