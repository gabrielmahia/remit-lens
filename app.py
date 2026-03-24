"""
remit-lens — Diaspora remittance comparison for Kenya.

Compares the true cost (fee + exchange rate spread) of sending money to Kenya
across major providers: Wise, Remitly, Sendwave, WorldRemit, Western Union, and others.
"""
import streamlit as st
from remit.compare import compare, _PROVIDER_PROFILES


@st.cache_data(ttl=86400)
def fetch_remittance_benchmark():
    """World Bank average cost of receiving remittances to Kenya — G20 benchmark."""
    try:
        import urllib.request as _ur, json as _jrm
        url = ("https://api.worldbank.org/v2/country/KE/indicator/SI.RMT.COST.OB.ZS"
               "?format=json&mrv=3&per_page=3")
        with _ur.urlopen(url, timeout=12) as r:
            d = _jrm.loads(r.read())
        entries = [e for e in (d[1] if len(d) > 1 else []) if e.get("value")]
        if entries:
            return {
                "cost_pct": round(entries[0]["value"], 2),
                "year":     entries[0].get("date", "?"),
                "g20_target": 3.0,
                "live": True,
            }
    except Exception:
        pass
    return {"cost_pct": 5.26, "year": "2023", "g20_target": 3.0, "live": False}

st.set_page_config(
    page_title="TumaPesa — Send Money to Kenya",
    page_icon="💸",
    layout="centered",
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.5rem;
    border-left: 4px solid #4CAF50;
}
.metric-card.best { border-left-color: #1a73e8; }
.metric-card.fast { border-left-color: #fbbc04; }
.badge {
    font-size: 0.7rem;
    background: #e8f5e9;
    color: #2e7d32;
    padding: 2px 7px;
    border-radius: 10px;
    margin-left: 5px;
}
.disclaimer {
    font-size: 0.78rem;
    color: #888;
    font-style: italic;
    margin-top: 0.5rem;
}
@media (max-width: 768px) {
    [data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; }
    [data-testid="stDataFrame"] { overflow-x: auto !important; }
    .stButton > button { width: 100% !important; min-height: 48px !important; }
}
    @media (max-width: 480px) {
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.15rem !important; }
        [data-testid="stMetricValue"] { font-size: 1rem !important; }
        .stButton > button { min-height: 52px !important; font-size: 0.95rem !important; }
    }

    /* Metric text — explicit colours, light + dark (both OS pref and Streamlit toggle) */
    [data-testid="stMetricLabel"]  { color: #444444 !important; font-size: 0.8rem !important; }
    [data-testid="stMetricValue"]  { color: #111111 !important; font-weight: 700 !important; }
    [data-testid="stMetricDelta"]  { color: #333333 !important; }
    @media (prefers-color-scheme: dark) {
        [data-testid="stMetricLabel"] { color: #aaaaaa !important; }
        [data-testid="stMetricValue"] { color: #f0f0f0 !important; }
        [data-testid="stMetricDelta"] { color: #cccccc !important; }
    }
    [data-theme="dark"] [data-testid="stMetricLabel"],
    .stApp[data-theme="dark"] [data-testid="stMetricLabel"] { color: #aaaaaa !important; }
    [data-theme="dark"] [data-testid="stMetricValue"],
    .stApp[data-theme="dark"] [data-testid="stMetricValue"] { color: #f0f0f0 !important; }
    [data-theme="dark"] [data-testid="stMetricDelta"],
    .stApp[data-theme="dark"] [data-testid="stMetricDelta"] { color: #cccccc !important; }

</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("💸 TumaPesa — Send Money to Kenya")
st.subheader("Find the best way to send money to Kenya")

st.warning(
    "⚠️ **ESTIMATES ONLY** — Exchange rates and fees are approximate, based on publicly "
    "listed provider rates. Always verify on the provider's website before sending. "
    "Rates change daily.",
    icon="⚠️",
)

# ── Inputs ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    send_amount = st.number_input(
        "Amount to send",
        min_value=10.0,
        max_value=10_000.0,
        value=200.0,
        step=50.0,
        format="%.0f",
    )

with col2:
    currency = st.selectbox(
        "Currency → KES",
        options=["USD", "GBP", "EUR", "CAD", "AUD", "AED"],
        index=0,
    )

# Provider filter
with st.expander("Filter providers"):
    all_providers = list(_PROVIDER_PROFILES.keys())
    selected = st.multiselect(
        "Show only:", all_providers, default=all_providers
    )

# ── Compute ───────────────────────────────────────────────────────────────────
from remit.compare import PROVIDER_CURRENCY_LIMITS

# Filter to providers that actually support this corridor
if selected:
    supported = [p for p in selected if currency in PROVIDER_CURRENCY_LIMITS.get(p, [currency])]
    if len(supported) < len(selected):
        unsupported = [p for p in selected if p not in supported]
        st.info(
            f"⚠️ {', '.join(unsupported)} {'does' if len(unsupported)==1 else 'do'} not list "
            f"{currency}→KES as a supported corridor. Showing supported providers only.",
            icon="ℹ️"
        )
else:
    supported = [p for p, currs in PROVIDER_CURRENCY_LIMITS.items() if currency in currs]

try:
    with st.spinner("Getting live exchange rate…"):
        result = compare(send_amount, from_currency=currency, providers=supported or None)
except Exception as e:
    st.error(f"Could not fetch rates: {e}")
    st.stop()

# Rate freshness indicator
is_fallback = "fallback" in result.rate_source
if is_fallback:
    st.warning(
        f"⚠️ Live rate unavailable — using a recent hardcoded fallback rate for "
        f"{currency}→KES. Verify on your provider's website before sending.",
        icon="⚠️"
    )
else:
    st.caption(f"📡 Mid-market rate sourced: {result.rate_source}")

# ── Headline cards ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Best options")

cards_html = '<div style="display:flex;flex-wrap:wrap;gap:0.75rem;margin-bottom:0.5rem;">'
highlight_cards = []
if result.best_rate:
    q = result.best_rate
    delta = q.receive_amount - (send_amount * result.mid_market_rate)
    link = f'<a href="{q.url}" target="_blank" style="font-size:0.8rem;color:#1a73e8;">Send with {q.provider} →</a>' if q.url else ""
    highlight_cards.append(
        f'<div style="flex:1 1 180px;min-width:160px;background:#e8f5e9;border-left:4px solid #1a73e8;'
        f'border-radius:8px;padding:1rem;">'
        f'<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:#555;margin-bottom:0.25rem;">💰 Best amount — {q.provider}</div>'
        f'<div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;">KES {q.receive_amount:,.0f}</div>'
        f'<div style="font-size:0.8rem;color:#2e7d32;margin-top:0.2rem;">+{delta:,.0f} vs mid-market</div>'
        f'{link}</div>'
    )
if result.fastest:
    q = result.fastest
    highlight_cards.append(
        f'<div style="flex:1 1 180px;min-width:160px;background:#fffde7;border-left:4px solid #fbbc04;'
        f'border-radius:8px;padding:1rem;">'
        f'<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:#555;margin-bottom:0.25rem;">⚡ Fastest — {q.provider}</div>'
        f'<div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;">KES {q.receive_amount:,.0f}</div>'
        f'<div style="font-size:0.8rem;color:#856404;margin-top:0.2rem;">{q.transfer_time}</div>'
        f'</div>'
    )
if result.most_trusted:
    q = result.most_trusted
    highlight_cards.append(
        f'<div style="flex:1 1 180px;min-width:160px;background:#e3f2fd;border-left:4px solid #4CAF50;'
        f'border-radius:8px;padding:1rem;">'
        f'<div style="font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;color:#555;margin-bottom:0.25rem;">📱 Best to M-Pesa — {q.provider}</div>'
        f'<div style="font-size:1.5rem;font-weight:800;color:#1a1a1a;">KES {q.receive_amount:,.0f}</div>'
        f'<div style="font-size:0.8rem;color:#c62828;margin-top:0.2rem;">{q.true_cost_percent:.1f}% true cost</div>'
        f'</div>'
    )
cards_html += "".join(highlight_cards) + "</div>"
st.markdown(cards_html, unsafe_allow_html=True)

# ── Mid-market context ────────────────────────────────────────────────────────
st.markdown("---")
mid_kes = send_amount * result.mid_market_rate
source_note = "via open.er-api.com" if "live" in result.rate_source else "fallback estimate"
st.caption(
    f"Mid-market rate: **1 {currency} = {result.mid_market_rate:.2f} KES** "
    f"({source_note}). "
    f"{currency} {send_amount:.0f} at mid-market = **KES {mid_kes:,.0f}**. "
    f"No provider gives you this rate — the gap is their margin."
)

# ── Full comparison table ─────────────────────────────────────────────────────
st.markdown("### All providers — ranked by true cost")

ranked = result.ranked()

table_data = []
for i, q in enumerate(ranked):
    savings_vs_worst = ranked[-1].receive_amount - q.receive_amount if ranked else 0
    row = {
        "Rank": f"#{i+1}",
        "Provider": q.provider,
        "You send": f"{currency} {q.send_amount:.0f}",
        "Fee": f"{currency} {q.fee:.2f}",
        "Rate": f"{q.exchange_rate:.2f}",
        "Recipient gets": f"KES {q.receive_amount:,.0f}",
        "True cost %": f"{q.true_cost_percent:.2f}%",
        "Speed": q.transfer_time,
        "Delivery": q.delivery_method,
    }
    table_data.append(row)

import pandas as pd
df = pd.DataFrame(table_data)
st.dataframe(df, use_container_width=True, hide_index=True)

# ── World Bank benchmark ─────────────────────────────────────────────────
_wb_rem = fetch_remittance_benchmark()
_src_lbl = "📡 World Bank live" if _wb_rem.get("live") else "📋 World Bank 2023"
st.info(
    f"**{_src_lbl} · Average cost to receive remittances to Kenya: "
    f"{_wb_rem['cost_pct']}% ({_wb_rem['year']})** — "
    f"G20 target is {_wb_rem['g20_target']}%. "
    f"Compare your provider's true cost % above against this benchmark."
)

# ── What "true cost" means ───────────────────────────────────────────────────
with st.expander("What is 'true cost %'?"):
    st.markdown("""
The **true cost %** combines two things providers charge you for:

1. **The explicit fee** — shown clearly (e.g. "we charge $3.99")
2. **The exchange rate spread** — hidden in the rate (e.g. mid-market is 129.50 KES/USD, 
   but they give you 126.00 KES/USD — that 2.7% difference is profit for them)

**True cost % = fee % + spread %**

The only way to compare providers fairly is to add both together. 
A "zero fee" provider often has a wider spread. A "best rate" provider may charge a high fee.
The provider with the lowest true cost % puts the most money in your family's hands.
    """)

# ── Disclaimer ────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div class="disclaimer">
Rates shown are estimates based on publicly listed provider rates and may differ from actual quotes.
Exchange rates are fetched from Frankfurter (ECB) and may be up to 24 hours old.
RemitLens is not affiliated with any provider. No transfers are processed through this tool.
Always verify on the provider's website before sending money.
</div>
""", unsafe_allow_html=True)
# -- Feedback sidebar ---------------------------------------------------------
with st.sidebar:
    st.markdown("---")
    st.markdown(
        "**Was this useful?**\n\n"
        "[:pencil: Leave feedback](https://docs.google.com/forms/d/e/1FAIpQLSff_cjR102HNUeYU428ROv56TScLBzsQRc1JTwY4wGizvTQKw/viewform) (2 min)\n\n"
        "[:bug: Report a bug](https://github.com/gabrielmahia/remit-lens/issues/new)\n\n"
        "---\n"
        "*Built by [Gabriel Mahia](https://aikungfu.dev)*\n\n"
        "[Back to all tools](https://gabrielmahia.github.io)"
    )

