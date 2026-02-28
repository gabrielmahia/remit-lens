# RemitLens

**Find the best way to send money to Kenya.**

[![Tests](https://img.shields.io/badge/tests-19%20passing-brightgreen)](https://github.com/gabrielmahia/remit-lens/actions)
[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-ESTIMATES%20ONLY-orange)](#disclaimer)

Compares the **true cost** of sending money to Kenya across major remittance providers. True cost = fee + exchange rate spread — because a "zero fee" provider often charges through a worse exchange rate.

> ⚠️ **ESTIMATES ONLY** — Rates shown are approximate. Always verify on the provider website before sending money.

## Providers compared

Wise · Remitly · Sendwave · WorldRemit · Western Union · Mukuru · LemFi

## What it calculates

| Metric | What it is |
|--------|-----------|
| True cost % | Fee % + exchange spread % combined |
| Recipient gets | Amount in KES after all charges |
| Best to M-Pesa | Lowest true cost with M-Pesa delivery |
| Fastest | Provider with instant or minutes delivery |

## Run locally

```bash
git clone https://github.com/gabrielmahia/remit-lens
cd remit-lens
pip install -r requirements.txt
streamlit run app.py
```

## Corridors supported

USD → KES · GBP → KES · EUR → KES · CAD → KES · AUD → KES · AED → KES

Exchange rates via [Frankfurter](https://www.frankfurter.app) (ECB, updated daily, free).

## Roadmap

- [ ] Live rate APIs (Wise, Remitly have public rate endpoints)
- [ ] Historical rate tracking (chart the best rate over 30 days)
- [ ] Alert: notify when a rate crosses a threshold
- [ ] Nigeria, Ghana, Uganda corridors
- [ ] Browser extension for rate check on provider sites

## Architecture

```
remit/
  compare.py    ← core engine: Quote, Comparison, compare()
tests/
  test_compare.py  ← 19 tests, no network calls
app.py          ← Streamlit UI
```

## Contributing

Open an issue. PRs welcome, especially for:
- Live rate API integrations
- Additional corridors (Tanzania, Uganda, Nigeria)
- Additional providers

## License

CC BY-NC-ND 4.0 — personal and educational use free. Commercial use: contact@aikungfu.dev.

---

*Built by a Kenyan diaspora engineer who has sent money home too many times to count without knowing if he was getting a fair rate.*
