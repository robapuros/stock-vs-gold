"""Vercel Serverless Function for Stock vs Gold API."""

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse, quote
from urllib.request import Request, urlopen
from datetime import datetime, timedelta

import yfinance as yf
import numpy as np

GOLD_TICKER = "GC=F"

def calculate_sma(data, period):
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
    if len(data) < period:
        return [None] * len(data)
    ema = [None] * (period - 1)
    sma = sum(data[:period]) / period
    ema.append(round(sma, 6))
    multiplier = 2 / (period + 1)
    for i in range(period, len(data)):
        val = (data[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(round(val, 6))
    return ema

def calculate_rsi(data, period=14):
    if len(data) < period + 1:
        return [None] * len(data)
    
    rsi = [None] * period
    gains, losses = [], []
    
    for i in range(1, len(data)):
        change = data[i] - data[i-1]
        gains.append(max(0, change))
        losses.append(max(0, -change))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    if avg_loss == 0:
        rsi.append(100)
    else:
        rs = avg_gain / avg_loss
        rsi.append(round(100 - (100 / (1 + rs)), 2))
    
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
    
    macd_values = [x for x in macd_line if x is not None]
    if len(macd_values) < signal:
        return macd_line, [None] * len(data), [None] * len(data)
    
    signal_line = [None] * (slow - 1)
    ema_signal = calculate_ema(macd_values, signal)
    signal_line.extend(ema_signal)
    
    histogram = []
    for i in range(len(data)):
        if macd_line[i] is None or i >= len(signal_line) or signal_line[i] is None:
            histogram.append(None)
        else:
            histogram.append(round(macd_line[i] - signal_line[i], 6))
    
    return macd_line, signal_line, histogram

def calculate_bollinger(data, period=20, std_dev=2):
    if len(data) < period:
        return [None] * len(data), [None] * len(data), [None] * len(data)
    
    sma = calculate_sma(data, period)
    upper, lower = [], []
    
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

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    if len(close) < k_period:
        return [None] * len(close), [None] * len(close)
    
    k_values = [None] * (k_period - 1)
    
    for i in range(k_period - 1, len(close)):
        highest_high = max(high[i-k_period+1:i+1])
        lowest_low = min(low[i-k_period+1:i+1])
        if highest_high - lowest_low == 0:
            k_values.append(50)
        else:
            k = ((close[i] - lowest_low) / (highest_high - lowest_low)) * 100
            k_values.append(round(k, 2))
    
    d_values = calculate_sma(k_values, d_period)
    return k_values, d_values

def search_tickers(query):
    try:
        url = f"https://query2.finance.yahoo.com/v1/finance/search?q={quote(query)}&quotesCount=10&newsCount=0"
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            quotes = data.get('quotes', [])
            results = []
            for q in quotes:
                if q.get('quoteType') in ['EQUITY', 'ETF', 'MUTUALFUND', 'INDEX']:
                    results.append({
                        'symbol': q.get('symbol', ''),
                        'name': q.get('shortname') or q.get('longname', ''),
                        'exchange': q.get('exchange', ''),
                        'type': q.get('quoteType', '')
                    })
            return results
    except:
        return []

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
                suggestions = search_tickers(ticker.replace('.', ' '))
                self.send_error_response(404, f'No data found for {ticker}', suggestions)
                return
            
            gold = yf.Ticker(GOLD_TICKER)
            gold_hist = gold.history(start=start_date, end=end_date)
            
            if gold_hist.empty:
                self.send_error_response(500, 'Could not fetch gold prices')
                return
            
            current_gold_price = gold_hist['Close'].iloc[-1]
            
            # Merge stock and gold data
            stock_df = stock_hist[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
            gold_df = gold_hist[['Close']].rename(columns={'Close': 'gold_price'})
            merged = stock_df.join(gold_df, how='inner')
            
            # Calculate gold-denominated OHLC
            merged['open_gold'] = merged['Open'] / merged['gold_price']
            merged['high_gold'] = merged['High'] / merged['gold_price']
            merged['low_gold'] = merged['Low'] / merged['gold_price']
            merged['close_gold'] = merged['Close'] / merged['gold_price']
            
            gold_prices = merged['close_gold'].tolist()
            usd_prices = merged['Close'].tolist()
            high_gold = merged['high_gold'].tolist()
            low_gold = merged['low_gold'].tolist()
            volume = merged['Volume'].tolist()
            
            # Technical Indicators
            sma_20 = calculate_sma(gold_prices, 20)
            sma_50 = calculate_sma(gold_prices, 50)
            sma_200 = calculate_sma(gold_prices, 200)
            ema_12 = calculate_ema(gold_prices, 12)
            ema_26 = calculate_ema(gold_prices, 26)
            rsi = calculate_rsi(gold_prices, 14)
            macd_line, signal_line, macd_histogram = calculate_macd(gold_prices)
            bb_middle, bb_upper, bb_lower = calculate_bollinger(gold_prices, 20, 2)
            stoch_k, stoch_d = calculate_stochastic(high_gold, low_gold, gold_prices)
            
            # Volume SMA
            volume_sma = calculate_sma(volume, 20)
            
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
                'company_name': info.get('shortName') or info.get('longName') or ticker,
                'dates': [d.strftime('%Y-%m-%d') for d in merged.index],
                # OHLCV data
                'ohlc': {
                    'open': [round(x, 6) for x in merged['open_gold'].tolist()],
                    'high': [round(x, 6) for x in high_gold],
                    'low': [round(x, 6) for x in low_gold],
                    'close': [round(x, 6) for x in gold_prices],
                    'open_usd': [round(x, 2) for x in merged['Open'].tolist()],
                    'high_usd': [round(x, 2) for x in merged['High'].tolist()],
                    'low_usd': [round(x, 2) for x in merged['Low'].tolist()],
                    'close_usd': [round(x, 2) for x in usd_prices],
                },
                'volume': [int(v) for v in volume],
                'volume_sma': volume_sma,
                'stock_usd': [round(x, 2) for x in usd_prices],
                'gold_usd': [round(x, 2) for x in merged['gold_price'].tolist()],
                'stock_in_gold': [round(x, 6) for x in gold_prices],
                'stats': {
                    'start_price_usd': round(merged['Close'].iloc[0], 2),
                    'end_price_usd': round(merged['Close'].iloc[-1], 2),
                    'change_usd_pct': round((merged['Close'].iloc[-1] / merged['Close'].iloc[0] - 1) * 100, 2),
                    'start_price_gold': round(merged['close_gold'].iloc[0], 6),
                    'end_price_gold': round(merged['close_gold'].iloc[-1], 6),
                    'change_gold_pct': round((merged['close_gold'].iloc[-1] / merged['close_gold'].iloc[0] - 1) * 100, 2),
                    'start_gold_price': round(merged['gold_price'].iloc[0], 2),
                    'end_gold_price': round(merged['gold_price'].iloc[-1], 2),
                    'high_gold': round(max(high_gold), 6),
                    'low_gold': round(min(low_gold), 6),
                    'avg_volume': int(sum(volume) / len(volume)) if volume else 0,
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
                    'stoch_k': stoch_k,
                    'stoch_d': stoch_d,
                    'current_rsi': rsi[-1] if rsi and rsi[-1] else None,
                    'current_macd': macd_line[-1] if macd_line and macd_line[-1] else None,
                    'current_macd_signal': signal_line[-1] if signal_line and len(signal_line) > 0 and signal_line[-1] else None,
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
            
            self.send_json(data)
            
        except Exception as e:
            suggestions = search_tickers(ticker.replace('.', ' ').split('.')[0])
            self.send_error_response(500, str(e), suggestions)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, code, message, suggestions=None):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        response = {'error': message}
        if suggestions:
            response['suggestions'] = suggestions[:5]
        self.wfile.write(json.dumps(response).encode())
