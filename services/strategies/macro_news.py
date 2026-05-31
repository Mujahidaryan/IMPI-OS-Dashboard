import asyncio
import logging
import time
from typing import List, Dict, Any
import feedparser
from textblob import TextBlob

from services.strategies.base import BaseStrategy, StrategySignal
from services.features.feature_engine import FeatureVector

logger = logging.getLogger("MacroNewsStrategy")

FEEDS = [
    "https://feeds.reuters.com/reuters/businessNews",
    "https://www.fxstreet.com/rss/news",
    "https://www.investing.com/rss/news_301.rss",  # forex
    "https://www.investing.com/rss/news_25.rss",   # commodities (gold)
    "https://www.investing.com/rss/news_2.rss",    # economy
]

KEYWORDS = {
    "XAUUSD_EXNESS": ["gold", "XAU", "bullion", "haven", "safe-haven", "inflation",
                       "federal reserve", "fed", "interest rate", "dollar", "DXY",
                       "geopolitical", "war", "sanctions", "central bank"],
    "XAUUSDT":       ["gold", "XAU", "bullion", "futures", "COMEX", "haven"],
    "BTCUSDT":       ["bitcoin", "BTC", "crypto", "blockchain", "ETF", "halving",
                      "SEC", "regulation", "institutional", "whale", "on-chain"],
}


class MacroNewsStrategy(BaseStrategy):
    """
    RSS News Feed Fetcher + TextBlob NLP Sentiment polarity/subjectivity weighting.
    """

    def __init__(self):
        super().__init__("macro_news")
        self.cached_articles: List[Dict[str, Any]] = []
        self._running = False
        self._poll_task: asyncio.Task | None = None

    async def start(self):
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Macro News Strategy background task started.")

    async def stop(self):
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("Macro News Strategy background task stopped.")

    async def _poll_loop(self):
        while self._running:
            try:
                logger.info("Polling RSS news feeds...")
                articles = []
                for url in FEEDS:
                    feed_articles = await self._fetch_feed(url)
                    articles.extend(feed_articles)
                
                # Keep latest 100 articles to avoid memory bloat
                articles.sort(key=lambda x: x["published"] if x["published"] else 0, reverse=True)
                self.cached_articles = articles[:100]
                logger.info("Fetched %d RSS news articles.", len(self.cached_articles))
            except Exception as e:
                logger.error("Error in RSS polling loop: %s", str(e))
            
            await asyncio.sleep(300)  # Poll every 5 minutes

    async def _fetch_feed(self, url: str) -> List[Dict[str, Any]]:
        """Fetch feed asynchronously using thread execution wrapper."""
        def _parse():
            feed = feedparser.parse(url)
            parsed_articles = []
            for entry in feed.entries[:20]:
                parsed_articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", ""),
                    "published": entry.get("published_parsed"),
                })
            return parsed_articles
        
        try:
            return await asyncio.to_thread(_parse)
        except Exception as e:
            logger.error("Failed to fetch RSS feed %s: %s", url, str(e))
            return []

    async def generate_signal(self, symbol: str, features: FeatureVector) -> StrategySignal:
        keywords = KEYWORDS.get(symbol, [])
        if not keywords:
            # Fallback for unexpected symbol matching
            return StrategySignal(
                name=self.name, bull_logit=0.0, bear_logit=0.0,
                reversal_logit=0.0, breakout_logit=0.0, base_reliability=0.50
            )

        # Filter relevant articles based on keyword overlap
        relevant = []
        for a in self.cached_articles:
            text = (a["title"] + " " + a["summary"]).lower()
            if any(kw.lower() in text for kw in keywords):
                relevant.append(a)

        if not relevant:
            logger.debug("No relevant news articles found for symbol %s.", symbol)
            return StrategySignal(
                name=self.name, bull_logit=0.0, bear_logit=0.0,
                reversal_logit=0.0, breakout_logit=0.0, base_reliability=0.50
            )

        polarities = []
        weights = []
        subjectivities = []
        now = time.time()

        for a in relevant:
            blob = TextBlob(a["title"] + " " + a["summary"])
            polarity = blob.sentiment.polarity
            subjectivity = blob.sentiment.subjectivity
            
            # Recency weighting
            pub_struct = a["published"]
            age_minutes = 60.0
            if pub_struct:
                try:
                    pub_epoch = time.mktime(pub_struct)
                    age_minutes = (now - pub_epoch) / 60.0
                except Exception:
                    pass
            
            if age_minutes < 30.0:
                w = 2.0
            elif age_minutes < 120.0:
                w = 1.0
            else:
                w = 0.5

            polarities.append(polarity)
            weights.append(w)
            subjectivities.append(subjectivity)

        w_total = sum(weights)
        if w_total <= 0:
            return StrategySignal(
                name=self.name, bull_logit=0.0, bear_logit=0.0,
                reversal_logit=0.0, breakout_logit=0.0, base_reliability=0.50
            )

        w_sentiment = sum(p * w for p, w in zip(polarities, weights)) / w_total
        w_subjectivity = sum(s * w for s, w in zip(subjectivities, weights)) / w_total
        objectivity_weight = 1.0 - w_subjectivity

        bull_logit = max(w_sentiment, 0.0) * 0.6 * objectivity_weight
        bear_logit = max(-w_sentiment, 0.0) * 0.6 * objectivity_weight

        return StrategySignal(
            name=self.name,
            bull_logit=float(bull_logit),
            bear_logit=float(bear_logit),
            reversal_logit=0.1,
            breakout_logit=0.1,
            base_reliability=0.50
        )
