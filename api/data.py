"""Vercel Serverless Function for Stock vs Gold API."""

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse
from datetime import datetime, timedelta

# Install dependencies via requirements.txt in api folder
import yfinance as yf

GOLD_TICKER = "GC=F"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Parse query params
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        ticker = params.get('ticker', ['AAPL'])[0].upper()
        years = int(params.get('years', ['10'])[0])
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years * 365)
        
        try:
            # Fetch stock data
            stock = yf.Ticker(ticker)
            stock_hist = stock.history(start=start_date, end=end_date)
            
            if stock_hist.empty:
                self.send_error_response(404, f'No data found for {ticker}')
                return
            
            # Fetch gold data
            gold = yf.Ticker(GOLD_TICKER)
            gold_hist = gold.history(start=start_date, end=end_date)
            
            if gold_hist.empty:
                self.send_error_response(500, 'Could not fetch gold prices')
                return
            
            # Get current gold price
            current_gold_price = gold_hist['Close'].iloc[-1]
            
            # Align dates
            stock_df = stock_hist[['Close']].rename(columns={'Close': 'stock_price'})
            gold_df = gold_hist[['Close']].rename(columns={'Close': 'gold_price'})
            merged = stock_df.join(gold_df, how='inner')
            merged['stock_in_gold'] = merged['stock_price'] / merged['gold_price']
            
            # Get company info
            info = {}
            try:
                info = stock.info
            except:
                pass
            
            # Extract metrics
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
            
            # Calculate gold values
            market_cap_gold = market_cap / current_gold_price if market_cap else None
            revenue_gold = revenue / current_gold_price if revenue else None
            fcf_gold = free_cash_flow / current_gold_price if free_cash_flow else None
            
            data = {
                'ticker': ticker,
                'company_name': info.get('shortName', ticker),
                'dates': [d.strftime('%Y-%m-%d') for d in merged.index],
                'stock_usd': [round(x, 2) for x in merged['stock_price'].tolist()],
                'gold_usd': [round(x, 2) for x in merged['gold_price'].tolist()],
                'stock_in_gold': [round(x, 6) for x in merged['stock_in_gold'].tolist()],
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
