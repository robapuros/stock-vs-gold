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

# Gold proxy - Gold Futures (spot price proxy)
GOLD_TICKER = "GC=F"

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
        
        # Get current gold price for market cap calculation
        current_gold_price = gold_hist['Close'].iloc[-1]
        
        # Align dates - only use dates where we have both
        stock_df = stock_hist[['Close']].rename(columns={'Close': 'stock_price'})
        gold_df = gold_hist[['Close']].rename(columns={'Close': 'gold_price'})
        
        # Merge on date index
        merged = stock_df.join(gold_df, how='inner')
        
        # Calculate stock price in gold (oz)
        merged['stock_in_gold'] = merged['stock_price'] / merged['gold_price']
        
        # Get company info for metrics
        info = {}
        try:
            info = stock.info
        except:
            pass
        
        # Extract key metrics
        market_cap = info.get('marketCap', None)
        pe_ratio = info.get('trailingPE', None)
        forward_pe = info.get('forwardPE', None)
        peg_ratio = info.get('pegRatio', None)
        price_to_book = info.get('priceToBook', None)
        dividend_yield = info.get('dividendYield', None)
        eps = info.get('trailingEps', None)
        revenue = info.get('totalRevenue', None)
        profit_margin = info.get('profitMargins', None)
        debt_to_equity = info.get('debtToEquity', None)
        free_cash_flow = info.get('freeCashflow', None)
        shares_outstanding = info.get('sharesOutstanding', None)
        fifty_two_week_high = info.get('fiftyTwoWeekHigh', None)
        fifty_two_week_low = info.get('fiftyTwoWeekLow', None)
        
        # Calculate market cap in gold
        market_cap_gold = None
        if market_cap and current_gold_price:
            market_cap_gold = market_cap / current_gold_price
        
        # Calculate revenue in gold
        revenue_gold = None
        if revenue and current_gold_price:
            revenue_gold = revenue / current_gold_price
        
        # Calculate free cash flow in gold
        fcf_gold = None
        if free_cash_flow and current_gold_price:
            fcf_gold = free_cash_flow / current_gold_price
        
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
            },
            'metrics': {
                'market_cap_usd': market_cap,
                'market_cap_gold': round(market_cap_gold, 2) if market_cap_gold else None,
                'pe_ratio': round(pe_ratio, 2) if pe_ratio else None,
                'forward_pe': round(forward_pe, 2) if forward_pe else None,
                'peg_ratio': round(peg_ratio, 2) if peg_ratio else None,
                'price_to_book': round(price_to_book, 2) if price_to_book else None,
                'dividend_yield': round(dividend_yield * 100, 2) if dividend_yield else None,
                'eps': round(eps, 2) if eps else None,
                'revenue_usd': revenue,
                'revenue_gold': round(revenue_gold, 2) if revenue_gold else None,
                'profit_margin': round(profit_margin * 100, 2) if profit_margin else None,
                'debt_to_equity': round(debt_to_equity, 2) if debt_to_equity else None,
                'free_cash_flow_usd': free_cash_flow,
                'free_cash_flow_gold': round(fcf_gold, 2) if fcf_gold else None,
                'shares_outstanding': shares_outstanding,
                '52w_high': round(fifty_two_week_high, 2) if fifty_two_week_high else None,
                '52w_low': round(fifty_two_week_low, 2) if fifty_two_week_low else None,
                'current_gold_price': round(current_gold_price, 2),
            }
        }
        
        # Get company name
        try:
            data['company_name'] = info.get('shortName', ticker)
        except:
            data['company_name'] = ticker
        
        return jsonify(data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
