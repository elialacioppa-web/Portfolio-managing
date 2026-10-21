# portfolio_analyzer.py
# Software completo di analisi portafoglio finanziario
# Esegui con: streamlit run portfolio_analyzer.py

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings("ignore")

# ====================== CONFIGURAZIONE PAGINA ======================
st.set_page_config(
    page_title="Portfolio Analyzer Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 Portfolio Analyzer Pro")
st.markdown("**Software completo di gestione e analisi finanziaria personale**")

# ====================== SIDEBAR - INPUT PORTAFOGLIO ======================
st.sidebar.header("⚙️ Configurazione Portafoglio")

# Esempio di portafoglio predefinito (puoi modificarlo)
default_portfolio = {
    "Ticker": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ", "GLD"],
    "Quantità": [15, 10, 8, 5, 12, 20, 15, 10],
    "Prezzo Medio (€)": [180.5, 410.0, 165.0, 175.0, 120.0, 520.0, 450.0, 185.0]
}

uploaded_file = st.sidebar.file_uploader("Carica CSV portafoglio (opzionale)", type=["csv"])

if uploaded_file:
    portfolio_df = pd.read_csv(uploaded_file)
else:
    portfolio_df = pd.DataFrame(default_portfolio)

# Editor interattivo
edited_df = st.sidebar.data_editor(
    portfolio_df,
    num_rows="dynamic",
    use_container_width=True,
    key="portfolio_editor"
)

# Periodo di analisi
period = st.sidebar.selectbox(
    "Periodo storico",
    options=["1y", "2y", "3y", "5y", "10y", "max"],
    index=2
)

# Benchmark
benchmark = st.sidebar.selectbox("Benchmark", ["SPY", "^GSPC", "QQQ", "VT"], index=0)

# ====================== FUNZIONI DI SUPPORTO ======================

@st.cache_data(ttl=3600)
def get_price_data(tickers, period="3y"):
    """Scarica prezzi storici"""
    data = yf.download(tickers, period=period, progress=False, auto_adjust=True)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return data.dropna(how="all")

@st.cache_data(ttl=3600)
def get_info(ticker):
    """Informazioni base azienda"""
    try:
        info = yf.Ticker(ticker).info
        return {
            "Nome": info.get("longName", ticker),
            "Settore": info.get("sector", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "Market Cap": info.get("marketCap", 0),
            "PE": info.get("trailingPE", None),
            "Forward PE": info.get("forwardPE", None),
            "PEG": info.get("pegRatio", None),
            "ROE": info.get("returnOnEquity", None),
            "Debt/Equity": info.get("debtToEquity", None),
            "Profit Margin": info.get("profitMargins", None),
            "Revenue Growth": info.get("revenueGrowth", None),
            "Beta": info.get("beta", None),
            "Dividend Yield": info.get("dividendYield", None),
        }
    except:
        return {}

@st.cache_data(ttl=86400)
def get_financials(ticker):
    """Scarica bilanci"""
    try:
        t = yf.Ticker(ticker)
        return {
            "income": t.income_stmt,
            "balance": t.balance_sheet,
            "cashflow": t.cashflow
        }
    except:
        return None

def calculate_metrics(returns):
    """Calcola metriche di performance e rischio"""
    if returns.empty or returns.isna().all():
        return {}
    
    ann_factor = 252
    total_return = (1 + returns).prod() - 1
    ann_return = (1 + total_return) ** (ann_factor / len(returns)) - 1
    volatility = returns.std() * np.sqrt(ann_factor)
    sharpe = ann_return / volatility if volatility > 0 else 0
    
    # Sortino
    downside = returns[returns < 0]
    downside_std = downside.std() * np.sqrt(ann_factor) if len(downside) > 0 else 0
    sortino = ann_return / downside_std if downside_std > 0 else 0
    
    # Max Drawdown
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    drawdown = (cum - peak) / peak
    max_dd = drawdown.min()
    
    # VaR 95%
    var_95 = np.percentile(returns, 5)
    
    return {
        "Rendimento Totale": total_return,
        "Rendimento Annualizzato": ann_return,
        "Volatilità Ann.": volatility,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Max Drawdown": max_dd,
        "VaR 95% (giornaliero)": var_95
    }

# ====================== CALCOLO PORTAFOGLIO ======================

tickers = edited_df["Ticker"].tolist()
quantities = edited_df["Quantità"].astype(float).tolist()
avg_prices = edited_df["Prezzo Medio (€)"].astype(float).tolist()

if not tickers:
    st.warning("Inserisci almeno un ticker nel portafoglio.")
    st.stop()

# Scarica dati
with st.spinner("Scarico dati di mercato..."):
    prices = get_price_data(tickers + [benchmark], period=period)
    prices = prices.dropna(axis=1, how="all")

# Prezzi correnti
current_prices = prices.iloc[-1]
valid_tickers = [t for t in tickers if t in current_prices.index]

# Calcolo valore attuale e pesi
portfolio_data = []
total_value = 0

for i, t in enumerate(tickers):
    if t in current_prices.index:
        qty = quantities[i]
        avg = avg_prices[i]
        curr = current_prices[t]
        value = qty * curr
        cost = qty * avg
        pnl = value - cost
        pnl_pct = (curr / avg - 1) if avg > 0 else 0
        total_value += value
        portfolio_data.append({
            "Ticker": t,
            "Quantità": qty,
            "Prezzo Medio": avg,
            "Prezzo Attuale": curr,
            "Valore Attuale": value,
            "Costo": cost,
            "P&L €": pnl,
            "P&L %": pnl_pct
        })

port_df = pd.DataFrame(portfolio_data)
if not port_df.empty:
    port_df["Peso %"] = port_df["Valore Attuale"] / total_value * 100

# ====================== TABS PRINCIPALI ======================

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboard Portafoglio",
    "📈 Performance & Rischio",
    "🏢 Analisi Aziendale",
    "🌍 Contesto Macro",
    "📰 News",
    "🔄 Ribilanciamento"
])

# ---------- TAB 1: DASHBOARD ----------
with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valore Totale Portafoglio", f"€ {total_value:,.0f}")
    if not port_df.empty:
        total_pnl = port_df["P&L €"].sum()
        total_pnl_pct = total_pnl / port_df["Costo"].sum() if port_df["Costo"].sum() > 0 else 0
        col2.metric("P&L Totale", f"€ {total_pnl:,.0f}", f"{total_pnl_pct:.1%}")
        col3.metric("Numero Posizioni", len(port_df))
        col4.metric("Peso Medio", f"{port_df['Peso %'].mean():.1f}%")

    st.subheader("Posizioni attuali")
    st.dataframe(
        port_df.style.format({
            "Prezzo Medio": "€{:.2f}",
            "Prezzo Attuale": "€{:.2f}",
            "Valore Attuale": "€{:,.0f}",
            "Costo": "€{:,.0f}",
            "P&L €": "€{:,.0f}",
            "P&L %": "{:.1%}",
            "Peso %": "{:.1f}%"
        }),
        use_container_width=True
    )

    # Grafico pesi
    if not port_df.empty:
        fig_pie = px.pie(port_df, values="Valore Attuale", names="Ticker", title="Allocazione attuale")
        st.plotly_chart(fig_pie, use_container_width=True)

# ---------- TAB 2: PERFORMANCE & RISCHIO ----------
with tab2:
    st.subheader("Andamento storico del portafoglio vs Benchmark")

    # Costruisci serie portafoglio
    returns = prices[valid_tickers].pct_change().dropna()
    weights = port_df.set_index("Ticker")["Peso %"] / 100
    weights = weights.reindex(valid_tickers).fillna(0)
    weights = weights / weights.sum()

    port_returns = (returns * weights).sum(axis=1)
    bench_returns = prices[benchmark].pct_change().dropna()

    # Allinea date
    common_idx = port_returns.index.intersection(bench_returns.index)
    port_returns = port_returns.loc[common_idx]
    bench_returns = bench_returns.loc[common_idx]

    cum_port = (1 + port_returns).cumprod()
    cum_bench = (1 + bench_returns).cumprod()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum_port.index, y=cum_port, name="Portafoglio"))
    fig.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench, name=benchmark))
    fig.update_layout(title="Performance cumulata", yaxis_title="Crescita (base 1)")
    st.plotly_chart(fig, use_container_width=True)

    # Metriche
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Metriche Portafoglio**")
        metrics_port = calculate_metrics(port_returns)
        for k, v in metrics_port.items():
            st.write(f"{k}: **{v:.2%}**" if "Ratio" not in k and "VaR" not in k else f"{k}: **{v:.2f}**")

    with col_b:
        st.markdown(f"**Metriche {benchmark}**")
        metrics_bench = calculate_metrics(bench_returns)
        for k, v in metrics_bench.items():
            st.write(f"{k}: **{v:.2%}**" if "Ratio" not in k and "VaR" not in k else f"{k}: **{v:.2f}**")

    # Matrice di correlazione
    st.subheader("Matrice di correlazione")
    corr = returns.corr()
    fig_corr = px.imshow(corr, text_auto=".2f", aspect="auto", color_continuous_scale="RdBu_r")
    st.plotly_chart(fig_corr, use_container_width=True)

# ---------- TAB 3: ANALISI AZIENDALE ----------
with tab3:
    selected_ticker = st.selectbox("Seleziona azienda", valid_tickers)

    if selected_ticker:
        info = get_info(selected_ticker)
        st.subheader(f"{info.get('Nome', selected_ticker)}")

        cols = st.columns(4)
        cols[0].metric("Settore", info.get("Settore", "N/A"))
        cols[1].metric("PE Trailing", f"{info.get('PE', 0):.1f}" if info.get("PE") else "N/A")
        cols[2].metric("ROE", f"{info.get('ROE', 0)*100:.1f}%" if info.get("ROE") else "N/A")
        cols[3].metric("Beta", f"{info.get('Beta', 0):.2f}" if info.get("Beta") else "N/A")

        # Bilanci
        fins = get_financials(selected_ticker)
        if fins:
            st.markdown("### Conto Economico (ultimi periodi)")
            st.dataframe(fins["income"].head(12) if fins["income"] is not None else pd.DataFrame())

            st.markdown("### Stato Patrimoniale")
            st.dataframe(fins["balance"].head(12) if fins["balance"] is not None else pd.DataFrame())

            st.markdown("### Cash Flow")
            st.dataframe(fins["cashflow"].head(12) if fins["cashflow"] is not None else pd.DataFrame())
        else:
            st.info("Dati di bilancio non disponibili per questo ticker.")

# ---------- TAB 4: MACRO ----------
with tab4:
    st.subheader("Contesto Macroeconomico (dati Yahoo / indicatori principali)")
    st.info("Per dati FRED più ricchi aggiungi una API key gratuita di FRED (St. Louis Fed).")

    # Indicatori proxy via Yahoo
    macro_tickers = {
        "S&P 500": "^GSPC",
        "Nasdaq": "^IXIC",
        "VIX": "^VIX",
        "Treasury 10Y": "^TNX",
        "Oro": "GC=F",
        "Petrolio": "CL=F",
        "EUR/USD": "EURUSD=X"
    }

    macro_data = get_price_data(list(macro_tickers.values()), period="2y")
    macro_data.columns = list(macro_tickers.keys())

    # Performance recenti
    perf_1m = macro_data.pct_change(21).iloc[-1]
    perf_3m = macro_data.pct_change(63).iloc[-1]
    perf_ytd = macro_data.pct_change(len(macro_data) - 1).iloc[-1]  # approssimato

    macro_perf = pd.DataFrame({
        "1 Mese": perf_1m,
        "3 Mesi": perf_3m,
        "Periodo": perf_ytd
    })
    st.dataframe(macro_perf.style.format("{:.1%}"), use_container_width=True)

    # Grafico VIX e S&P
    fig_macro = make_subplots(specs=[[{"secondary_y": True}]])
    fig_macro.add_trace(go.Scatter(x=macro_data.index, y=macro_data["S&P 500"], name="S&P 500"), secondary_y=False)
    fig_macro.add_trace(go.Scatter(x=macro_data.index, y=macro_data["VIX"], name="VIX", line=dict(color="red")), secondary_y=True)
    fig_macro.update_layout(title="S&P 500 vs VIX")
    st.plotly_chart(fig_macro, use_container_width=True)

# ---------- TAB 5: NEWS ----------
with tab5:
    st.subheader("News finanziarie (ultime notizie via Yahoo)")
    news_ticker = st.selectbox("Ticker per news", valid_tickers, key="news_ticker")
    try:
        news = yf.Ticker(news_ticker).news
        if news:
            for item in news[:8]:
                title = item.get("title", "")
                link = item.get("link", "")
                publisher = item.get("publisher", "")
                st.markdown(f"**[{title}]({link})** — *{publisher}*")
        else:
            st.info("Nessuna news trovata.")
    except:
        st.warning("Impossibile recuperare le news in questo momento.")

# ---------- TAB 6: RIBILANCIAMENTO ----------
with tab6:
    st.subheader("Suggerimenti di ribilanciamento")
    st.markdown("Inserisci i **pesi target** desiderati (somma = 100%)")

    target_weights = {}
    cols = st.columns(min(4, len(valid_tickers)))
    for i, t in enumerate(valid_tickers):
        with cols[i % 4]:
            current_w = port_df.loc[port_df["Ticker"] == t, "Peso %"].values[0] if t in port_df["Ticker"].values else 0
            target_weights[t] = st.number_input(f"{t} (%)", min_value=0.0, max_value=100.0, value=float(current_w), step=1.0)

    total_target = sum(target_weights.values())
    if abs(total_target - 100) > 0.5:
        st.warning(f"La somma dei pesi target è {total_target:.1f}% (dovrebbe essere 100%)")
    else:
        # Calcolo differenze
        rebal = []
        for t in valid_tickers:
            curr_w = port_df.loc[port_df["Ticker"] == t, "Peso %"].values[0]
            tgt = target_weights[t]
            diff = tgt - curr_w
            value_diff = (diff / 100) * total_value
            rebal.append({
                "Ticker": t,
                "Peso Attuale %": curr_w,
                "Peso Target %": tgt,
                "Differenza %": diff,
                "Importo da muovere €": value_diff
            })
        rebal_df = pd.DataFrame(rebal)
        st.dataframe(rebal_df.style.format({
            "Peso Attuale %": "{:.1f}%",
            "Peso Target %": "{:.1f}%",
            "Differenza %": "{:+.1f}%",
            "Importo da muovere €": "€{:+,.0f}"
        }), use_container_width=True)

        st.success("Valori positivi = da acquistare | Valori negativi = da vendere")

# ====================== FOOTER ======================
st.markdown("---")
st.caption("Portfolio Analyzer Pro • Dati forniti da Yahoo Finance • Solo a scopo informativo e didattico • Non costituisce consulenza finanziaria")
