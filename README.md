# ABC Backtest Paradex

Backtest offline de la stratégie ABC (fractales 3 barres → setups A–B–C → exécution SL/TP) sur OHLCV Paradex.

## Contenu

- `back_paradex2.py` — script principal
- `module/tools.py` — `get_dataset(file)` (lecture CSV)
- `module/structure.py` — `fractality(rows)` (HH/LH/LL/HL)

## Données

Attendu par le script (non inclus) :

`data/ohlcv_paradex_BTC-USD-PERP_1m_360d.csv`

## Lancer

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
python back_paradex2.py
```

Exécuter depuis la racine du dépôt pour que `import module.tools` / `import module.structure` fonctionnent.

## Licence / provenance

Sources copiées depuis `Documents\ABCBOT` (Nathan). Pas de live trading.
