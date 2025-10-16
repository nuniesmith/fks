from framework.base import BaseService
from services.transformer.processors.market_sentiment import MarketSentimentAnalyzer
from services.transformer.processors.news import NewsProcessor


class TransformerService(BaseService):
    def __init__(self):
        super().__init__("transformer")
        self.sentiment_analyzer = None
        self.news_processor = None
        self.market_analyzer = None

    async def initialize(self):
        """Initialize transformer service"""
        # Initialize NLP models
        await self._initialize_nlp_models()

        # Initialize processors
        self.news_processor = NewsProcessor(self.config["news_processing"])

        self.market_analyzer = MarketSentimentAnalyzer(self.config["market_analysis"])

        # Setup processing pipeline
        await self._setup_pipeline()
