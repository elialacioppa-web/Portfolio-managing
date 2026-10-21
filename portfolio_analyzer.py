# portfolio_analyzer.py
# Portfolio Analyzer Pro - Versione Avanzata per Consulenti Finanziari
# Autore: Assistente Grok - Ottobre 2026

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import warnings
import io
import base64

warnings.filterwarnings("ignore")

# Prova a importare quantstats (opzionale ma fortemente consigliato)
try:
    import quantstats as qs
    qs.extend_pandas()
    HAS_QUANTSTATS = True
except ImportError:
    HAS_QUANTSTATS = False

st.set_page_config(
    page_title="Portfolio Analyzer Pro | Consulente",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ====================== HEADER ======================
st.title("📈 Portfolio Analyzer Pro")
st.caption("Strumento professionale per consulenti finanziari • Analisi • Rischio • Proiezioni • Report")

# ====================== SIDEBAR - CLIENTE & PORTAFOGLIO ======================
st.sidebar.header("👤 Profilo Cliente")
client_name = st.sidebar.text_input("Nome Cliente", value="Cliente Esempio")
risk_profile = st.sidebar.selectbox("Profilo di Rischio", ["Conservativo", "Moderato", "Dinamico", "Aggressivo"])
time_horizon = st.sidebar.selectbox("Orizzonte Temporale", ["1-3 anni", "3-5 anni", "5-10 anni", "Oltre 10 anni"])
target_return = st.sidebar.slider("Obiettivo rendimento annuo (%)", 0.0, 15.0, 6.0, 0.5) / 100

st.sidebar.markdown("---")
st.sidebar.header("📁 Portafoglio")

uploaded_file = st.sidebar.file_uploader("Carica CSV o Excel", type=["csv", "xlsx", "xls"])

default_data = {
    "Ticker": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "SPY", "QQQ", "GLD"],
    "Quantità": [12, 8, 6, 4, 10, 25, 15, 8],
    "Prezzo Medio (€)": [185.0, 420.0, 170.0, 180.0, 125.0, 530.0, 460.0, 190.0]
}
default_df = pd.DataFrame(default_data)

portfolio_df = default_df.copy()

if uploaded_file is not None:
    try:
        if uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
            raw_df = pd.read_excel(uploaded_file)
        else:
            try:
                raw_df = pd.read_csv(uploaded_file, sep=None, engine="python", encoding="utf-8")
            except:
                uploaded_file.seek(0)
                raw_df = pd.read_csv(uploaded_file, sep=";", encoding="latin1")

        st.sidebar.success(f"File caricato: {uploaded_file.name}")
        st.sidebar.write("**Colonne rilevate:**")
        st.sidebar.write(list(raw_df.columns))

        st.sidebar.markdown("### Mappa le colonne")
        options = ["-- Seleziona --"] + list(raw_df.columns.astype(str))

        ticker_col = st.sidebar.selectbox("Colonna Ticker / Titolo / ISIN", options, key="t_col")
        qty_col = st.sidebar.selectbox("Colonna Quantità / Pezzi / Shares", options, key="q_col")
        price_col = st.sidebar.selectbox("Colonna Prezzo Medio / PMC / Costo", options, key="p_col")

        if ticker_col != "-- Seleziona --" and qty_col != "-- Seleziona --" and price_col != "-- Seleziona --":
            temp = pd.DataFrame({
                "Ticker": raw_df[ticker_col].astype(str).str.strip().str.upper(),
                "Quantità": pd.to_numeric(raw_df[qty_col], errors="coerce"),
                "Prezzo Medio (€)": pd.to_numeric(raw_df[price_col], errors="coerce")
            }).dropna()
            temp = temp[(temp["Ticker"] != "") & (temp["Quantità"] > 0)]
            if not temp.empty:
                portfolio_df = temp
                st.sidebar.success(f"{len(portfolio_df)} posizioni caricate")
            else:
                st.sidebar.warning("Nessuna riga valida trovata")
    except Exception as e:
        st.sidebar.error(f"Errore lettura file: {e}")

edited_df = st.sidebar.data_editor(
    portfolio_df,
    num_rows="dynamic",
    use_container_width=True,
    key="editor"
)

period = st.sidebar.selectbox("Periodo di analisi", ["1y", "2y", "3y", "5y", "10y", "max"], index=2)
benchmark = st.sidebar.selectbox("Benchmark", ["SPY", "^GSPC", "QQQ", "VT", "IWDA.L", "SWDA.L"], index=0)

st.sidebar.markdown("---")
st.sidebar.header("💰 Fee Consulente")
fee_pct = st.sidebar.number_input("Fee annua AUM (%)", 0.0, 3.0, 1.0, 0.05) / 100

# ====================== FUNZIONI ======================
@st.cache_data(ttl=1800)
def get_prices(tickers, period="3y"):
    if not tickers:
        return pd.DataFrame()
    data = yf.download(tickers, period=period, progress=False, auto_adjust=True)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return data.dropna(how="all")

@st.cache_data(ttl=3600)
def get_ticker_info(ticker):
    try:
        info = yf.Ticker(ticker).info
        return {
            "Nome": info.get("longName", ticker),
            "Settore": info.get("sector", "N/A"),
            "Industry": info.get("industry", "N/A"),
            "PE": info.get("trailingPE"),
            "Forward PE": info.get("forwardPE"),
            "ROE": info.get("returnOnEquity"),
            "Debt/Equity": info.get("debtToEquity"),
            "Beta": info.get("beta"),
            "Dividend Yield": info.get("dividendYield"),
            "Market Cap": info.get("marketCap"),
        }
    except:
        return {}

def calc_basic_metrics(returns):
    if returns.empty:
        return {}
    ann = 252
    total_ret = (1 + returns).prod() - 1
    cagr = (1 + total_ret) ** (ann / len(returns)) - 1
    vol = returns.std() * np.sqrt(ann)
    sharpe = cagr / vol if vol > 0 else 0
    downside = returns[returns < 0]
    sortino = cagr / (downside.std() * np.sqrt(ann)) if len(downside) > 0 else 0
    cum = (1 + returns).cumprod()
    max_dd = ((cum / cum.cummax()) - 1).min()
    var95 = np.percentile(returns.dropna(), 5)
    cvar95 = returns[returns <= var95].mean()
    return {
        "CAGR": cagr,
        "Volatilità": vol,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Max Drawdown": max_dd,
        "VaR 95%": var95,
        "CVaR 95%": cvar95,
        "Rendimento Totale": total_ret
    }

# ====================== PREPARAZIONE DATI ======================
if edited_df.empty or "Ticker" not in edited_df.columns:
    st.warning("Inserisci o carica un portafoglio valido.")
    st.stop()

tickers = edited_df["Ticker"].astype(str).str.strip().str.upper().tolist()
qtys = pd.to_numeric(edited_df["Quantità"], errors="coerce").fillna(0).tolist()
avgs = pd.to_numeric(edited_df["Prezzo Medio (€)"], errors="coerce").fillna(0).tolist()

valid = [(t, q, a) for t, q, a in zip(tickers, qtys, avgs) if t and q > 0]
if not valid:
    st.warning("Nessuna posizione valida.")
    st.stop()

tickers, qtys, avgs = map(list, zip(*valid))

with st.spinner("Aggiorno i prezzi di mercato..."):
    prices = get_prices(tickers + [benchmark], period=period)

if prices.empty:
    st.error("Impossibile scaricare i dati di mercato. Controlla i ticker.")
    st.stop()

last_prices = prices.iloc[-1]
valid_tickers = [t for t in tickers if t in last_prices.index]

rows = []
total_value = 0.0
for t, q, a in zip(tickers, qtys, avgs):
    if t in last_prices.index:
        curr = float(last_prices[t])
        val = q * curr
        cost = q * a
        pnl = val - cost
        pnl_pct = (curr / a - 1) if a > 0 else 0
        total_value += val
        rows.append({
            "Ticker": t, "Quantità": q, "Prezzo Medio": a,
            "Prezzo Attuale": curr, "Valore": val, "Costo": cost,
            "P&L €": pnl, "P&L %": pnl_pct
        })

port = pd.DataFrame(rows)
if not port.empty:
    port["Peso %"] = port["Valore"] / total_value * 100

# Returns
rets = prices[valid_tickers].pct_change().dropna()
weights = port.set_index("Ticker")["Peso %"] / 100
weights = weights.reindex(valid_tickers).fillna(0)
weights = weights / weights.sum()
port_rets = (rets * weights).sum(axis=1)
bench_rets = prices[benchmark].pct_change().dropna()
common_idx = port_rets.index.intersection(bench_rets.index)
port_rets = port_rets.loc[common_idx]
bench_rets = bench_rets.loc[common_idx]

# ====================== TABS ======================
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "🏠 Dashboard Cliente",
    "📊 Performance & Rischio",
    "🔮 Proiezioni Monte Carlo",
    "⚖️ Ribilanciamento",
    "🏢 Analisi Titoli",
    "📄 Report Professionale",
    "🛠️ Strumenti Consulente"
])

# ---------- TAB 1: DASHBOARD ----------
with tab1:
    st.subheader(f"Cliente: **{client_name}**")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valore Portafoglio", f"€ {total_value:,.0f}")
    total_pnl = port["P&L €"].sum() if not port.empty else 0
    total_cost = port["Costo"].sum() if not port.empty else 1
    c2.metric("P&L Complessivo", f"€ {total_pnl:,.0f}", f"{total_pnl/total_cost:.1%}")
    c3.metric("Profilo Rischio", risk_profile)
    c4.metric("Fee Annua Stimata", f"€ {total_value * fee_pct:,.0f}")

    st.markdown("### Allocazione attuale")
    col_a, col_b = st.columns([1.2, 1])
    with col_a:
        if not port.empty:
            st.dataframe(
                port.style.format({
                    "Prezzo Medio": "€{:.2f}", "Prezzo Attuale": "€{:.2f}",
                    "Valore": "€{:,.0f}", "Costo": "€{:,.0f}",
                    "P&L €": "€{:+,.0f}", "P&L %": "{:+.1%}", "Peso %": "{:.1f}%"
                }),
                use_container_width=True, height=350
            )
    with col_b:
        if not port.empty:
            fig = px.pie(port, values="Valore", names="Ticker", hole=0.35,
                         color_discrete_sequence=px.colors.qualitative.Set2)
            fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 2: PERFORMANCE & RISCHIO ----------
with tab2:
    st.subheader("Andamento storico vs Benchmark")
    if not port_rets.empty:
        cum_p = (1 + port_rets).cumprod()
        cum_b = (1 + bench_rets).cumprod()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=cum_p.index, y=cum_p, name="Portafoglio", line=dict(width=2.5)))
        fig.add_trace(go.Scatter(x=cum_b.index, y=cum_b, name=benchmark, line=dict(width=1.5, dash="dot")))
        fig.update_layout(height=420, legend=dict(orientation="h"))
        st.plotly_chart(fig, use_container_width=True)

        metrics_p = calc_basic_metrics(port_rets)
        metrics_b = calc_basic_metrics(bench_rets)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Portafoglio")
            for k, v in metrics_p.items():
                st.write(f"**{k}**: {v:.2%}" if abs(v) < 5 else f"**{k}**: {v:.2f}")
        with col2:
            st.markdown(f"#### {benchmark}")
            for k, v in metrics_b.items():
                st.write(f"**{k}**: {v:.2%}" if abs(v) < 5 else f"**{k}**: {v:.2f}")

        st.subheader("Matrice di correlazione")
        corr = rets.corr()
        fig_corr = px.imshow(corr, text_auto=".2f", color_continuous_scale="RdBu_r", aspect="auto")
        st.plotly_chart(fig_corr, use_container_width=True)

        # Drawdown
        st.subheader("Underwater (Drawdown)")
        dd = (cum_p / cum_p.cummax() - 1)
        fig_dd = go.Figure()
        fig_dd.add_trace(go.Scatter(x=dd.index, y=dd, fill="tozeroy", name="Drawdown", line=dict(color="crimson")))
        fig_dd.update_layout(height=300)
        st.plotly_chart(fig_dd, use_container_width=True)

# ---------- TAB 3: MONTE CARLO ----------
with tab3:
    st.subheader("Simulazione Monte Carlo del patrimonio")
    st.info("Simula migliaia di scenari futuri basati sulla volatilità e rendimento storico del portafoglio.")

    years = st.slider("Anni di proiezione", 1, 20, 10)
    sims = st.slider("Numero di simulazioni", 200, 3000, 1000, 100)
    initial = total_value

    if st.button("Esegui Simulazione Monte Carlo", type="primary"):
        mu = port_rets.mean() * 252
        sigma = port_rets.std() * np.sqrt(252)
        dt = 1/252
        steps = int(years * 252)

        np.random.seed(42)
        daily_returns = np.random.normal(mu * dt, sigma * np.sqrt(dt), size=(steps, sims))
        paths = initial * np.exp(np.cumsum(daily_returns, axis=0))
        paths = np.vstack([np.full(sims, initial), paths])

        final_values = paths[-1]
        p5, p25, p50, p75, p95 = np.percentile(final_values, [5, 25, 50, 75, 95])

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Mediana (50%)", f"€ {p50:,.0f}")
        c2.metric("Scenario pessimistico (5%)", f"€ {p5:,.0f}")
        c3.metric("Scenario ottimistico (95%)", f"€ {p95:,.0f}")
        c4.metric("Prob. > obiettivo", f"{(final_values > initial * (1+target_return)**years).mean():.1%}")

        # Fan chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(steps+1)), y=np.percentile(paths, 95, axis=1),
                                 line=dict(width=0), showlegend=False))
        fig.add_trace(go.Scatter(x=list(range(steps+1)), y=np.percentile(paths, 5, axis=1),
                                 fill="tonexty", name="90% confidenza", line=dict(width=0),
                                 fillcolor="rgba(0,100,255,0.15)"))
        fig.add_trace(go.Scatter(x=list(range(steps+1)), y=np.median(paths, axis=1),
                                 name="Mediana", line=dict(color="blue", width=2)))
        fig.update_layout(title=f"Proiezione patrimonio a {years} anni", height=450,
                          xaxis_title="Giorni di borsa", yaxis_title="Valore (€)")
        st.plotly_chart(fig, use_container_width=True)

# ---------- TAB 4: RIBILANCIAMENTO ----------
with tab4:
    st.subheader("Suggerimenti di ribilanciamento")
    st.write("Imposta i pesi target desiderati (devono sommare circa 100%)")

    if not port.empty:
        targets = {}
        cols = st.columns(min(4, len(valid_tickers)))
        for i, t in enumerate(valid_tickers):
            with cols[i % 4]:
                curr = float(port.loc[port["Ticker"] == t, "Peso %"].iloc[0])
                targets[t] = st.number_input(f"{t}", 0.0, 100.0, curr, 0.5, key=f"tgt_{t}")

        total_tgt = sum(targets.values())
        if abs(total_tgt - 100) > 1.5:
            st.warning(f"Somma pesi target = {total_tgt:.1f}% (dovrebbe essere \~100%)")
        else:
            rebal_rows = []
            for t in valid_tickers:
                curr_w = float(port.loc[port["Ticker"] == t, "Peso %"].iloc[0])
                diff = targets[t] - curr_w
                amount = diff / 100 * total_value
                rebal_rows.append({
                    "Ticker": t,
                    "Peso Attuale": curr_w,
                    "Peso Target": targets[t],
                    "Differenza %": diff,
                    "Importo da muovere €": amount
                })
            rebal_df = pd.DataFrame(rebal_rows)
            st.dataframe(rebal_df.style.format({
                "Peso Attuale": "{:.1f}%", "Peso Target": "{:.1f}%",
                "Differenza %": "{:+.1f}%", "Importo da muovere €": "€{:+,.0f}"
            }), use_container_width=True)
            st.success("Valori positivi = comprare | Valori negativi = vendere")

# ---------- TAB 5: ANALISI TITOLI ----------
with tab5:
    if valid_tickers:
        sel = st.selectbox("Seleziona titolo da analizzare", valid_tickers)
        info = get_ticker_info(sel)
        st.markdown(f"### {info.get('Nome', sel)}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Settore", info.get("Settore", "N/A"))
        c2.metric("P/E", f"{info.get('PE'):.1f}" if info.get("PE") else "N/A")
        c3.metric("ROE", f"{info.get('ROE')*100:.1f}%" if info.get("ROE") else "N/A")
        c4.metric("Beta", f"{info.get('Beta'):.2f}" if info.get("Beta") else "N/A")

        # Prezzo storico del singolo titolo
        if sel in prices.columns:
            fig = px.line(prices[sel], title=f"Prezzo storico {sel}")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nessun titolo valido")

# ---------- TAB 6: REPORT ----------
with tab6:
    st.subheader("Report Professionale")
    st.write(f"**Cliente:** {client_name} | **Data:** {datetime.now().strftime('%d/%m/%Y')}")

    if HAS_QUANTSTATS and not port_rets.empty:
        st.success("QuantStats disponibile – puoi generare un tearsheet completo")
        if st.button("Genera Tearsheet HTML (QuantStats)"):
            with st.spinner("Generazione report in corso..."):
                output = io.StringIO()
                qs.reports.html(port_rets, benchmark=bench_rets, output=None,
                                title=f"Report Portafoglio - {client_name}",
                                download_filename="report.html")
                # QuantStats di solito salva su file; per semplicità mostriamo metriche
                st.info("Per un report HTML completo in produzione si può salvare su file e offrire il download.")
                st.write(qs.reports.metrics(port_rets, mode="full", display=False))
    else:
        st.warning("Installa `quantstats` per i report avanzati (aggiunto nei requirements).")
        st.write(calc_basic_metrics(port_rets))

# ---------- TAB 7: STRUMENTI CONSULENTE ----------
with tab7:
    st.subheader("Strumenti per il Consulente")

    st.markdown("### Calcolo Fee")
    aum = st.number_input("AUM del cliente (€)", value=float(total_value), step=1000.0)
    fee = st.number_input("Fee % annua", value=fee_pct*100, step=0.05) / 100
    st.metric("Ricavo annuo stimato", f"€ {aum * fee:,.0f}")

    st.markdown("### Note e Raccomandazioni per il cliente")
    notes = st.text_area("Scrivi qui le tue osservazioni e raccomandazioni", height=180,
                         placeholder="Es: Consigliamo di aumentare l'esposizione azionaria internazionale e ridurre la concentrazione su singoli titoli...")

    if st.button("Salva note nella sessione"):
        st.session_state["client_notes"] = notes
        st.success("Note salvate per questa sessione")

    if "client_notes" in st.session_state:
        st.info(st.session_state["client_notes"])

st.markdown("---")
st.caption(f"Portfolio Analyzer Pro • Cliente: {client_name} • Generato il {datetime.now().strftime('%d/%m/%Y %H:%M')} • Solo a scopo informativo e didattico")
