"""
remit-lens unit tests.
Exchange rate API tests use fallback rates (no network calls required).
"""
import pytest
from unittest.mock import patch
from remit.compare import (
    Quote, Comparison, compare, get_mid_market_rate, _PROVIDER_PROFILES
)


# ── Quote calculations ────────────────────────────────────────────────────────

class TestQuote:
    def _make(self, **kwargs):
        defaults = dict(
            provider="Wise", send_currency="USD", receive_currency="KES",
            send_amount=200.0, receive_amount=25_600.0,
            fee=0.82, exchange_rate=128.5, mid_market_rate=129.5,
            spread_percent=0.77, transfer_time="minutes",
            delivery_method="M-Pesa, Bank deposit",
        )
        defaults.update(kwargs)
        return Quote(**defaults)

    def test_true_cost_combines_fee_and_spread(self):
        q = self._make(send_amount=200.0, fee=0.82, spread_percent=0.55)
        # fee% = 0.82/200 = 0.41%; spread=0.55%; total ≈ 0.96%
        assert 0.9 < q.true_cost_percent < 1.1

    def test_zero_fee_provider_cost_is_spread_only(self):
        q = self._make(fee=0.0, spread_percent=1.0)
        assert abs(q.true_cost_percent - 1.0) < 0.01

    def test_kes_per_dollar_effective(self):
        q = self._make(send_amount=200.0, fee=0.0, receive_amount=25_900.0)
        assert q.kes_per_dollar_effective == pytest.approx(129.5, rel=0.01)

    def test_repr_contains_provider(self):
        q = self._make()
        assert "Wise" in repr(q)


# ── Comparison ranking ────────────────────────────────────────────────────────

class TestComparison:
    def _make_comparison(self):
        quotes = [
            Quote("Wise", "USD", "KES", 200, 25_900, 0.82, 128.5, 129.5,
                  0.55, "minutes", "M-Pesa"),
            Quote("Remitly", "USD", "KES", 200, 25_500, 3.99, 127.2, 129.5,
                  1.2, "instant", "M-Pesa"),
            Quote("Western Union", "USD", "KES", 200, 24_800, 5.0, 125.0, 129.5,
                  3.5, "minutes", "Cash pickup"),
        ]
        return Comparison("USD", "KES", 200, 129.5, quotes)

    def test_best_rate_is_highest_receive_amount(self):
        c = self._make_comparison()
        assert c.best_rate.provider == "Wise"

    def test_fastest_prefers_instant(self):
        c = self._make_comparison()
        assert c.fastest.provider == "Remitly"  # "instant" wins over "minutes"

    def test_most_trusted_picks_best_mpesa_option(self):
        c = self._make_comparison()
        # Both Wise and Remitly deliver to M-Pesa; Wise has lower true cost
        assert c.most_trusted.provider == "Wise"

    def test_ranked_ascending_by_true_cost(self):
        c = self._make_comparison()
        costs = [q.true_cost_percent for q in c.ranked()]
        assert costs == sorted(costs)

    def test_ranked_best_first(self):
        c = self._make_comparison()
        assert c.ranked()[0].provider == "Wise"


# ── Provider profiles ─────────────────────────────────────────────────────────

class TestProviderProfiles:
    def test_all_providers_have_required_fields(self):
        required = {"spread_pct", "fee_type", "fee_pct", "fee_fixed", "time", "delivery"}
        for name, profile in _PROVIDER_PROFILES.items():
            missing = required - profile.keys()
            assert not missing, f"{name} missing: {missing}"

    def test_spread_pct_is_positive(self):
        for name, p in _PROVIDER_PROFILES.items():
            assert p["spread_pct"] >= 0, f"{name} has negative spread"

    def test_fee_pct_in_valid_range(self):
        for name, p in _PROVIDER_PROFILES.items():
            assert 0 <= p["fee_pct"] <= 10, f"{name} fee_pct out of range"

    def test_sendwave_has_zero_fee(self):
        assert _PROVIDER_PROFILES["Sendwave"]["fee_type"] == "zero"
        assert _PROVIDER_PROFILES["Sendwave"]["fee_fixed"] == 0.0

    def test_wise_has_lowest_spread(self):
        wise_spread = _PROVIDER_PROFILES["Wise"]["spread_pct"]
        others = [p["spread_pct"] for n, p in _PROVIDER_PROFILES.items() if n != "Wise"]
        assert all(wise_spread <= o for o in others)


# ── Compare engine ────────────────────────────────────────────────────────────

class TestCompare:
    @patch("remit.compare.get_mid_market_rate", return_value=129.50)
    def test_compare_returns_all_providers(self, _mock):
        result = compare(200, "USD")
        assert len(result.quotes) == len(_PROVIDER_PROFILES)

    @patch("remit.compare.get_mid_market_rate", return_value=129.50)
    def test_compare_provider_subset(self, _mock):
        result = compare(200, "USD", providers=["Wise", "Remitly"])
        assert len(result.quotes) == 2
        names = {q.provider for q in result.quotes}
        assert names == {"Wise", "Remitly"}

    @patch("remit.compare.get_mid_market_rate", return_value=129.50)
    def test_all_quotes_marked_estimated(self, _mock):
        result = compare(100, "USD")
        assert all(q.estimated for q in result.quotes)

    @patch("remit.compare.get_mid_market_rate", return_value=129.50)
    def test_receive_amount_is_positive(self, _mock):
        result = compare(500, "USD")
        for q in result.quotes:
            assert q.receive_amount > 0

    @patch("remit.compare.get_mid_market_rate", return_value=129.50)
    def test_mid_market_rate_in_result(self, _mock):
        result = compare(200, "GBP")
        assert result.mid_market_rate == 129.50


# ── Fallback rate ─────────────────────────────────────────────────────────────

class TestMidMarketRate:
    @patch("urllib.request.urlopen", side_effect=Exception("network down"))
    def test_falls_back_gracefully(self, _mock):
        rate = get_mid_market_rate("USD", "KES")
        assert rate > 0  # returns hardcoded fallback

    @patch("urllib.request.urlopen", side_effect=Exception("network down"))
    def test_fallback_gbp_kes(self, _mock):
        rate = get_mid_market_rate("GBP", "KES")
        assert rate > 100  # GBP is worth more than 100 KES
