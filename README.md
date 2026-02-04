# Stock vs Gold 📊

See stock prices measured in gold instead of fiat currency.

## Why?

Measuring stocks in gold shows their "real" purchasing power over time, filtering out monetary inflation and currency debasement.

## Run Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Then open http://localhost:5000

## Features

- Enter any stock ticker (AAPL, MSFT, TSLA, etc.)
- Choose time range (1-20 years)
- See price in gold ounces over time
- Compare USD vs Gold performance
- Interactive chart with tooltips

## How it works

1. Fetches stock prices from Yahoo Finance
2. Fetches gold prices (Gold Futures GC=F)
3. Calculates: `stock_price_usd / gold_price_per_oz = stock_price_in_gold`
4. Shows the difference between USD gains and real (gold) gains

## Deploy

Works on Replit, Railway, Render, or any Python hosting.

Set `PORT` environment variable if needed.

---

Built with ⚡ by clawdbot
