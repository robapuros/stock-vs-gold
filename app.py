#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stock vs Gold - See stock prices measured in gold instead of fiat."""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import os

app = Flask(__name__, static_folder='static')
CORS(app)

# Gold proxy - GLD ETF (1 share ≈ 0.1 oz gold, but we use price ratio)
# For more accuracy, we could use actual gold spot, but GLD tracks well
GOLD_TICKER = "GC=F"  # Gold Futures (spot price proxy)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/data')
def get_data():
    ticker = request.args.get('ticker', 'AAPL').upper()
    years = int(request.args.get('years', 10))
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    
    try:
        # Fetch stock data
        stock = yf.Ticker(ticker)
        stock_hist = stock.history(start=start_date, end=end_date)
        
        if stock_hist.empty:
            return jsonify({'error': f'No data found for {ticker}'}), 404
        
        # Fetch gold data
        gold = yf.Ticker(GOLD_TICKER)
        gold_hist = gold.history(start=start_date, end=end_date)
        
        if gold_hist.empty:
            return jsonify({'error': 'Could not fetch gold prices'}), 500
        
        # Align dates - only use dates where we have both
        stock_df = stock_hist[['Close']].rename(columns={'Close': 'stock_price'})
        gold_df = gold_hist[['Close']].rename(columns={'Close': 'gold_price'})
        
        # Merge on date index
        merged = stock_df.join(gold_df, how='inner')
        
        # Calculate stock price in gold (oz)
        # Gold futures are per troy oz
        merged['stock_in_gold'] = merged['stock_price'] / merged['gold_price']
        
        # Prepare response
        data = {
            'ticker': ticker,
            'dates': [d.strftime('%Y-%m-%d') for d in merged.index],
            'stock_usd': merged['stock_price'].round(2).tolist(),
            'gold_usd': merged['gold_price'].round(2).tolist(),
            'stock_in_gold': merged['stock_in_gold'].round(6).tolist(),
            'stats': {
                'start_price_usd': round(merged['stock_price'].iloc[0], 2),
                'end_price_usd': round(merged['stock_price'].iloc[-1], 2),
                'change_usd_pct': round((merged['stock_price'].iloc[-1] / merged['stock_price'].iloc[0] - 1) * 100, 2),
                'start_price_gold': round(merged['stock_in_gold'].iloc[0], 6),
                'end_price_gold': round(merged['stock_in_gold'].iloc[-1], 6),
                'change_gold_pct': round((merged['stock_in_gold'].iloc[-1] / merged['stock_in_gold'].iloc[0] - 1) * 100, 2),
                'start_gold_price': round(merged['gold_price'].iloc[0], 2),
                'end_gold_price': round(merged['gold_price'].iloc[-1], 2),
            }
        }
        
        # Get company name
        try:
            data['company_name'] = stock.info.get('shortName', ticker)
        except:
            data['company_name'] = ticker
        
        return jsonify(data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
