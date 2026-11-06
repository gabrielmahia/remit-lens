"""Smoke tests for live data functions — remit-lens."""
import sys

import pytest

sys.path.insert(0, "/tmp/remit-lens")
from unittest import mock


def test_fetch_remittance_benchmark_returns_dict_on_success():
    """Verify fetch_remittance_benchmark returns dict when API succeeds."""
    with mock.patch('urllib.request.urlopen') as mu:
        mu.return_value.__enter__ = lambda s: s
        mu.return_value.__exit__ = mock.Mock(return_value=False)
        mu.return_value.read = mock.Mock(return_value=b'<rss><channel></channel></rss>')
        app = pytest.importorskip("app")  # skip only if the app cannot be imported here; any exception from the call fails the test
        fn = getattr(app.fetch_remittance_benchmark, "__wrapped__", app.fetch_remittance_benchmark)
        result = fn()
    assert isinstance(result, dict)

def test_fetch_remittance_benchmark_graceful_on_network_failure():
    """Verify fetch_remittance_benchmark does not raise when network is unavailable."""
    with mock.patch('urllib.request.urlopen', side_effect=Exception('network down')):
        app = pytest.importorskip("app")  # skip only if the app cannot be imported here; any exception from the call fails the test
        fn = getattr(app.fetch_remittance_benchmark, "__wrapped__", app.fetch_remittance_benchmark)
        result = fn()
    assert isinstance(result, dict)