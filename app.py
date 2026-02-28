"""
remit-lens — Diaspora remittance comparison for Kenya.

Compares the true cost (fee + exchange rate spread) of sending money to Kenya
across major providers: Wise, Remitly, Sendwave, WorldRemit, Western Union, and others.
"""
import streamlit as st
from remit.compare import compare, _PROVIDER_PROFILES

st.set_page_config(
    page_title="RemitLens — Send Money to Kenya",
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
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("💸 RemitLens")
st.subheader("Find the best way to send money to Kenya")

st.warning(
    "⚠️ **ESTIMATES ONLY** — Exchange rates and fees are approximate, based on publicly "
    "listed provider rates. Always verify on the provider's website before sending. "
    "Rates change daily.",
    icon="⚠️",
)

# ── Inputs ────────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([2, 1, 1])

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
        "Currency",
        options=["USD", "GBP", "EUR", "CAD", "AUD", "AED"],
        index=0,
    )

with col3:
    st.text_input("Recipient gets", value="KES", disabled=True)

# Provider filter
with st.expander("Filter providers"):
    all_providers = list(_PROVIDER_PROFILES.keys())
    selected = st.multiselect(
        "Show only:", all_providers, default=all_providers
    )

# ── Compute ───────────────────────────────────────────────────────────────────
try:
    with st.spinner("Getting live exchange rate…"):
        result = compare(send_amount, from_currency=currency, providers=selected or None)
except Exception as e:
    st.error(f"Could not fetch rates: {e}")
    st.stop()

# ── Headline cards ────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Best options")

c1, c2, c3 = st.columns(3)

if result.best_rate:
    with c1:
        q = result.best_rate
        delta = q.receive_amount - (send_amount * result.mid_market_rate)
        st.metric(
            f"💰 Best amount — {q.provider}",
            f"KES {q.receive_amount:,.0f}",
            delta=f"{delta:,.0f} vs mid-market",
            delta_color="normal",
        )
        if q.url:
            st.markdown(f"[Send with {q.provider} →]({q.url})")

if result.fastest:
    with c2:
        q = result.fastest
        st.metric(
            f"⚡ Fastest — {q.provider}",
            f"KES {q.receive_amount:,.0f}",
            delta=q.transfer_time,
            delta_color="off",
        )

if result.most_trusted:
    with c3:
        q = result.most_trusted
        st.metric(
            f"📱 Best to M-Pesa — {q.provider}",
            f"KES {q.receive_amount:,.0f}",
            delta=f"{q.true_cost_percent:.1f}% true cost",
            delta_color="inverse",
        )

# ── Mid-market context ────────────────────────────────────────────────────────
st.markdown("---")
mid_kes = send_amount * result.mid_market_rate
st.caption(
    f"Mid-market rate: **1 {currency} = {result.mid_market_rate:.2f} KES** "
    f"(via Frankfurter / ECB). "
    f"{currency} {send_amount:.0f} at mid-market = **KES {mid_kes:,.0f}**. "
    f"No provider charges this rate — the gap is their margin."
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
