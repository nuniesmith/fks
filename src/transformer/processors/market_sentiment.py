import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class FinancialSentimentAnalyzer:
    def __init__(self, config: dict):
        self.config = config
        self.model_name = config.get("model", "ProsusAI/finbert")
        self.tokenizer = None
        self.model = None

    async def initialize(self):
        """Load model and tokenizer"""
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.model_name)

        # Move to GPU if available
        if torch.cuda.is_available():
            self.model = self.model.cuda()

    async def analyze_text(self, text: str):
        """Analyze sentiment of financial text"""
        # Tokenize
        inputs = self.tokenizer(
            text, padding=True, truncation=True, max_length=512, return_tensors="pt"
        )

        # Move to GPU if available
        if torch.cuda.is_available():
            inputs = {k: v.cuda() for k, v in inputs.items()}

        # Predict
        with torch.no_grad():
            outputs = self.model(**inputs)

        # Process outputs
        predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)

        # Get sentiment scores
        positive = predictions[0][0].item()
        negative = predictions[0][1].item()
        neutral = predictions[0][2].item()

        return {
            "positive": positive,
            "negative": negative,
            "neutral": neutral,
            "compound": positive - negative,
            "dominant": max(
                [("positive", positive), ("negative", negative), ("neutral", neutral)],
                key=lambda x: x[1],
            )[0],
        }
