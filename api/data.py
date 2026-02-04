"""Vercel Serverless Function for Stock vs Gold API."""

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timedelta

import yfinance as yf
import numpy as np

GOLD_TICKER = "GC=F"

def calculate_sma(data, period):
    """Calculate Simple Moving Average."""
    if len(data) < period:
        return [None] * len(data)
    sma = []
    for i in range(len(data)):
        if i < period - 1:
            sma.append(None)
        else:
            sma.append(round(sum(data[i-period+1:i+1]) / period, 6))
    return sma

def calculate_ema(data, period):
    """Calculate Exponential Moving Average."""
    if len(data) < period:
        return [None] * len(data)
    ema = [None] * (period - 1)
    # First EMA is SMA
    sma = sum(data[:period]) / period
    ema.append(round(sma, 6))
    multiplier = 2 / (period + 1)
    for i in range(period, len(data)):
        val = (data[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(round(val, 6))
    return ema

def calculate_rsi(data, period=14):
    """Calculate Relative Strength Index."""
    if len(data) < period + 1:
        return [None] * len(data)
    
    rsi = [None] * period
    gains = []
    losses = []
    
    # Calculate price changes
    for i in range(1, len(data)):
        change = data[i] - data[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    # First RSI
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        rsi.append(100)
    else:
        rs = avg_gain / avg_loss
        rsi.append(round(100 - (100 / (1 + rs)), 2))
    
    # Subsequent RSI values
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(round(100 - (100 / (1 + rs)), 2))
    
    return rsi

def calculate_macd(data, fast=12, slow=26, signal=9):
    """Calculate MACD, Signal line, and Histogram."""
    if len(data) < slow:
        return [None] * len(data), [None] * len(data), [None] * len(data)
    
    ema_fast = calculate_ema(data, fast)
    ema_slow = calculate_ema(data, slow)
    
    macd_line = []
    for i in range(len(data)):
        if ema_fast[i] is None or ema_slow[i] is None:
            macd_line.append(None)
        else:
            macd_line.append(round(ema_fast[i] - ema_slow[i], 6))
    
    # Signal line (EMA of MACD)
    macd_values = [x for x in macd_line if x is not None]
    if len(macd_values) < signal:
        return macd_line, [None] * len(data), [None] * len(data)
    
    signal_line = [None] * (slow - 1)
    ema_signal = calculate_ema(macd_values, signal)
    signal_line.extend(ema_signal)
    
    # Histogram
    histogram = []
    for i in range(len(data)):
        if macd_line[i] is None or signal_line[i] is None:
            histogram.append(None)
        else:
            histogram.append(round(macd_line[i] - signal_line[i], 6))
    
    return macd_line, signal_line, histogram

def calculate_bollinger(data, period=20, std_dev=2):
    """Calculate Bollinger Bands."""
    if len(data) < period:
        return [None] * len(data), [None] * len(data), [None] * len(data)
    
    sma = calculate_sma(data, period)
    upper = []
    lower = []
    
    for i in range(len(data)):
        if i < period - 1:
            upper.append(None)
            lower.append(None)
        else:
            window = data[i-period+1:i+1]
            std = np.std(window)
            upper.append(round(sma[i] + std_dev * std, 6))
            lower.append(round(sma[i] - std_dev * std, 6))
    
    return sma, upper, lower

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        ticker = params.get('ticker', ['AAPL'])[0].upper()
        years = int(params.get('years', ['10'])[0])
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        try:
            stock = yf.Ticker(ticker)
            stock_hist = stock.history(start=start_date, end=end_date)
            
            if stock_hist.empty:
                self.send_error_response(404, f'No data found for {ticker}')
                return
            
            gold = yf.Ticker(GOLD_TICKER)
            gold_hist = gold.history(start=start_date, end=end_date)
            
            if gold_hist.empty:
                self.send_error_response(500, 'Could not fetch gold prices')
                return
            
            current_gold_price = gold_hist['Close'].iloc[-1]
            
            stock_df = stock_hist[['Close']].rename(columns={'Close': 'stock_price'})
            gold_df = gold_hist[['Close']].rename(columns={'Close': 'gold_price'})
            merged = stock_df.join(gold_df, how='inner')
            merged['stock_in_gold'] = merged['stock_price'] / merged['gold_price']
            
            # Get data as lists for TA calculations
            gold_prices = merged['stock_in_gold'].tolist()
            usd_prices = merged['stock_price'].tolist()
            
            # Calculate Technical Indicators (on gold-denominated prices)
            sma_20 = calculate_sma(gold_prices, 20)
            sma_50 = calculate_sma(gold_prices, 50)
            sma_200 = calculate_sma(gold_prices, 200)
            ema_12 = calculate_ema(gold_prices, 12)
            ema_26 = calculate_ema(gold_prices, 26)
            rsi = calculate_rsi(gold_prices, 14)
            macd_line, signal_line, macd_histogram = calculate_macd(gold_prices)
            bb_middle, bb_upper, bb_lower = calculate_bollinger(gold_prices, 20, 2)
            
            info = {}
            try:
                info = stock.info
            except:
                pass
            
            market_cap = info.get('marketCap')
            pe_ratio = info.get('trailingPE')
            forward_pe = info.get('forwardPE')
            peg_ratio = info.get('pegRatio')
            price_to_book = info.get('priceToBook')
            dividend_yield = info.get('dividendYield')
            eps = info.get('trailingEps')
            revenue = info.get('totalRevenue')
            profit_margin = info.get('profitMargins')
            debt_to_equity = info.get('debtToEquity')
            free_cash_flow = info.get('freeCashflow')
            fifty_two_week_high = info.get('fiftyTwoWeekHigh')
            fifty_two_week_low = info.get('fiftyTwoWeekLow')
            
            market_cap_gold = market_cap / current_gold_price if market_cap else None
            revenue_gold = revenue / current_gold_price if revenue else None
            fcf_gold = free_cash_flow / current_gold_price if free_cash_flow else None
            
            data = {
                'ticker': ticker,
                'company_name': info.get('shortName', ticker),
                'dates': [d.strftime('%Y-%m-%d') for d in merged.index],
                'stock_usd': [round(x, 2) for x in usd_prices],
                'gold_usd': [round(x, 2) for x in merged['gold_price'].tolist()],
                'stock_in_gold': [round(x, 6) for x in gold_prices],
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
                'technical': {
                    'sma_20': sma_20,
                    'sma_50': sma_50,
                    'sma_200': sma_200,
                    'ema_12': ema_12,
                    'ema_26': ema_26,
                    'rsi': rsi,
                    'macd': macd_line,
                    'macd_signal': signal_line,
                    'macd_histogram': macd_histogram,
                    'bb_upper': bb_upper,
                    'bb_middle': bb_middle,
                    'bb_lower': bb_lower,
                    'current_rsi': rsi[-1] if rsi and rsi[-1] else None,
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
                    '52w_high': round(fifty_two_week_high, 2) if fifty_two_week_high else None,
                    '52w_low': round(fifty_two_week_low, 2) if fifty_two_week_low else None,
                    'current_gold_price': round(current_gold_price, 2),
                }
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            
        except Exception as e:
            self.send_error_response(500, str(e))
    
    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode())
