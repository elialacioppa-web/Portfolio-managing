# portfolio_analyzer.py
# Portfolio Analyzer Pro - Versione Professionale per Consulenti Finanziari
# Ottobre 2026

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import io
import warnings
warnings.filterwarnings("ignore")

# Librerie avanzate
try:
    import quantstats as qs
    qs.extend_pandas()
    HAS_QS = True
except:
    HAS_QS = False

try:
    from pypfopt import EfficientFrontier, risk_models, expected_returns
    from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices
    HAS_PFP = True
except:
    HAS_PFP = False

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ====================== CONFIGURAZIONE PAGINA ======================
st.set_page_config(
    page_title="Portfolio Analyzer Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Stile più pulito
st.markdown("""
<style>
    .main {padding-top: 1.5rem;}
    .stMetric {background-color: #f8f9fa; padding: 12px; border-radius: 8px;}
    h1, h2, h3 {color: #1e3a5f;}
</style>
""", unsafe_allow_html=True)

st.title("Portfolio Analyzer Pro")
st.caption("Strumento professionale per consulenti finanziari  •  Analisi  •  Rischio  •  Ottimizzazione  •  Report PDF")

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("Profilo Cliente")
    client_name = st.text_input("Nome Cliente", value="Mario Rossi")
    risk_profile = st.selectbox("Profilo di Rischio", ["Conservativo", "Moderato", "Dinamico", "Aggressivo"])
    time_horizon = st.selectbox("Orizzonte", ["1-3 anni", "3-5 anni", "5-10 anni", "> 10 anni"])
    target_return = st.slider("Obiettivo rendimento annuo", 0.0, 12.0, 5.5, 0.5) / 100

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

            st.success(f"File caricato: {uploaded_file.name}")
            st.caption("Colonne trovate: " + ", ".join(raw.columns.astype(str)))

            opts = ["-- Seleziona --"] + list(raw.columns.astype(str))
            t_col = st.selectbox("Colonna Ticker / Titolo", opts)
            q_col = st.selectbox("Colonna Quantità", opts)
            p_col = st.selectbox("Colonna Prezzo Medio", opts)

            if t_col != "-- Seleziona --" and q_col != "-- Seleziona --" and p_col != "-- Seleziona --":
                temp = pd.DataFrame({
                    "Ticker": raw[t_col].astype(str).str.strip().str.upper(),
                    "Quantità": pd.to_numeric(raw[q_col], errors="coerce"),
                    "Prezzo Medio (€)": pd.to_numeric(raw[p_col], errors="coerce")
                }).dropna()
                temp = temp[(temp["Ticker"] != "") & (temp["Quantità"] > 0)]
                if not temp.empty:
                    portfolio_df = temp
                    st.success(f"{len(portfolio_df)} posizioni caricate")
        except Exception as e:
            st.error(f"Errore lettura: {e}")

    edited_df = st.data_editor(portfolio_df, num_rows="dynamic", use_container_width=True, key="ed")

    st.divider()
    period = st.selectbox("Periodo analisi", ["1y", "2y", "3y", "5y", "10y"], index=2)
    benchmark = st.selectbox("Benchmark", ["SPY", "^GSPC", "QQQ", "VT", "IWDA.L"], index=0)
    fee_pct = st.number_input("Fee AUM annua (%)", 0.0, 2.5, 1.0, 0.05) / 100

# ====================== FUNZIONI ======================
@st.cache_data(ttl=900)
def download_prices(tickers, period="3y"):
    data = yf.download(tickers, period=period, progress=False, auto_adjust=True)["Close"]
    if isinstance(data, pd.Series):
        data = data.to_frame()
    return data.dropna(how="all")

@st.cache_data(ttl=3600)
def get_info(ticker):
    try:
        t = yf.Ticker(ticker)
        info = t.info
        return {
            "Nome": info.get("longName") or info.get("shortName") or ticker,
            "Settore": info.get("sector", "Non classificato"),
            "Industry": info.get("industry", "N/A"),
            "PE": info.get("trailingPE"),
            "Beta": info.get("beta"),
            "ROE": info.get("returnOnEquity"),
            "Market Cap": info.get("marketCap"),
        }
    except:
        return {"Nome": ticker, "Settore": "Non classificato", "Industry": "N/A",
                "PE": None, "Beta": None, "ROE": None, "Market Cap": None}

def calculate_metrics(returns):
    if returns.empty:
        return {}
    ann = 252
    total = (1 + returns).prod() - 1
    cagr = (1 + total) ** (ann / len(returns)) - 1
    vol = returns.std() * np.sqrt(ann)
    sharpe = cagr / vol if vol > 0 else 0
    downside = returns[returns < 0]
    sortino = cagr / (downside.std() * np.sqrt(ann)) if len(downside) > 0 else 0
    cum = (1 + returns).cumprod()
    max_dd = (cum / cum.cummax() - 1).min()
    var95 = np.percentile(returns.dropna(), 5)
    return {"CAGR": cagr, "Volatilità": vol, "Sharpe": sharpe, "Sortino": sortino,
            "Max Drawdown": max_dd, "VaR 95%": var95, "Totale": total}

# ====================== DATI PORTAFOGLIO ======================
if edited_df.empty or "Ticker" not in edited_df.columns:
    st.warning("Carica o inserisci un portafoglio valido.")
    st.stop()

tickers = edited_df["Ticker"].astype(str).str.strip().str.upper().tolist()
qtys = pd.to_numeric(edited_df["Quantità"], errors="coerce").fillna(0).tolist()
avgs = pd.to_numeric(edited_df["Prezzo Medio (€)"], errors="coerce").fillna(0).tolist()

valid_data = [(t, q, a) for t, q, a in zip(tickers, qtys, avgs) if t and q > 0]
if not valid_data:
    st.warning("Nessuna posizione valida.")
    st.stop()

tickers, qtys, avgs = map(list, zip(*valid_data))

with st.spinner("Recupero prezzi aggiornati da Yahoo Finance..."):
    prices = download_prices(tickers + [benchmark], period=period)

if prices.empty:
    st.error("Impossibile recuperare i prezzi. Verifica i ticker.")
    st.stop()

last_price = prices.iloc[-1]
valid_tickers = [t for t in tickers if t in last_price.index]

# Costruzione portafoglio con prezzi attuali
rows = []
total_value = 0.0
sector_map = {}

for t, q, a in zip(tickers, qtys, avgs):
    if t not in last_price.index:
        continue
    curr = float(last_price[t])
    val = q * curr
    cost = q * a
    pnl = val - cost
    pnl_pct = (curr / a - 1) if a > 0 else 0
    total_value += val

    info = get_info(t)
    sector = info["Settore"]
    sector_map[t] = sector

    rows.append({
        "Ticker": t,
        "Nome": info["Nome"],
        "Settore": sector,
        "Quantità": q,
        "Prezzo Medio": a,
        "Prezzo Attuale": curr,
        "Valore": val,
        "Costo": cost,
        "P&L €": pnl,
        "P&L %": pnl_pct
    })

port = pd.DataFrame(rows)
if port.empty:
    st.error("Nessun ticker valido trovato.")
    st.stop()

port["Peso %"] = port["Valore"] / total_value * 100

# Returns
rets = prices[valid_tickers].pct_change().dropna()
w = port.set_index("Ticker")["Peso %"] / 100
w = w.reindex(valid_tickers).fillna(0)
w = w / w.sum()
port_rets = (rets * w).sum(axis=1)
bench_rets = prices[benchmark].pct_change().dropna()
common = port_rets.index.intersection(bench_rets.index)
port_rets = port_rets.loc[common]
bench_rets = bench_rets.loc[common]

# ====================== TABS ======================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Dashboard",
    "Performance & Rischio",
    "Esposizione & Frontier",
    "Ribilanciamento",
    "Report PDF",
    "Strumenti Consulente"
])

# ----- TAB 1: DASHBOARD -----
with tab1:
    st.subheader(f"Cliente: {client_name}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Valore Attuale Portafoglio", f"€ {total_value:,.0f}")
    total_pnl = port["P&L €"].sum()
    total_cost = port["Costo"].sum()
    c2.metric("P&L Totale", f"€ {total_pnl:,.0f}", f"{total_pnl/total_cost:.1%}")
    c3.metric("Profilo", risk_profile)
    c4.metric("Fee Annua Stimata", f"€ {total_value * fee_pct:,.0f}")

    st.markdown("### Posizioni dettagliate")
    st.dataframe(
        port[["Ticker", "Nome", "Settore", "Quantità", "Prezzo Medio", "Prezzo Attuale", "Valore", "P&L €", "P&L %", "Peso %"]]
        .style.format({
            "Prezzo Medio": "€{:.2f}",
            "Prezzo Attuale": "€{:.2f}",
            "Valore": "€{:,.0f}",
            "P&L €": "€{:+,.0f}",
            "P&L %": "{:+.1%}",
            "Peso %": "{:.1f}%"
        }),
        use_container_width=True,
        height=380
    )

    col1, col2 = st.columns(2)
    with col1:
        fig = px.pie(port, values="Valore", names="Ticker", hole=0.4,
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(title="Allocazione per Titolo", margin=dict(t=40, b=20))
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        sector_exp = port.groupby("Settore")["Valore"].sum().reset_index()
        fig2 = px.pie(sector_exp, values="Valore", names="Settore", hole=0.4,
                      color_discrete_sequence=px.colors.qualitative.Set2)
        fig2.update_layout(title="Esposizione Settoriale", margin=dict(t=40, b=20))
        st.plotly_chart(fig2, use_container_width=True)

# ----- TAB 2: PERFORMANCE -----
with tab2:
    st.subheader("Andamento storico")
    cum_p = (1 + port_rets).cumprod()
    cum_b = (1 + bench_rets).cumprod()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=cum_p.index, y=cum_p, name="Portafoglio", line=dict(width=2.5, color="#1f77b4")))
    fig.add_trace(go.Scatter(x=cum_b.index, y=cum_b, name=benchmark, line=dict(width=1.8, dash="dot", color="#ff7f0e")))
    fig.update_layout(height=420, legend=dict(orientation="h"), yaxis_title="Crescita (base 1)")
    st.plotly_chart(fig, use_container_width=True)

    m_p = calculate_metrics(port_rets)
    m_b = calculate_metrics(bench_rets)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Metriche Portafoglio")
        for k, v in m_p.items():
            st.write(f"**{k}**: {v:.2%}" if abs(v) < 10 else f"**{k}**: {v:.2f}")
    with col2:
        st.markdown(f"#### Metriche {benchmark}")
        for k, v in m_b.items():
            st.write(f"**{k}**: {v:.2%}" if abs(v) < 10 else f"**{k}**: {v:.2f}")

    st.subheader("Drawdown")
    dd = cum_p / cum_p.cummax() - 1
    fig_dd = go.Figure(go.Scatter(x=dd.index, y=dd, fill="tozeroy", line=dict(color="#d62728")))
    fig_dd.update_layout(height=280, yaxis_title="Drawdown")
    st.plotly_chart(fig_dd, use_container_width=True)

    if HAS_QS:
        st.subheader("QuantStats – Metriche avanzate")
        st.dataframe(qs.reports.metrics(port_rets, mode="full", display=False), use_container_width=True)

# ----- TAB 3: ESPOSIZIONE + EFFICIENT FRONTIER -----
with tab3:
    st.subheader("Esposizione Settoriale")
    sector_exp = port.groupby("Settore").agg({"Valore": "sum", "Peso %": "sum"}).reset_index()
    sector_exp = sector_exp.sort_values("Valore", ascending=False)
    st.dataframe(sector_exp.style.format({"Valore": "€{:,.0f}", "Peso %": "{:.1f}%"}), use_container_width=True)

    st.subheader("Efficient Frontier")
    if HAS_PFP and len(valid_tickers) >= 3:
        try:
            mu = expected_returns.mean_historical_return(prices[valid_tickers])
            S = risk_models.sample_cov(prices[valid_tickers])
            ef = EfficientFrontier(mu, S)
            ef.max_sharpe()
            ret_sharpe, vol_sharpe, _ = ef.portfolio_performance()
            cleaned = ef.clean_weights()

            st.success(f"Portafoglio Max Sharpe → Rendimento atteso: {ret_sharpe:.1%}  |  Volatilità: {vol_sharpe:.1%}")
            st.write("Pesi ottimali (Max Sharpe):")
            st.json({k: round(v, 4) for k, v in cleaned.items() if v > 0.001})

            # Frontiera
            ef_frontier = EfficientFrontier(mu, S)
            fig_ef = go.Figure()
            # Punti random
            n_samples = 800
            results = np.zeros((3, n_samples))
            weights_record = []
            for i in range(n_samples):
                w_rand = np.random.dirichlet(np.ones(len(valid_tickers)), size=1)[0]
                port_ret = np.dot(w_rand, mu)
                port_vol = np.sqrt(np.dot(w_rand.T, np.dot(S, w_rand)))
                results[0, i] = port_vol
                results[1, i] = port_ret
                results[2, i] = port_ret / port_vol if port_vol > 0 else 0

            fig_ef.add_trace(go.Scatter(x=results[0], y=results[1], mode="markers",
                                        marker=dict(size=5, color=results[2], colorscale="Viridis", showscale=True),
                                        name="Portafogli casuali"))
            fig_ef.add_trace(go.Scatter(x=[vol_sharpe], y=[ret_sharpe], mode="markers",
                                        marker=dict(size=14, color="red", symbol="star"),
                                        name="Max Sharpe"))
            fig_ef.update_layout(title="Efficient Frontier", xaxis_title="Volatilità", yaxis_title="Rendimento atteso", height=480)
            st.plotly_chart(fig_ef, use_container_width=True)
        except Exception as e:
            st.warning(f"Impossibile calcolare la frontiera: {e}")
    else:
        st.info("Servono almeno 3 titoli e la libreria PyPortfolioOpt per l’Efficient Frontier.")

# ----- TAB 4: RIBILANCIAMENTO -----
with tab4:
    st.subheader("Ribilanciamento verso pesi target")
    targets = {}
    cols = st.columns(min(4, len(valid_tickers)))
    for i, t in enumerate(valid_tickers):
        with cols[i % 4]:
            curr = float(port.loc[port["Ticker"] == t, "Peso %"].iloc[0])
            targets[t] = st.number_input(t, 0.0, 100.0, curr, 0.5, key=f"tg_{t}")

    if abs(sum(targets.values()) - 100) < 2:
        rebal = []
        for t in valid_tickers:
            curr_w = float(port.loc[port["Ticker"] == t, "Peso %"].iloc[0])
            diff = targets[t] - curr_w
            amount = (diff / 100) * total_value
            rebal.append({"Ticker": t, "Attuale %": curr_w, "Target %": targets[t],
                          "Diff %": diff, "Importo €": amount})
        st.dataframe(pd.DataFrame(rebal).style.format({
            "Attuale %": "{:.1f}%", "Target %": "{:.1f}%",
            "Diff %": "{:+.1f}%", "Importo €": "€{:+,.0f}"
        }), use_container_width=True)
    else:
        st.warning("La somma dei pesi target deve essere prossima al 100%.")

# ----- TAB 5: REPORT PDF -----
with tab5:
    st.subheader("Genera Report PDF Professionale")
    st.write(f"Cliente: **{client_name}**  |  Data: {datetime.now().strftime('%d/%m/%Y')}")

    if st.button("Genera e scarica PDF", type="primary"):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=1.5*cm, leftMargin=1.5*cm,
                                topMargin=1.5*cm, bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("Title", parent=styles["Heading1"], alignment=TA_CENTER, fontSize=16, spaceAfter=12)
        h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=6)
        normal = styles["Normal"]

        elements = []
        elements.append(Paragraph("Portfolio Analyzer Pro – Report Cliente", title_style))
        elements.append(Paragraph(f"<b>Cliente:</b> {client_name}", normal))
        elements.append(Paragraph(f"<b>Data report:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", normal))
        elements.append(Paragraph(f"<b>Profilo di rischio:</b> {risk_profile}", normal))
        elements.append(Paragraph(f"<b>Valore attuale portafoglio:</b> € {total_value:,.0f}", normal))
        elements.append(Spacer(1, 12))

        elements.append(Paragraph("Sintesi Posizioni", h2_style))
        table_data = [["Ticker", "Nome", "Settore", "Valore €", "Peso %", "P&L %"]]
        for _, r in port.iterrows():
            table_data.append([
                r["Ticker"],
                r["Nome"][:28],
                r["Settore"][:18],
                f"{r['Valore']:,.0f}",
                f"{r['Peso %']:.1f}",
                f"{r['P&L %']:+.1%}"
            ])
        t = Table(table_data, colWidths=[2.2*cm, 5.5*cm, 3.5*cm, 2.8*cm, 2*cm, 2*cm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 14))

        elements.append(Paragraph("Metriche di Performance", h2_style))
        m = calculate_metrics(port_rets)
        metrics_text = "<br/>".join([f"<b>{k}:</b> {v:.2%}" if abs(v) < 10 else f"<b>{k}:</b> {v:.2f}" for k, v in m.items()])
        elements.append(Paragraph(metrics_text, normal))

        elements.append(Spacer(1, 16))
        elements.append(Paragraph("Questo report è generato automaticamente da Portfolio Analyzer Pro ed ha esclusivamente scopo informativo.", 
                                  ParagraphStyle("Footer", parent=normal, fontSize=8, textColor=colors.grey)))

        doc.build(elements)
        buffer.seek(0)

        st.download_button(
            label="Scarica Report PDF",
            data=buffer,
            file_name=f"Report_{client_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
        st.success("PDF generato correttamente. Clicca sul pulsante qui sopra per scaricarlo.")

# ----- TAB 6: STRUMENTI CONSULENTE -----
with tab6:
    st.subheader("Strumenti per il Consulente")
    aum = st.number_input("AUM cliente (€)", value=float(total_value), step=1000.0)
    st.metric("Ricavo annuo da fee", f"€ {aum * fee_pct:,.0f}")

    st.markdown("### Note e raccomandazioni")
    notes = st.text_area("Osservazioni per il cliente", height=150,
                         placeholder="Inserisci qui le tue raccomandazioni, punti di attenzione e prossimi passi...")
    if st.button("Salva note in sessione"):
        st.session_state["notes"] = notes
        st.success("Note salvate")

    if "notes" in st.session_state:
        st.info(st.session_state["notes"])

st.markdown("---")
st.caption(f"Portfolio Analyzer Pro  •  {client_name}  •  {datetime.now().strftime('%d/%m/%Y %H:%M')}  •  Dati Yahoo Finance  •  Solo scopo informativo")
