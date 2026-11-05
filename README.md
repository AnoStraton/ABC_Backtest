# ABC Backtest (Lighter)

Offline ABC fractal backtest for Lighter BTC perp.

## Files
- `back_lighter.py` — backtest runner
- `module/` — `structure.fractality`, `tools.get_dataset`
- `data/ohlcv_lighter_BTC-USDC_1m_full.csv` — candles (scraped separately)

## Run
```bash
pip install -r requirements.txt
python back_lighter.py
```

Formerly `back_paradex2.py` (same logic; data source = Lighter).
