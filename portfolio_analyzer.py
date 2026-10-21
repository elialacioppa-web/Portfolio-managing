# portfolio_analyzer.py
# Versione corretta - supporta CSV e Excel + mappatura colonne

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

st.set_page_config(
    page_title="Portfolio Analyzer Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📈 Portfolio Analyzer Pro")
st.markdown("**Software completo di gestione e analisi finanziaria personale**")

# ====================== SIDEBAR ======================
st.sidebar.header("⚙️ Configurazione Portafoglio")

uploaded_file = st.sidebar.file_uploader(
    "Carica portafoglio (CSV o Excel)",
    type=["csv", "xlsx", "xls"]
)

# Portafoglio di esempio (usato se non carichi nulla)
default_data = {
    "Ticker": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ"],
    "Quantità": [15, 10, 8, 5, 12, 20, 15],
    "Prezzo Medio (€)": [180.5, 410.0, 165.0, 175.0, 120.0, 520.0, 450.0]
}
default_df = pd.DataFrame(default_data)

portfolio_df = default_df.copy()

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            raw_df = pd.read_excel(uploaded_file)
        else:
            # Prova diversi separatori e encoding comuni
            try:
                raw_df = pd.read_csv(uploaded_file, sep=None, engine='python', encoding='utf-8')
            except:
                uploaded_file.seek(0)
                raw_df = pd.read_csv(uploaded_file, sep=';', encoding='latin1')
        
        st.sidebar.success(f"File caricato: {uploaded_file.name}")
        st.sidebar.write("Colonne trovate nel file:")
        st.sidebar.write(list(raw_df.columns))

        # ===== MAPPATURA COLONNE =====
        st.sidebar.markdown("### Mappa le colonne")
        col_options = ["-- Seleziona --"] + list(raw_df.columns)

        ticker_col = st.sidebar.selectbox("Colonna Ticker / Titolo / Isin", col_options, key="ticker_map")
        qty_col = st.sidebar.selectbox("Colonna Quantità / Shares / Pezzi", col_options, key="qty_map")
        price_col = st.sidebar.selectbox("Colonna Prezzo Medio / Prezzo di carico / PMC", col_options, key="price_map")

        if ticker_col != "-- Seleziona --" and qty_col != "-- Seleziona --" and price_col != "-- Seleziona --":
            portfolio_df = pd.DataFrame({
                "Ticker": raw_df[ticker_col].astype(str).str.strip().str.upper(),
                "Quantità": pd.to_numeric(raw_df[qty_col], errors='coerce'),
                "Prezzo Medio (€)": pd.to_numeric(raw_df[price_col], errors='coerce')
            }).dropna()
            
            # Pulisce eventuali ticker vuoti
            portfolio_df = portfolio_df[portfolio_df["Ticker"] != ""]
            portfolio_df = portfolio_df[portfolio_df["Quantità"] > 0]
            
            st.sidebar.success(f"Caricate {len(portfolio_df)} posizioni valide")
        else:
            st.sidebar.warning("Seleziona tutte e tre le colonne per continuare")
            portfolio_df = default_df.copy()

    except Exception as e:
        st.sidebar.error(f"Errore nella lettura del file: {e}")
        portfolio_df = default_df.copy()

# Editor interattivo
edited_df = st.sidebar.data_editor(
    portfolio_df,
    num_rows="dynamic",
    use_container_width=True,
    key="portfolio_editor"
)

period = st.sidebar.selectbox("Periodo storico", ["1y", "2y", "3y", "5y", "10y", "max"], index=2)
benchmark = st.sidebar.selectbox("Benchmark", ["SPY", "^GSPC", "QQQ", "VT", "IWDA.L"], index=0)

# ====================== FUNZIONI ======================

@st.cache_data(ttl=3600)
def get_price_data(tickers, period="3y"):
    if not tickers:
        return pd.DataFrame()
    data = yf.download(tickers, period=period, progress=False, auto_adjust=True)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return data.dropna(how="all")

@st.cache_data(ttl=3600)
def get_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "Nome": info.get("longName", ticker),
            "Settore": info.get("sector", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "Market Cap": info.get("marketCap", 0),
            "PE": info.get("trailingPE", None),
            "ROE": info.get("returnOnEquity", None),
            "Debt/Equity": info.get("debtToEquity", None),
            "Beta": info.get("beta", None),
            "Dividend Yield": info.get("dividendYield", None),
        }
    except:
        return {}

def calculate_metrics(returns):
    if returns.empty or returns.isna().all().all():
        return {}
    ann_factor = 252
    total_return = (1 + returns).prod() - 1
    ann_return = (1 + total_return) ** (ann_factor / len(returns)) - 1
    volatility = returns.std() * np.sqrt(ann_factor)
    sharpe = ann_return / volatility if volatility > 0 else 0
    downside = returns[returns < 0]
    downside_std = downside.std() * np.sqrt(ann_factor) if len(downside) > 0 else 0
    sortino = ann_return / downside_std if downside_std > 0 else 0
    cum = (1 + returns).cumprod()
    max_dd = ((cum - cum.cummax()) / cum.cummax()).min()
    var_95 = np.percentile(returns.dropna(), 5)
    return {
        "Rendimento Totale": total_return,
        "Rendimento Annualizzato": ann_return,
        "Volatilità Ann.": volatility,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Max Drawdown": max_dd,
        "VaR 95%": var_95
    }

# ====================== CALCOLI ======================

if edited_df.empty or "Ticker" not in edited_df.columns:
    st.warning("Nessun dato valido nel portafoglio. Usa l'editor o carica un file.")
    st.stop()

tickers = edited_df["Ticker"].astype(str).str.strip().str.upper().tolist()
quantities = pd.to_numeric(edited_df["Quantità"], errors='coerce').fillna(0).tolist()
avg_prices = pd.to_numeric(edited_df["Prezzo Medio (€)"], errors='coerce').fillna(0).tolist()

# Rimuove ticker vuoti
valid_pairs = [(t, q, p) for t, q, p in zip(tickers, quantities, avg_prices) if t and q > 0]
if not valid_pairs:
    st.warning("Nessuna posizione valida trovata.")
    st.stop()

tickers, quantities, avg_prices = zip(*valid_pairs)
tickers = list(tickers)

with st.spinner("Scarico dati di mercato..."):
    prices = get_price_data(tickers + [benchmark], period=period)

if prices.empty:
    st.error("Impossibile scaricare i prezzi. Controlla i ticker.")
    st.stop()

current_prices = prices.iloc[-1]
valid_tickers = [t for t in tickers if t in current_prices.index]

portfolio_data = []
total_value = 0.0

for i, t in enumerate(tickers):
    if t in current_prices.index:
        qty = quantities[i]
        avg = avg_prices[i]
        curr = float(current_prices[t])
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

# ====================== TABS ======================

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", 
    "📈 Performance & Rischio", 
    "🏢 Analisi Aziendale", 
    "🌍 Macro", 
    "🔄 Ribilanciamento"
])

with tab1:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valore Totale", f"€ {total_value:,.0f}")
    if not port_df.empty:
        total_pnl = port_df["P&L €"].sum()
        total_cost = port_df["Costo"].sum()
        total_pnl_pct = total_pnl / total_cost if total_cost > 0 else 0
        col2.metric("P&L Totale", f"€ {total_pnl:,.0f}", f"{total_pnl_pct:.1%}")
        col3.metric("Posizioni", len(port_df))
        col4.metric("Peso medio", f"{port_df['Peso %'].mean():.1f}%")

    st.subheader("Posizioni attuali")
    if not port_df.empty:
        st.dataframe(
            port_df.style.format({
                "Prezzo Medio": "€{:.2f}",
                "Prezzo Attuale": "€{:.2f}",
                "Valore Attuale": "€{:,.0f}",
                "Costo": "€{:,.0f}",
                "P&L €": "€{:+,.0f}",
                "P&L %": "{:+.1%}",
                "Peso %": "{:.1f}%"
            }),
            use_container_width=True
        )
        fig_pie = px.pie(port_df, values="Valore Attuale", names="Ticker", title="Allocazione")
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Nessuna posizione valida da mostrare.")

with tab2:
    st.subheader("Performance storica")
    if len(valid_tickers) > 0 and not port_df.empty:
        returns = prices[valid_tickers].pct_change().dropna()
        weights = port_df.set_index("Ticker")["Peso %"] / 100
        weights = weights.reindex(valid_tickers).fillna(0)
        weights = weights / weights.sum()
        port_returns = (returns * weights).sum(axis=1)
        bench_returns = prices[benchmark].pct_change().dropna()
        common = port_returns.index.intersection(bench_returns.index)
        port_returns = port_returns.loc[common]
        bench_returns = bench_returns.loc[common]

        cum_port = (1 + port_returns).cumprod()
        cum_bench = (1 + bench_returns).cumprod()

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cum_port.index, y=cum_port, name="Portafoglio"))
        fig.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench, name=benchmark))
        fig.update_layout(title="Crescita cumulata")
        st.plotly_chart(fig, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Portafoglio**")
            for k, v in calculate_metrics(port_returns).items():
                st.write(f"{k}: **{v:.2%}**" if abs(v) < 10 else f"{k}: **{v:.2f}**")
        with col_b:
            st.markdown(f"**{benchmark}**")
            for k, v in calculate_metrics(bench_returns).items():
                st.write(f"{k}: **{v:.2%}**" if abs(v) < 10 else f"{k}: **{v:.2f}**")

        st.subheader("Matrice di correlazione")
        corr = returns.corr()
        fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r")
        st.plotly_chart(fig_corr, use_container_width=True)

with tab3:
    if valid_tickers:
        selected = st.selectbox("Seleziona titolo", valid_tickers)
        info = get_info(selected)
        st.subheader(info.get("Nome", selected))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Settore", info.get("Settore", "N/A"))
        c2.metric("PE", f"{info.get('PE'):.1f}" if info.get("PE") else "N/A")
        c3.metric("ROE", f"{info.get('ROE')*100:.1f}%" if info.get("ROE") else "N/A")
        c4.metric("Beta", f"{info.get('Beta'):.2f}" if info.get("Beta") else "N/A")
    else:
        st.info("Nessun ticker valido")

with tab4:
    st.subheader("Indicatori di mercato")
    macro_map = {"S&P 500": "^GSPC", "Nasdaq": "^IXIC", "VIX": "^VIX", "Oro": "GC=F", "Petrolio": "CL=F"}
    macro_data = get_price_data(list(macro_map.values()), period="1y")
    if not macro_data.empty:
        macro_data.columns = list(macro_map.keys())
        st.line_chart(macro_data)

with tab5:
    st.subheader("Ribilanciamento")
    if not port_df.empty:
        target = {}
        cols = st.columns(min(4, len(valid_tickers)))
        for i, t in enumerate(valid_tickers):
            with cols[i % 4]:
                curr_w = float(port_df.loc[port_df["Ticker"] == t, "Peso %"].values[0])
                target[t] = st.number_input(f"{t} %", 0.0, 100.0, curr_w, 1.0)
        
        if abs(sum(target.values()) - 100) < 1:
            rebal = []
            for t in valid_tickers:
                curr = float(port_df.loc[port_df["Ticker"] == t, "Peso %"].values[0])
                diff = target[t] - curr
                rebal.append({
                    "Ticker": t,
                    "Attuale %": curr,
                    "Target %": target[t],
                    "Differenza %": diff,
                    "Importo €": (diff/100) * total_value
                })
            st.dataframe(pd.DataFrame(rebal).style.format({
                "Attuale %": "{:.1f}",
                "Target %": "{:.1f}",
                "Differenza %": "{:+.1f}",
                "Importo €": "€{:+,.0f}"
            }))
        else:
            st.warning("La somma dei pesi target deve essere circa 100%")

st.markdown("---")
st.caption("Portfolio Analyzer Pro • Solo a scopo informativo")
