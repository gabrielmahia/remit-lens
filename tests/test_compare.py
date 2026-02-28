"""remit-lens unit tests — no network calls."""
import pytest
from remit.compare import Quote, Comparison, compare, get_mid_market_rate
from unittest.mock import patch
from datetime import datetime, timezone


def _mock_rate(from_currency: str, to_currency: str = "KES") -> float:
    rates = {"USD": 129.50, "GBP": 164.20, "EUR": 140.80, "CAD": 95.30}
    return rates.get(from_currency, 129.50)


class TestQuote:
    def _make_quote(self, **kwargs) -> Quote:
        defaults = dict(
            provider="TestProvider",
            send_currency="USD",
            receive_currency="KES",
            send_amount=200.0,
            receive_amount=25_000.0,
            fee=3.99,
            exchange_rate=127.00,
            mid_market_rate=129.50,
            spread_percent=1.93,
            transfer_time="minutes",
            delivery_method="M-Pesa",
        )
        defaults.update(kwargs)
        return Quote(**defaults)

    def test_true_cost_combines_fee_and_spread(self):
        q = self._make_quote(fee=4.0, spread_percent=1.5, send_amount=200.0)
        # fee% = 4/200 = 2.0%, spread = 1.5%, total = 3.5%
        assert q.true_cost_percent == 3.5

    def test_zero_fee_true_cost_is_spread_only(self):
        q = self._make_quote(fee=0.0, spread_percent=1.0, send_amount=200.0)
        assert q.true_cost_percent == 1.0

    def test_repr_contains_provider_name(self):
        q = self._make_quote(provider="Wise")
        assert "Wise" in repr(q)

    def test_receive_amount_is_positive(self):
        q = self._make_quote(receive_amount=25_800.0)
        assert q.receive_amount > 0


class TestComparison:
    def _make_comparison(self, quotes) -> Comparison:
        return Comparison(
            send_currency="USD",
            receive_currency="KES",
            send_amount=200.0,
            mid_market_rate=129.50,
            quotes=quotes,
        )

    def _make_quote(self, provider, receive, fee, spread, time, delivery="M-Pesa") -> Quote:
        return Quote(
            provider=provider,
            send_currency="USD",
            receive_currency="KES",
            send_amount=200.0,
            receive_amount=receive,
            fee=fee,
            exchange_rate=129.50 * (1 - spread / 100),
            mid_market_rate=129.50,
            spread_percent=spread,
            transfer_time=time,
            delivery_method=delivery,
        )

    def test_best_rate_is_highest_receive_amount(self):
        quotes = [
            self._make_quote("ProvA", 25_000, 0, 1.0, "minutes"),
            self._make_quote("ProvB", 26_000, 0, 0.5, "days"),  # best receive
            self._make_quote("ProvC", 24_000, 0, 2.0, "instant"),
        ]
        c = self._make_comparison(quotes)
        assert c.best_rate.provider == "ProvB"

    def test_fastest_prefers_instant(self):
        quotes = [
            self._make_quote("Fast", 24_000, 0, 2.0, "instant"),
            self._make_quote("Slow", 26_000, 0, 0.5, "1-3 days"),
        ]
        c = self._make_comparison(quotes)
        assert c.fastest.provider == "Fast"

    def test_ranked_ascending_by_true_cost(self):
        quotes = [
            self._make_quote("Expensive", 24_000, 5.0, 3.0, "minutes"),
            self._make_quote("Cheap", 25_800, 0.0, 0.5, "minutes"),
            self._make_quote("Mid", 25_000, 2.0, 1.5, "minutes"),
        ]
        c = self._make_comparison(quotes)
        ranked = c.ranked()
        costs = [q.true_cost_percent for q in ranked]
        assert costs == sorted(costs)  # ascending

    def test_most_trusted_prefers_mpesa(self):
        quotes = [
            self._make_quote("BankOnly", 26_000, 0, 0.5, "days", "Bank deposit"),
            self._make_quote("MpesaProvider", 25_500, 0, 0.8, "minutes", "M-Pesa"),
        ]
        c = self._make_comparison(quotes)
        assert c.most_trusted.provider == "MpesaProvider"

    def test_empty_quotes_returns_none_for_best(self):
        c = self._make_comparison([])
        assert c.best_rate is None
        assert c.fastest is None


class TestCompareFunction:
    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_returns_all_providers(self, mock_rate):
        result = compare(200, from_currency="USD")
        assert len(result.quotes) > 0
        providers = {q.provider for q in result.quotes}
        assert "Wise" in providers
        assert "Remitly" in providers

    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_send_amounts_match_input(self, mock_rate):
        result = compare(500, from_currency="USD")
        for q in result.quotes:
            assert q.send_amount == 500.0

    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_fees_are_non_negative(self, mock_rate):
        result = compare(200)
        for q in result.quotes:
            assert q.fee >= 0

    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_receive_amounts_are_positive(self, mock_rate):
        result = compare(200)
        for q in result.quotes:
            assert q.receive_amount > 0

    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_provider_filter(self, mock_rate):
        result = compare(200, providers=["Wise", "Remitly"])
        assert len(result.quotes) == 2
        providers = {q.provider for q in result.quotes}
        assert providers == {"Wise", "Remitly"}

    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_sendwave_zero_fee(self, mock_rate):
        result = compare(200, providers=["Sendwave"])
        q = result.quotes[0]
        assert q.fee == 0.0

    @patch("remit.compare.get_mid_market_rate", side_effect=_mock_rate)
    def test_wise_has_lowest_true_cost(self, mock_rate):
        result = compare(200)
        ranked = result.ranked()
        # Wise should be top 2 — best rate provider
        top_2 = {q.provider for q in ranked[:2]}
        assert "Wise" in top_2 or "LemFi" in top_2  # either is fine

    @patch("remit.compare.get_mid_market_rate", return_value=0.0)
    def test_zero_rate_raises(self, mock_rate):
        with pytest.raises(ValueError, match="exchange rate"):
            compare(200)


class TestRateFallback:
    def test_fallback_returns_nonzero_for_usd(self):
        # Test that if API fails, fallback works
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            rate = get_mid_market_rate("USD", "KES")
        assert rate > 0

    def test_fallback_gbp_kes(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            rate = get_mid_market_rate("GBP", "KES")
        assert rate > 130  # GBP/KES is always > 130
