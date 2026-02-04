"""Vercel Serverless Function for ticker search/autocomplete."""

from http.server import BaseHTTPRequestHandler
import json
from urllib.parse import parse_qs, urlparse, quote
from urllib.request import Request, urlopen

def search_tickers(query):
    """Search for tickers using Yahoo Finance."""
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
    except Exception:
        return []

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        query = params.get('q', [''])[0]
        if len(query) < 1:
            self.send_json({'results': []})
            return
        
        results = search_tickers(query)
        self.send_json({'results': results})
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
