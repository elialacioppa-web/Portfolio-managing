portfolio_analyzer/
├── main.py                      # Script principale (482 righe)
├── config.py                   # Configurazione (220 righe)
├── config.yaml                 # File di configurazione YAML
├── requirements.txt            # Dipendenze necessarie
├── README.md                   # Documentazione completa
├── portfolio_example.csv       # Esempio di file portfolio
└── modules/
    ├── __init__.py
    ├── data_loader.py           # Caricamento CSV/Excel (175 righe)
    ├── macro_analysis.py        # Analisi macroeconomica (712 righe)
    ├── micro_analysis.py        # Analisi microeconomica (1138 righe)
    ├── news_analysis.py         # Analisi news finanziarie (636 righe)
    ├── technical_analysis.py    # Analisi tecnica (882 righe)
    ├── portfolio_optimizer.py   # Ottimizzazione portfolio (597 righe)
    ├── report_generator.py      # Generazione report HTML (1057 righe)
    └── providers/
        ├── __init__.py
        ├── fred_provider.py         # Provider FRED (200 righe)
        ├── world_bank_provider.py   # Provider World Bank (190 righe)
        ├── imf_provider.py           # Provider FMI (169 righe)
        ├── ecb_provider.py           # Provider BCE (215 righe)
        ├── yahoo_finance_provider.py # Provider Yahoo Finance (369 righe)
        ├── alpha_vantage_provider.py # Provider Alpha Vantage (465 righe)
        ├── newsapi_provider.py       # Provider NewsAPI (180 righe)
        └── financial_modeling_prep_provider.py # Provider FMP (391 righe)
