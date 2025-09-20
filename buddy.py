import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
from dataclasses import dataclass
from flask import Flask, render_template_string, request, jsonify
import threading
import yfinance as yf
import pandas as pd
from textblob import TextBlob
import re
import os
from urllib.parse import quote
import random
import random

@dataclass
class MarketData:
    symbol: str
    price: float
    change: float
    change_percent: float
    volume: int
    timestamp: datetime

@dataclass
class NewsItem:
    title: str
    summary: str
    url: str
    sentiment: float
    timestamp: datetime
    symbols: List[str]

class RealTimeDataSource:
    """Real-time market data and news feeds with actual APIs"""
    
    def __init__(self):
        self.active_symbols = ['TSLA', 'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'NVDA']
        self.running = False
        
        # API Keys (you'll need to set these as environment variables or replace with your keys)
        self.newsapi_key = os.getenv('NEWSAPI_KEY', '')  # Get free key from newsapi.org
        self.alpha_vantage_key = os.getenv('ALPHA_VANTAGE_KEY', '')  # Get free key from alphavantage.co
        self.finnhub_key = os.getenv('FINNHUB_KEY', '')  # Get free key from finnhub.io
        
        # Fallback to free sources if no API keys
        self.use_free_sources = not any([self.newsapi_key, self.alpha_vantage_key, self.finnhub_key])
        
        # Rate limiting for API calls
        self.last_api_call = {}
        self.min_delay_between_calls = 30  # Much longer delay - 30 seconds between calls
        self.failed_symbols = {}  # Track failed symbols to avoid repeated failures
        self.api_healthy = True  # Track overall API health
        
        # Configure session for better API reliability
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # Aggressive rate limiting to get real data
        self.min_delay_between_calls = 30  # Much longer delay - 30 seconds between calls
        self.max_retries = 5  # More retry attempts
        
    def get_market_data(self, symbol: str) -> Optional[MarketData]:
        """Fetch real market data using yfinance with rate limiting"""
        # Check if symbol has failed recently (skip for 5 minutes)
        now = time.time()
        if symbol in self.failed_symbols:
            if now - self.failed_symbols[symbol] < 300:  # 5 minutes
                return None
            else:
                del self.failed_symbols[symbol]  # Remove old failure record
        
        # Check rate limiting
        if symbol in self.last_api_call:
            time_since_last = now - self.last_api_call[symbol]
            if time_since_last < self.min_delay_between_calls:
                print(f"Rate limiting: waiting {self.min_delay_between_calls - time_since_last:.1f}s for {symbol}")
                time.sleep(self.min_delay_between_calls - time_since_last)
        
        self.last_api_call[symbol] = time.time()
        
        # Try multiple approaches with VERY long delays for real data
        for attempt in range(5):  # 5 retry attempts for real data
            try:
                # Much longer delays to avoid rate limiting
                base_delay = 10 + (attempt * 5)  # 10, 15, 20, 25, 30 seconds
                jitter = random.uniform(0, 5)  # Add randomness
                total_delay = base_delay + jitter
                
                print(f"Attempt {attempt + 1}/5 for {symbol}, waiting {total_delay:.1f}s...")
                time.sleep(total_delay)
                
                # Method 1: Try multiple user agents
                user_agents = [
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                ]
                
                # Rotate user agent
                self.session.headers['User-Agent'] = random.choice(user_agents)
                
                ticker = yf.Ticker(symbol, session=self.session)
                
                # Method 2: Try info method first (often more reliable)
                if attempt == 0:
                    try:
                        info = ticker.info
                        if info and 'regularMarketPrice' in info:
                            current_price = float(info['regularMarketPrice'])
                            prev_close = float(info.get('previousClose', current_price))
                            change = current_price - prev_close
                            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                            volume = int(info.get('volume', 0))
                            
                            print(f"✅ Got real-time data for {symbol}: ${current_price:.2f} ({change_percent:+.2f}%)")
                            return MarketData(
                                symbol=symbol,
                                price=current_price,
                                change=change,
                                change_percent=change_percent,
                                volume=volume,
                                timestamp=datetime.now()
                            )
                    except Exception as info_error:
                        print(f"Info method failed for {symbol}: {info_error}")
                
                # Method 3: Try intraday data
                if attempt == 1:
                    # Alternative approach - use different period/interval
                    hist = ticker.history(period="1d", interval="5m", timeout=15)
                    if len(hist) > 0:
                        current_price = hist['Close'].iloc[-1]
                        open_price = hist['Open'].iloc[0]
                        volume = int(hist['Volume'].sum())
                        change = current_price - open_price
                        change_percent = (change / open_price) * 100 if open_price > 0 else 0
                        
                        print(f"✅ Got intraday data for {symbol}: ${current_price:.2f} ({change_percent:+.2f}%)")
                        return MarketData(
                            symbol=symbol,
                            price=float(current_price),
                            change=float(change),
                            change_percent=float(change_percent),
                            volume=volume,
                            timestamp=datetime.now()
                        )
                
                # Method 3: Try info method as fallback
                if attempt == 2:
                    try:
                        info = ticker.info
                        if info and 'regularMarketPrice' in info:
                            current_price = float(info['regularMarketPrice'])
                            prev_close = float(info.get('previousClose', current_price))
                            change = current_price - prev_close
                            change_percent = (change / prev_close) * 100 if prev_close > 0 else 0
                            volume = int(info.get('volume', 0))
                            
                            return MarketData(
                                symbol=symbol,
                                price=current_price,
                                change=change,
                                change_percent=change_percent,
                                volume=volume,
                                timestamp=datetime.now()
                            )
                    except Exception as info_error:
                        print(f"Info method failed for {symbol}: {info_error}")
                
                # Original method with improvements
                try:
                    # Add random delay to avoid rate limiting patterns
                    time.sleep(random.uniform(1, 3))
                    
                    fast_info = ticker.fast_info
                    if hasattr(fast_info, 'last_price') and fast_info.last_price:
                        # Get more detailed history for change calculation
                        hist = ticker.history(period="2d", interval="1d", timeout=15)
                        if len(hist) >= 1:
                            current_price = float(fast_info.last_price)
                            if len(hist) >= 2:
                                prev_price = hist['Close'].iloc[-2]
                                change = current_price - prev_price
                                change_percent = (change / prev_price) * 100
                            else:
                                # Fallback: use today's open vs close
                                open_price = hist['Open'].iloc[-1]
                                change = current_price - open_price
                                change_percent = (change / open_price) * 100 if open_price > 0 else 0
                            
                            volume = int(hist['Volume'].iloc[-1]) if len(hist) > 0 else 0
                            
                            return MarketData(
                                symbol=symbol,
                                price=current_price,
                                change=float(change),
                                change_percent=float(change_percent),
                                volume=volume,
                                timestamp=datetime.now()
                            )
                except Exception as e:
                    print(f"Fast info failed for {symbol}: {e}")
                
                # Fallback to regular history method
                hist = ticker.history(period="5d", interval="1d")  # Get more days for better data
                
                if len(hist) >= 1:
                    current_price = hist['Close'].iloc[-1]
                    if len(hist) >= 2:
                        prev_price = hist['Close'].iloc[-2]
                        change = current_price - prev_price
                        change_percent = (change / prev_price) * 100
                    else:
                        # Use open vs close for same day
                        open_price = hist['Open'].iloc[-1]
                        change = current_price - open_price
                        change_percent = (change / open_price) * 100 if open_price > 0 else 0
                    
                    volume = int(hist['Volume'].iloc[-1])
                    
                    return MarketData(
                        symbol=symbol,
                        price=float(current_price),
                        change=float(change),
                        change_percent=float(change_percent),
                        volume=volume,
                        timestamp=datetime.now()
                    )
                    
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    wait_time = (attempt + 1) * 10  # Longer backoff: 10, 20, 30 seconds
                    print(f"Rate limited for {symbol}, waiting {wait_time}s (attempt {attempt + 1}/3)")
                    self.api_healthy = False
                    time.sleep(wait_time)
                    continue
                elif "404" in error_msg or "Not Found" in error_msg:
                    print(f"Symbol {symbol} not found")
                    self.failed_symbols[symbol] = time.time()
                    break
                elif "Expecting value" in error_msg or "JSONDecodeError" in error_msg:
                    print(f"API returned invalid response for {symbol} (attempt {attempt + 1}/3)")
                    self.api_healthy = False
                    if attempt < 2:
                        time.sleep(5 + (attempt * 5))  # Progressive delay
                    continue
                else:
                    print(f"Error fetching data for {symbol} (attempt {attempt + 1}/3): {e}")
                    if attempt < 2:  # Don't sleep on last attempt
                        time.sleep(3)
        
        # All attempts failed - try alternative data source
        print(f"🔄 Trying alternative data sources for {symbol}...")
        alt_data = self._try_alternative_sources(symbol)
        if alt_data:
            return alt_data
            
        # All attempts failed - no real data available
        print(f"❌ Failed to get REAL market data for {symbol} after all attempts")
        self.failed_symbols[symbol] = time.time()
        return None
    
    def _try_alternative_sources(self, symbol: str) -> Optional[MarketData]:
        """Try alternative data sources for real market data"""
        
        # Method 1: Try Alpha Vantage free API
        try:
            print(f"🔄 Trying Alpha Vantage for {symbol}...")
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=demo"
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'Global Quote' in data:
                    quote = data['Global Quote']
                    current_price = float(quote.get('05. price', 0))
                    change = float(quote.get('09. change', 0))
                    change_percent = float(quote.get('10. change percent', '0%').replace('%', ''))
                    
                    if current_price > 0:
                        print(f"✅ Got Alpha Vantage data for {symbol}: ${current_price:.2f} ({change_percent:+.2f}%)")
                        return MarketData(
                            symbol=symbol,
                            price=current_price,
                            change=change,
                            change_percent=change_percent,
                            volume=int(quote.get('06. volume', 0)),
                            timestamp=datetime.now()
                        )
        except Exception as e:
            print(f"Alpha Vantage failed for {symbol}: {e}")
        
        # Method 2: Try IEX Cloud (free tier)
        try:
            print(f"🔄 Trying IEX Cloud for {symbol}...")
            url = f"https://cloud.iexapis.com/stable/stock/{symbol}/quote?token=pk_demo"
            response = self.session.get(url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                current_price = float(data.get('latestPrice', 0))
                change = float(data.get('change', 0))
                change_percent = float(data.get('changePercent', 0)) * 100
                volume = int(data.get('latestVolume', 0))
                
                if current_price > 0:
                    print(f"✅ Got IEX Cloud data for {symbol}: ${current_price:.2f} ({change_percent:+.2f}%)")
                    return MarketData(
                        symbol=symbol,
                        price=current_price,
                        change=change,
                        change_percent=change_percent,
                        volume=volume,
                        timestamp=datetime.now()
                    )
        except Exception as e:
            print(f"IEX Cloud failed for {symbol}: {e}")
            
        return None
    
    def get_news_data(self, symbol: str) -> List[NewsItem]:
        """Fetch real news for a symbol from multiple sources"""
        news_items = []
        
        try:
            # Try multiple news sources
            news_items.extend(self._get_yahoo_finance_news(symbol))
            news_items.extend(self._get_newsapi_news(symbol))
            news_items.extend(self._get_finnhub_news(symbol))
            news_items.extend(self._get_alpha_vantage_news(symbol))
            
            # Remove duplicates and sort by timestamp
            seen_titles = set()
            unique_news = []
            for item in news_items:
                if item.title not in seen_titles:
                    seen_titles.add(item.title)
                    unique_news.append(item)
            
            # Sort by timestamp (most recent first) and return top 5
            unique_news.sort(key=lambda x: x.timestamp, reverse=True)
            return unique_news[:5]
            
        except Exception as e:
            print(f"Error fetching news for {symbol}: {e}")
            return []
    
    def _get_yahoo_finance_news(self, symbol: str) -> List[NewsItem]:
        """Fetch news from Yahoo Finance (free)"""
        try:
            ticker = yf.Ticker(symbol)
            news = ticker.news
            
            news_items = []
            for item in news[:3]:  # Get top 3 articles
                # Analyze sentiment
                sentiment_score = TextBlob(item.get('title', '')).sentiment.polarity
                
                news_items.append(NewsItem(
                    title=item.get('title', 'No title'),
                    summary=item.get('summary', item.get('title', 'No summary available'))[:200] + '...',
                    url=item.get('link', ''),
                    sentiment=sentiment_score,
                    timestamp=datetime.fromtimestamp(item.get('providerPublishTime', time.time())),
                    symbols=[symbol]
                ))
            
            return news_items
        except Exception as e:
            print(f"Error fetching Yahoo Finance news: {e}")
            return []
    
    def _get_newsapi_news(self, symbol: str) -> List[NewsItem]:
        """Fetch news from NewsAPI (requires free API key)"""
        if not self.newsapi_key:
            return []
            
        try:
            company_names = {
                'TSLA': 'Tesla',
                'AAPL': 'Apple',
                'GOOGL': 'Google Alphabet',
                'MSFT': 'Microsoft',
                'AMZN': 'Amazon',
                'NVDA': 'NVIDIA'
            }
            
            query = f"{symbol} OR {company_names.get(symbol, symbol)}"
            url = f"https://newsapi.org/v2/everything"
            params = {
                'q': query,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': 5,
                'apiKey': self.newsapi_key,
                'domains': 'reuters.com,bloomberg.com,cnbc.com,marketwatch.com,yahoo.com'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news_items = []
                
                for article in data.get('articles', []):
                    if article.get('title') and article.get('title') != '[Removed]':
                        sentiment_score = TextBlob(article.get('description', '') or article.get('title', '')).sentiment.polarity
                        
                        news_items.append(NewsItem(
                            title=article.get('title'),
                            summary=article.get('description', 'No description available')[:200] + '...',
                            url=article.get('url', ''),
                            sentiment=sentiment_score,
                            timestamp=datetime.fromisoformat(article.get('publishedAt', '').replace('Z', '+00:00')),
                            symbols=[symbol]
                        ))
                
                return news_items
        except Exception as e:
            print(f"Error fetching NewsAPI news: {e}")
            return []
    
    def _get_finnhub_news(self, symbol: str) -> List[NewsItem]:
        """Fetch news from Finnhub (requires free API key)"""
        if not self.finnhub_key:
            return []
            
        try:
            # Get news from last 7 days
            from_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            to_date = datetime.now().strftime('%Y-%m-%d')
            
            url = f"https://finnhub.io/api/v1/company-news"
            params = {
                'symbol': symbol,
                'from': from_date,
                'to': to_date,
                'token': self.finnhub_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news_items = []
                
                for article in data[:3]:  # Get top 3 articles
                    sentiment_score = TextBlob(article.get('summary', '') or article.get('headline', '')).sentiment.polarity
                    
                    news_items.append(NewsItem(
                        title=article.get('headline', 'No title'),
                        summary=article.get('summary', 'No summary available')[:200] + '...',
                        url=article.get('url', ''),
                        sentiment=sentiment_score,
                        timestamp=datetime.fromtimestamp(article.get('datetime', time.time())),
                        symbols=[symbol]
                    ))
                
                return news_items
        except Exception as e:
            print(f"Error fetching Finnhub news: {e}")
            return []
    
    def _get_alpha_vantage_news(self, symbol: str) -> List[NewsItem]:
        """Fetch news from Alpha Vantage (requires free API key)"""
        if not self.alpha_vantage_key:
            return []
            
        try:
            url = f"https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'apikey': self.alpha_vantage_key,
                'limit': 5,
                'time_from': (datetime.now() - timedelta(days=7)).strftime('%Y%m%dT%H%M')
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                news_items = []
                
                for article in data.get('feed', [])[:3]:  # Get top 3 articles
                    # Alpha Vantage provides sentiment scores
                    ticker_sentiments = article.get('ticker_sentiment', [])
                    sentiment_score = 0
                    for ticker_sentiment in ticker_sentiments:
                        if ticker_sentiment.get('ticker') == symbol:
                            sentiment_score = float(ticker_sentiment.get('relevance_score', 0)) * float(ticker_sentiment.get('ticker_sentiment_score', 0))
                            break
                    
                    news_items.append(NewsItem(
                        title=article.get('title', 'No title'),
                        summary=article.get('summary', 'No summary available')[:200] + '...',
                        url=article.get('url', ''),
                        sentiment=sentiment_score,
                        timestamp=datetime.strptime(article.get('time_published', ''), '%Y%m%dT%H%M%S'),
                        symbols=[symbol]
                    ))
                
                return news_items
        except Exception as e:
            print(f"Error fetching Alpha Vantage news: {e}")
            return []

class TradingBuddy:
    """Main AI assistant for trading analysis"""
    
    def __init__(self):
        self.data_source = RealTimeDataSource()
        self.market_data_cache = {}
        self.news_cache = {}
        self.running = False
        
    def start_real_time_processing(self):
        """Start the real-time data processing pipeline"""
        self.running = True
        
        # Start background data collection
        threading.Thread(target=self._collect_market_data, daemon=True).start()
        threading.Thread(target=self._collect_news_data, daemon=True).start()
        
    def _collect_market_data(self):
        """Background thread to collect market data"""
        while self.running:
            for i, symbol in enumerate(self.data_source.active_symbols):
                try:
                    data = self.data_source.get_market_data(symbol)
                    if data:
                        self.market_data_cache[symbol] = data
                        print(f"Updated market data for {symbol}: ${data.price:.2f} ({data.change_percent:+.2f}%)")
                    else:
                        print(f"Failed to get market data for {symbol}")
                except Exception as e:
                    print(f"Error in background data collection for {symbol}: {e}")
                
                # Add LONG delay between symbols to avoid rate limiting
                if i < len(self.data_source.active_symbols) - 1:
                    time.sleep(60)  # 60 seconds between each symbol for real data
            
            time.sleep(1800)  # Update every 30 minutes (very conservative for real data)
    
    def _collect_news_data(self):
        """Background thread to collect news data"""
        while self.running:
            for i, symbol in enumerate(self.data_source.active_symbols):
                try:
                    news_items = self.data_source.get_news_data(symbol)
                    self.news_cache[symbol] = news_items
                    print(f"Updated news for {symbol}: {len(news_items)} articles")
                except Exception as e:
                    print(f"Error fetching news for {symbol}: {e}")
                
                # Add delay between symbols
                if i < len(self.data_source.active_symbols) - 1:
                    time.sleep(30)  # 30 seconds between each symbol for news
            
            time.sleep(3600)  # Update every 1 hour for news (very conservative)
    
    def analyze_stock_movement(self, symbol: str, question: str) -> Dict:
        """Analyze why a stock is moving based on real-time data"""
        symbol = symbol.upper()
        
        # Get current market data
        market_data = self.market_data_cache.get(symbol)
        news_items = self.news_cache.get(symbol, [])
        
        if not market_data:
            # Provide fallback information when API is having issues
            fallback_analysis = self._generate_fallback_analysis(symbol, question)
            return {
                'symbol': symbol,
                'current_price': 'API Unavailable',
                'change': 'API Issues',
                'change_percent': 'N/A',
                'volume': 'N/A',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'analysis': fallback_analysis,
                'news_items': [],
                'api_status': 'limited'
            }
        
        # Analyze the movement
        analysis = self._generate_analysis(market_data, news_items, question)
        
        return {
            'symbol': symbol,
            'current_price': f'${market_data.price:.2f}',
            'change': f'${market_data.change:+.2f}',
            'change_percent': f'{market_data.change_percent:+.2f}%',
            'volume': f'{market_data.volume:,}',
            'timestamp': market_data.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'analysis': analysis,
            'news_items': [
                {
                    'title': item.title,
                    'summary': item.summary,
                    'sentiment': 'Positive' if item.sentiment > 0.2 else 'Negative' if item.sentiment < -0.2 else 'Neutral',
                    'url': item.url
                } for item in news_items[:3]
            ],
            'api_status': 'healthy' if self.data_source.api_healthy else 'degraded'
        }
    
    def _generate_analysis(self, market_data: MarketData, news_items: List[NewsItem], question: str) -> str:
        """Generate AI-powered analysis of stock movement"""
        
        # Determine movement direction and magnitude
        if abs(market_data.change_percent) < 1:
            movement_desc = "relatively stable"
        elif market_data.change_percent > 3:
            movement_desc = "surging significantly"
        elif market_data.change_percent > 1:
            movement_desc = "rising"
        elif market_data.change_percent < -3:
            movement_desc = "dropping significantly"
        elif market_data.change_percent < -1:
            movement_desc = "declining"
        else:
            movement_desc = "moving"
        
        # Analyze news sentiment
        avg_sentiment = sum(item.sentiment for item in news_items) / len(news_items) if news_items else 0
        
        if avg_sentiment > 0.2:
            news_sentiment = "positive news sentiment"
        elif avg_sentiment < -0.2:
            news_sentiment = "negative news sentiment"
        else:
            news_sentiment = "mixed news sentiment"
        
        # Generate contextual analysis
        analysis = f"""
Based on real-time data as of {market_data.timestamp.strftime('%H:%M:%S')}, {market_data.symbol} is {movement_desc} 
at ${market_data.price:.2f} ({market_data.change_percent:+.2f}%).

Key factors driving the movement:

📊 **Price Action**: The stock has moved {market_data.change_percent:+.2f}% with {market_data.volume:,} shares traded, 
{'above' if market_data.volume > 1000000 else 'below'} average volume levels.

📰 **News Impact**: Current {news_sentiment} is {'supporting' if avg_sentiment > 0 else 'pressuring' if avg_sentiment < 0 else 'having mixed effects on'} 
the stock price. Recent headlines suggest {'bullish' if avg_sentiment > 0.3 else 'bearish' if avg_sentiment < -0.3 else 'neutral'} 
market sentiment.

🎯 **Market Context**: {'Strong' if abs(market_data.change_percent) > 2 else 'Moderate'} price movement indicates 
{'significant market interest' if abs(market_data.change_percent) > 3 else 'normal trading activity'}.

The real-time analysis suggests {'continued momentum' if abs(market_data.change_percent) > 2 else 'stabilization'} 
in the near term, though market conditions can change rapidly.
        """.strip()
        
        return analysis
    
    def _generate_fallback_analysis(self, symbol: str, question: str) -> str:
        """Generate analysis when real-time data is unavailable"""
        
        # Provide helpful context even without live data
        fallback_info = {
            'TSLA': "Tesla is known for high volatility driven by EV market trends, production updates, and regulatory news.",
            'AAPL': "Apple typically moves on product announcements, earnings, supply chain news, and broader tech sentiment.",
            'GOOGL': "Alphabet/Google responds to advertising market changes, AI developments, and regulatory concerns.",
            'MSFT': "Microsoft is influenced by cloud computing growth, enterprise software adoption, and AI initiatives.",
            'AMZN': "Amazon moves on e-commerce trends, AWS cloud performance, and logistics/shipping developments.",
            'NVDA': "NVIDIA is highly sensitive to AI/GPU demand, gaming trends, and semiconductor market conditions."
        }
        
        company_context = fallback_info.get(symbol, f"{symbol} is a actively traded stock that responds to market sentiment and company-specific news.")
        
        analysis = f"""
⚠️ **Live Data Currently Unavailable** - API experiencing high demand

📈 **About {symbol}**: {company_context}

🔍 **What to Watch For**:
• Company earnings reports and guidance updates  
• Industry-specific news and regulatory changes
• Broader market sentiment and economic indicators
• Analyst upgrades/downgrades and price target changes

💡 **Trading Context**: 
Stock movements are typically driven by a combination of company fundamentals, market sentiment, 
and external factors. Consider checking multiple news sources and official company communications 
for the most current information.

🔄 **Data Status**: We're working to restore live market data. Please check back shortly for 
real-time pricing and volume information.

For immediate live data, consider checking your broker's platform or financial news websites.
        """.strip()
        
        return analysis

# Flask Web Application
app = Flask(__name__)
trading_buddy = TradingBuddy()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Buddy - Real-Time Market Analysis</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(90deg, #2c3e50, #3498db);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            opacity: 0.9;
            font-size: 1.1em;
        }
        
        .chat-container {
            display: flex;
            height: 600px;
        }
        
        .sidebar {
            width: 250px;
            background: #f8f9fa;
            padding: 20px;
            border-right: 1px solid #e9ecef;
        }
        
        .popular-stocks {
            margin-bottom: 20px;
        }
        
        .popular-stocks h3 {
            margin-bottom: 15px;
            color: #2c3e50;
        }
        
        .stock-button {
            display: block;
            width: 100%;
            padding: 10px;
            margin-bottom: 8px;
            background: white;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .stock-button:hover {
            background: #e3f2fd;
            border-color: #2196f3;
        }
        
        .main-chat {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        
        .messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
        }
        
        .message {
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 10px;
        }
        
        .message.user {
            background: #e3f2fd;
            margin-left: 20%;
        }
        
        .message.ai {
            background: #f5f5f5;
            margin-right: 20%;
        }
        
        .input-area {
            padding: 20px;
            background: #f8f9fa;
            border-top: 1px solid #e9ecef;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
        }
        
        #userInput {
            flex: 1;
            padding: 12px;
            border: 1px solid #ced4da;
            border-radius: 8px;
            font-size: 16px;
        }
        
        #sendBtn {
            padding: 12px 25px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
        }
        
        #sendBtn:hover {
            background: #0056b3;
        }
        
        .loading {
            display: none;
            text-align: center;
            padding: 20px;
        }
        
        .market-data {
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 8px;
            padding: 15px;
            margin: 10px 0;
        }
        
        .news-item {
            background: white;
            border-left: 4px solid #007bff;
            padding: 12px;
            margin: 8px 0;
            border-radius: 4px;
        }
        
        .sentiment-positive { border-left-color: #28a745; }
        .sentiment-negative { border-left-color: #dc3545; }
        .sentiment-neutral { border-left-color: #6c757d; }
        
        @media (max-width: 768px) {
            .chat-container {
                flex-direction: column;
                height: auto;
            }
            .sidebar {
                width: 100%;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Trading Buddy</h1>
            <p>Real-time AI-powered market analysis at your fingertips</p>
        </div>
        
        <div class="chat-container">
            <div class="sidebar">
                <div class="popular-stocks">
                    <h3>📈 Popular Stocks</h3>
                    <button class="stock-button" onclick="askAboutStock('TSLA')">🚗 TSLA - Tesla</button>
                    <button class="stock-button" onclick="askAboutStock('AAPL')">🍎 AAPL - Apple</button>
                    <button class="stock-button" onclick="askAboutStock('GOOGL')">🔍 GOOGL - Google</button>
                    <button class="stock-button" onclick="askAboutStock('MSFT')">💻 MSFT - Microsoft</button>
                    <button class="stock-button" onclick="askAboutStock('NVDA')">🎮 NVDA - NVIDIA</button>
                    <button class="stock-button" onclick="askAboutStock('AMZN')">📦 AMZN - Amazon</button>
                </div>
                
                <div class="quick-questions">
                    <h3>💡 Quick Questions</h3>
                    <button class="stock-button" onclick="askQuestion('Market overview today')">Market Overview</button>
                    <button class="stock-button" onclick="askQuestion('Best performing stocks')">Top Performers</button>
                    <button class="stock-button" onclick="askQuestion('Market news summary')">News Summary</button>
                </div>
            </div>
            
            <div class="main-chat">
                <div class="messages" id="messages">
                    <div class="message ai">
                        <strong>Trading Buddy:</strong> Hello! I'm your real-time trading assistant with live news integration. Ask me about any stock movement, and I'll analyze current market data and breaking financial news to give you insights. Try asking "Why is Tesla's stock moving?" or click on any stock from the sidebar!
                    </div>
                </div>
                
                <div class="loading" id="loading">
                    <p>🔄 Analyzing real-time market data and news...</p>
                </div>
                
                <div class="input-area">
                    <div class="input-group">
                        <input type="text" id="userInput" placeholder="Ask about any stock... (e.g., 'Why is TSLA moving?')" 
                               onkeypress="handleKeyPress(event)">
                        <button id="sendBtn" onclick="sendMessage()">Send</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function addMessage(content, isUser = false) {
            const messages = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user' : 'ai'}`;
            messageDiv.innerHTML = content;
            messages.appendChild(messageDiv);
            messages.scrollTop = messages.scrollHeight;
        }

        function showLoading(show) {
            document.getElementById('loading').style.display = show ? 'block' : 'none';
        }

        async function sendMessage() {
            const input = document.getElementById('userInput');
            const question = input.value.trim();
            
            if (!question) return;
            
            addMessage(`<strong>You:</strong> ${question}`, true);
            input.value = '';
            showLoading(true);
            
            try {
                const response = await fetch('/analyze', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ question: question })
                });
                
                const data = await response.json();
                showLoading(false);
                
                if (data.error) {
                    addMessage(`<strong>Trading Buddy:</strong> ${data.error}. ${data.suggestion || ''}`);
                } else {
                    let response = `<strong>Trading Buddy:</strong><br><br>`;
                    
                    if (data.symbol) {
                        response += `
                            <div class="market-data">
                                <h4>📊 ${data.symbol} Real-Time Data</h4>
                                <p><strong>Price:</strong> ${data.current_price} (${data.change_percent})</p>
                                <p><strong>Volume:</strong> ${data.volume}</p>
                                <p><strong>Last Update:</strong> ${data.timestamp}</p>
                            </div>
                        `;
                    }
                    
                    response += `<div style="white-space: pre-line; margin: 15px 0;">${data.analysis}</div>`;
                    
                    if (data.news_items && data.news_items.length > 0) {
                        response += `<h4>📰 Related News:</h4>`;
                        data.news_items.forEach(item => {
                            response += `
                                <div class="news-item sentiment-${item.sentiment.toLowerCase()}">
                                    <h5>${item.title}</h5>
                                    <p>${item.summary}</p>
                                    <small>Sentiment: ${item.sentiment}</small>
                                </div>
                            `;
                        });
                    }
                    
                    addMessage(response);
                }
            } catch (error) {
                showLoading(false);
                addMessage('<strong>Trading Buddy:</strong> Sorry, I encountered an error analyzing the market data. Please try again.');
            }
        }

        function askAboutStock(symbol) {
            document.getElementById('userInput').value = `Why is ${symbol} moving today?`;
            sendMessage();
        }

        function askQuestion(question) {
            document.getElementById('userInput').value = question;
            sendMessage();
        }

        function handleKeyPress(event) {
            if (event.key === 'Enter') {
                sendMessage();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    question = data.get('question', '')
    
    # Extract symbol from question
    symbols = ['TSLA', 'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'NVDA']
    detected_symbol = None
    
    for symbol in symbols:
        if symbol.lower() in question.lower():
            detected_symbol = symbol
            break
    
    if not detected_symbol:
        return jsonify({
            'error': 'I couldn\'t detect a stock symbol in your question.',
            'suggestion': 'Try mentioning a specific stock like TSLA, AAPL, GOOGL, MSFT, AMZN, or NVDA.'
        })
    
    result = trading_buddy.analyze_stock_movement(detected_symbol, question)
    return jsonify(result)

@app.route('/status')
def status():
    """API status endpoint"""
    return jsonify({
        'api_healthy': trading_buddy.data_source.api_healthy,
        'failed_symbols': len(trading_buddy.data_source.failed_symbols),
        'cached_data': len(trading_buddy.market_data_cache),
        'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    print("🚀 Starting Trading Buddy...")
    print("📊 Initializing real-time data streams...")
    
    # Start the real-time processing
    trading_buddy.start_real_time_processing()
    
    print("✅ Trading Buddy is ready!")
    print("🌐 Access the app at: http://localhost:5000")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)