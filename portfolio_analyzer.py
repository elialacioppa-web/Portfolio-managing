# portfolio_analyzer.py
# Portfolio Analyzer Pro - Versione Resistente (Ottobre 2026)

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import warnings
warnings.filterwarnings("ignore")

# Librerie opzionali
try:
    import quantstats as qs
    qs.extend_pandas()
    HAS_QS = True
except:
    HAS_QS = False

try:
    from pypfopt import EfficientFrontier, risk_models, expected_returns
    HAS_PFP = True
except:
    HAS_PFP = False

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER

# ====================== CONFIG ======================
st.set_page_config(page_title="Portfolio Analyzer Pro", page_icon="📈", layout="wide")
st.markdown("""
<style>
    .stMetric {background-color: #f8f9fa; padding: 10px; border-radius: 8px;}
    h1, h2, h3 {color: #1e3a5f;}
</style>
""", unsafe_allow_html=True)

st.title("Portfolio Analyzer Pro")
st.caption("Versione resistente • Riconoscimento automatico ticker • Report PDF • Efficient Frontier")

# ====================== DIZIONARIO TICKER COMUNI ======================
TICKER_MAP = {
    "APPLE": "AAPL", "AAPL": "AAPL",
    "MICROSOFT": "MSFT", "MSFT": "MSFT",
    "AMAZON": "AMZN", "AMZN": "AMZN",
    "ALPHABET": "GOOGL", "GOOGLE": "GOOGL", "GOOGL": "GOOGL", "GOOG": "GOOG",
    "NVIDIA": "NVDA", "NVDA": "NVDA",
    "TESLA": "TSLA", "TSLA": "TSLA",
    "META": "META", "FACEBOOK": "META",
    "BERKSHIRE": "BRK-B", "BERKSHIRE HATHAWAY": "BRK-B", "BRK.B": "BRK-B", "BRK-B": "BRK-B",
    "COCA-COLA": "KO", "COCA COLA": "KO", "KO": "KO",
    "JPMORGAN": "JPM", "JPM": "JPM",
    "VISA": "V", "MASTERCARD": "MA",
    "JOHNSON": "JNJ", "JNJ": "JNJ",
    "PROCTER": "PG", "PG": "PG",
    "EXXON": "XOM", "XOM": "XOM",
    "UNITEDHEALTH": "UNH", "UNH": "UNH",
    "HOME DEPOT": "HD", "HD": "HD",
    "SPY": "SPY", "QQQ": "QQQ", "VOO": "VOO", "VTI": "VTI",
    "CORE MSCI WORLD": "URTH", "MSCI WORLD": "URTH", "IWDA": "IWDA.L", "SWDA": "SWDA.L",
    "CORE S&P 500": "CSPX.L", "S&P 500": "SPY",
    "FTSE ALL-WORLD": "VWRL.L", "ALL-WORLD": "VWRL.L",
    "HIGH DIVIDEND": "VHYL.L",
    "QUANTITATIVE STRATEGIES ESG": "EQQQ.L",  # esempio generico
    "AMEX": "AXP", "AMERICAN EXPRESS": "AXP",
}

def normalize_ticker(raw):
    """Prova a convertire un nome in ticker Yahoo Finance"""
    if pd.isna(raw):
        return None
    t = str(raw).strip().upper()
    # Rimuove caratteri strani
    t = t.replace(".", "-").replace(" ", " ")
    
    # Match esatto
    if t in TICKER_MAP:
        return TICKER_MAP[t]
    
    # Match parziale
    for key, value in TICKER_MAP.items():
        if key in t or t in key:
            return value
    
    # Se sembra già un ticker valido (3-5 lettere)
    if 1 <= len(t) <= 6 and t.replace("-", "").replace(".", "").isalnum():
        return t
    
    return t  # prova comunque

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("Profilo Cliente")
    client_name = st.text_input("Nome Cliente", value="Mario Rossi")
    risk_profile = st.selectbox("Profilo di Rischio", ["Conservativo", "Moderato", "Dinamico", "Aggressivo"])
    time_horizon = st.selectbox("Orizzonte", ["1-3 anni", "3-5 anni", "5-10 anni", "> 10 anni"])
    
    st.divider()
    st.header("Portafoglio")
    uploaded_file = st.file_uploader("Carica CSV o Excel", type=["csv", "xlsx", "xls"])

    default_df = pd.DataFrame({
        "Ticker": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ"],
        "Quantità": [15, 10, 8, 5, 12, 20, 15],
        "Prezzo Medio (€)": [185.0, 420.0, 170.0, 180.0, 125.0, 530.0, 460.0]
    })
    portfolio_df = default_df.copy()

    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith((".xlsx", ".xls")):
                raw = pd.read_excel(uploaded_file)
            else:
                try:
                    raw = pd.read_csv(uploaded_file, sep=None, engine="python")
                except:
                    uploaded_file.seek(0)
                    raw = pd.read_csv(uploaded_file, sep=";", encoding="latin1")

            st.success(f"File: {uploaded_file.name}")
            st.caption("Colonne: " + " | ".join(raw.columns.astype(str)))

            opts = ["-- Seleziona --"] + list(raw.columns.astype(str))
            t_col = st.selectbox("Colonna Ticker / Titolo", opts)
            q_col = st.selectbox("Colonna Quantità", opts)
            p_col = st.selectbox("Colonna Prezzo Medio", opts)

            if t_col != "-- Seleziona --" and q_col != "-- Seleziona --" and p_col != "-- Seleziona --":
                temp = pd.DataFrame({
                    "Ticker_Raw": raw[t_col].astype(str).str.strip(),
                    "Quantità": pd.to_numeric(raw[q_col], errors="coerce"),
                    "Prezzo Medio (€)": pd.to_numeric(raw[p_col], errors="coerce")
                }).dropna()
                temp = temp[temp["Quantità"] > 0]
                
                # Normalizza i ticker
                temp["Ticker"] = temp["Ticker_Raw"].apply(normalize_ticker)
                portfolio_df = temp[["Ticker", "Quantità", "Prezzo Medio (€)", "Ticker_Raw"]].copy()
                st.success(f"{len(portfolio_df)} posizioni caricate")
        except Exception as e:
            st.error(f"Errore lettura file: {e}")

    edited_df = st.data_editor(
        portfolio_df.drop(columns=["Ticker_Raw"], errors="ignore"),
        num_rows="dynamic",
        use_container_width=True,
        key="editor"
    )

    st.divider()
    period = st.selectbox("Periodo analisi", ["1y", "2y", "3y", "5y", "10y"], index=2)
    benchmark = st.selectbox("Benchmark", ["SPY", "^GSPC", "QQQ", "VT", "URTH"], index=0)
    fee_pct = st.number_input("Fee AUM annua (%)", 0.0, 2.5, 1.0, 0.05) / 100

# ====================== FUNZIONI ======================
@st.cache_data(ttl=900)
def get_prices(tickers, period="3y"):
    if not tickers:
        return pd.DataFrame()
    try:
        data = yf.download(tickers, period=period, progress=False, auto_adjust=True)["Close"]
        if isinstance(data, pd.Series):
            data = data.to_frame()
        return data.dropna(how="all")
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "Nome": info.get("longName") or info.get("shortName") or ticker,
            "Settore": info.get("sector") or "Non classificato",
            "PE": info.get("trailingPE"),
            "Beta": info.get("beta"),
        }
    except:
        return {"Nome": ticker, "Settore": "Non classificato", "PE": None, "Beta": None}

def safe_metrics(returns):
    if returns is None or len(returns.dropna()) < 20:
        return {}
    try:
        ann = 252
        total = (1 + returns).prod() - 1
        cagr = (1 + total) ** (ann / len(returns)) - 1
        vol = returns.std() * np.sqrt(ann)
        sharpe = cagr / vol if vol > 0 else 0
        downside = returns[returns < 0]
        sortino = cagr / (downside.std() * np.sqrt(ann)) if len(downside) > 0 else 0
        cum = (1 + returns).cumprod()
        max_dd = (cum / cum.cummax() - 1).min()
        return {"CAGR": cagr, "Volatilità": vol, "Sharpe": sharpe, "Sortino": sortino, "Max Drawdown": max_dd}
    except:
        return {}

# ====================== ELABORAZIONE ======================
if edited_df.empty or "Ticker" not in edited_df.columns:
    st.warning("Inserisci o carica un portafoglio.")
    st.stop()

tickers = edited_df["Ticker"].astype(str).str.strip().str.upper().tolist()
qtys = pd.to_numeric(edited_df["Quantità"], errors="coerce").fillna(0).tolist()
avgs = pd.to_numeric(edited_df["Prezzo Medio (€)"], errors="coerce").fillna(0).tolist()

valid_rows = [(t, q, a) for t, q, a in zip(tickers, qtys, avgs) if t and q > 0]
if not valid_rows:
    st.warning("Nessuna posizione valida.")
    st.stop()

tickers, qtys, avgs = map(list, zip(*valid_rows))

with st.spinner("Scarico prezzi da Yahoo Finance e verifico i ticker..."):
    prices = get_prices(tickers + [benchmark], period=period)

# Quali ticker funzionano
found = [t for t in tickers if t in prices.columns]
not_found = [t for t in tickers if t not in prices.columns]

if not_found:
    st.error("**Titoli non trovati su Yahoo Finance:**")
    st.write(", ".join(not_found))
    st.info("Suggerimento: usa i ticker ufficiali (es. AAPL, AMZN, BRK-B, URTH, KO...). Il sistema ha già provato a convertirli automaticamente.")

if not found:
    st.error("Nessun titolo valido trovato. Controlla i ticker e riprova.")
    st.stop()

last_price = prices.iloc[-1]

# Costruisci portafoglio solo con i titoli trovati
rows = []
total_value = 0.0
for t, q, a in zip(tickers, qtys, avgs):
    if t not in found:
        continue
    curr = float(last_price[t])
    val = q * curr
    cost = q * a
    pnl = val - cost
    pnl_pct = (curr / a - 1) if a > 0 else 0
    total_value += val
    info = get_info(t)
    rows.append({
        "Ticker": t,
        "Nome": info["Nome"],
        "Settore": info["Settore"],
        "Quantità": q,
        "Prezzo Medio": a,
        "Prezzo Attuale": curr,
        "Valore": val,
        "P&L €": pnl,
        "P&L %": pnl_pct
    })

port = pd.DataFrame(rows)
port["Peso %"] = port["Valore"] / total_value * 100

# Returns
rets = prices[found].pct_change().dropna()
w = port.set_index("Ticker")["Peso %"] / 100
w = w.reindex(found).fillna(0)
w = w / w.sum() if w.sum() > 0 else w
port_rets = (rets * w).sum(axis=1).dropna()
bench_rets = prices[benchmark].pct_change().dropna() if benchmark in prices.columns else pd.Series(dtype=float)

# ====================== TABS ======================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Dashboard", "Performance & Rischio", "Esposizione & Frontier", "Ribilanciamento", "Report PDF"
])

with tab1:
    st.subheader(f"Cliente: {client_name}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valore Portafoglio", f"€ {total_value:,.0f}")
    total_pnl = port["P&L €"].sum()
    c2.metric("P&L Totale", f"€ {total_pnl:,.0f}", f"{total_pnl / port['Prezzo Medio'].sum() * port['Quantità'].sum() if False else (total_pnl / (port['Valore'] - port['P&L €']).sum()):.1%}")
    c3.metric("Titoli validi", f"{len(found)} / {len(tickers)}")
    c4.metric("Fee annua stimata", f"€ {total_value * fee_pct:,.0f}")

    st.dataframe(
        port.style.format({
            "Prezzo Medio": "€{:.2f}", "Prezzo Attuale": "€{:.2f}",
            "Valore": "€{:,.0f}", "P&L €": "€{:+,.0f}", "P&L %": "{:+.1%}", "Peso %": "{:.1f}%"
        }),
        use_container_width=True, height=360
    )

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(port, values="Valore", names="Ticker", hole=0.4, title="Allocazione per Titolo")
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        sector_exp = port.groupby("Settore")["Valore"].sum().reset_index()
        fig2 = px.pie(sector_exp, values="Valore", names="Settore", hole=0.4, title="Esposizione Settoriale")
        st.plotly_chart(fig2, use_container_width=True)

with tab2:
    st.subheader("Performance storica")
    if len(port_rets) > 10:
        cum_p = (1 + port_rets).cumprod()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cum_p.index, y=cum_p, name="Portafoglio", line=dict(width=2.5)))
        if len(bench_rets) > 10:
            common = port_rets.index.intersection(bench_rets.index)
            cum_b = (1 + bench_rets.loc[common]).cumprod()
            fig.add_trace(go.Scatter(x=cum_b.index, y=cum_b, name=benchmark, line=dict(dash="dot")))
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

        m = safe_metrics(port_rets)
        cols = st.columns(4)
        for i, (k, v) in enumerate(m.items()):
            cols[i % 4].metric(k, f"{v:.2%}" if abs(v) < 10 else f"{v:.2f}")

        # QuantStats protetto
        if HAS_QS and len(port_rets.dropna()) >= 40:
            try:
                clean = port_rets.dropna()
                if not isinstance(clean.index, pd.DatetimeIndex):
                    clean.index = pd.to_datetime(clean.index)
                st.subheader("Metriche QuantStats")
                st.dataframe(qs.reports.metrics(clean, mode="basic", display=False), use_container_width=True)
            except Exception as e:
                st.info(f"QuantStats non disponibile in questo momento ({str(e)[:80]})")
        else:
            st.info("Dati insufficienti per QuantStats (servono almeno 40 giorni di storia).")
    else:
        st.warning("Dati storici insufficienti per calcolare la performance.")

with tab3:
    st.subheader("Esposizione Settoriale")
    sector_exp = port.groupby("Settore").agg({"Valore": "sum", "Peso %": "sum"}).sort_values("Valore", ascending=False)
    st.dataframe(sector_exp.style.format({"Valore": "€{:,.0f}", "Peso %": "{:.1f}%"}), use_container_width=True)

    st.subheader("Efficient Frontier")
    if HAS_PFP and len(found) >= 3 and len(prices) > 60:
        try:
            mu = expected_returns.mean_historical_return(prices[found])
            S = risk_models.sample_cov(prices[found])
            ef = EfficientFrontier(mu, S)
            ef.max_sharpe()
            ret, vol, _ = ef.portfolio_performance()
            weights_opt = ef.clean_weights()
            st.success(f"Max Sharpe → Rendimento atteso {ret:.1%} | Volatilità {vol:.1%}")
            st.json({k: round(v, 3) for k, v in weights_opt.items() if v > 0.005})
        except Exception as e:
            st.warning(f"Impossibile calcolare la frontiera: {e}")
    else:
        st.info("Servono almeno 3 titoli validi e dati sufficienti.")

with tab4:
    st.subheader("Ribilanciamento")
    if not port.empty:
        targets = {}
        cols = st.columns(min(4, len(found)))
        for i, t in enumerate(found):
            with cols[i % 4]:
                curr = float(port.loc[port["Ticker"] == t, "Peso
