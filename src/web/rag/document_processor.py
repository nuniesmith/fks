"""
Document processor for RAG system.
Handles chunking of documents, logs, and trading insights using sliding window approach.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

import tiktoken


@dataclass
class Chunk:
    """Represents a document chunk"""

    content: str
    chunk_index: int
    token_count: int
    metadata: dict[str, Any]


class DocumentProcessor:
    """Process documents for RAG knowledge base"""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        model_name: str = "gpt-3.5-turbo",
    ):
        """
        Initialize document processor.

        Args:
            chunk_size: Target size of each chunk in tokens
            chunk_overlap: Number of overlapping tokens between chunks
            model_name: OpenAI model name for tokenization
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.encoding = tiktoken.encoding_for_model(model_name)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))

    def chunk_text(
        self, text: str, metadata: dict[str, Any] | None = None
    ) -> list[Chunk]:
        """
        Chunk text using sliding window approach.

        Args:
            text: Text to chunk
            metadata: Optional metadata to include with each chunk

        Returns:
            List of Chunk objects
        """
        if not text or not text.strip():
            return []

        # Clean text
        text = self._clean_text(text)

        # Tokenize
        tokens = self.encoding.encode(text)

        chunks = []
        start_idx = 0
        chunk_index = 0

        while start_idx < len(tokens):
            # Get chunk tokens
            end_idx = min(start_idx + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start_idx:end_idx]

            # Decode back to text
            chunk_text = self.encoding.decode(chunk_tokens)

            # Create chunk
            chunk = Chunk(
                content=chunk_text.strip(),
                chunk_index=chunk_index,
                token_count=len(chunk_tokens),
                metadata=metadata or {},
            )
            chunks.append(chunk)

            # Move to next chunk with overlap
            start_idx += self.chunk_size - self.chunk_overlap
            chunk_index += 1

            # Break if we've processed all tokens
            if end_idx >= len(tokens):
                break

        return chunks

    def chunk_trading_signal(self, signal_data: dict[str, Any]) -> list[Chunk]:
        """
        Chunk trading signal data.

        Args:
            signal_data: Signal dictionary with fields like symbol, action, indicators, etc.

        Returns:
            List of Chunk objects
        """
        # Format signal as natural language
        text = self._format_signal_text(signal_data)

        metadata = {
            "type": "signal",
            "symbol": signal_data.get("symbol"),
            "action": signal_data.get("action"),
            "timestamp": signal_data.get("timestamp"),
        }

        return self.chunk_text(text, metadata)

    def chunk_backtest_result(self, backtest_data: dict[str, Any]) -> list[Chunk]:
        """
        Chunk backtest results.

        Args:
            backtest_data: Backtest results with metrics, trades, etc.

        Returns:
            List of Chunk objects
        """
        text = self._format_backtest_text(backtest_data)

        metadata = {
            "type": "backtest",
            "strategy": backtest_data.get("strategy_name"),
            "symbol": backtest_data.get("symbol"),
            "timeframe": backtest_data.get("timeframe"),
            "total_return": backtest_data.get("total_return"),
            "win_rate": backtest_data.get("win_rate"),
        }

        return self.chunk_text(text, metadata)

    def chunk_trade_analysis(self, trade_data: dict[str, Any]) -> list[Chunk]:
        """
        Chunk trade analysis.

        Args:
            trade_data: Trade data with entry, exit, PnL, etc.

        Returns:
            List of Chunk objects
        """
        text = self._format_trade_text(trade_data)

        metadata = {
            "type": "trade",
            "symbol": trade_data.get("symbol"),
            "side": trade_data.get("position_side"),
            "pnl": trade_data.get("realized_pnl"),
            "timestamp": trade_data.get("time"),
        }

        return self.chunk_text(text, metadata)

    def chunk_market_report(
        self, report_text: str, symbol: str, timeframe: str
    ) -> list[Chunk]:
        """
        Chunk market analysis report.

        Args:
            report_text: Market analysis text
            symbol: Trading pair
            timeframe: Timeframe

        Returns:
            List of Chunk objects
        """
        metadata = {
            "type": "market_report",
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": datetime.now().isoformat(),
        }

        return self.chunk_text(report_text, metadata)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove special characters that might interfere
        text = re.sub(r"[^\w\s\.\,\!\?\-\:\;\(\)\[\]\{\}\/\'\"]", "", text)
        return text.strip()

    def _format_signal_text(self, signal: dict[str, Any]) -> str:
        """Format signal data as natural language"""
        parts = [
            f"Trading Signal for {signal.get('symbol', 'Unknown')}",
            f"Action: {signal.get('action', 'HOLD')}",
            f"Timestamp: {signal.get('timestamp', datetime.now().isoformat())}",
        ]

        # Add indicators
        if "indicators" in signal:
            parts.append("Technical Indicators:")
            for indicator, value in signal["indicators"].items():
                parts.append(f"  - {indicator}: {value}")

        # Add price info
        if "price" in signal:
            parts.append(f"Current Price: {signal['price']}")

        if "stop_loss" in signal:
            parts.append(f"Stop Loss: {signal['stop_loss']}")

        if "take_profit" in signal:
            parts.append(f"Take Profit: {signal['take_profit']}")

        # Add reasoning if available
        if "reasoning" in signal:
            parts.append(f"Reasoning: {signal['reasoning']}")

        return "\n".join(parts)

    def _format_backtest_text(self, backtest: dict[str, Any]) -> str:
        """Format backtest results as natural language"""
        parts = [
            f"Backtest Results: {backtest.get('strategy_name', 'Unknown Strategy')}",
            f"Symbol: {backtest.get('symbol', 'N/A')} | Timeframe: {backtest.get('timeframe', 'N/A')}",
            f"Period: {backtest.get('start_date', 'N/A')} to {backtest.get('end_date', 'N/A')}",
            "",
            "Performance Metrics:",
            f"  - Total Return: {backtest.get('total_return', 0):.2f}%",
            f"  - Win Rate: {backtest.get('win_rate', 0):.2f}%",
            f"  - Sharpe Ratio: {backtest.get('sharpe_ratio', 0):.2f}",
            f"  - Max Drawdown: {backtest.get('max_drawdown', 0):.2f}%",
            f"  - Total Trades: {backtest.get('total_trades', 0)}",
        ]

        # Add strategy parameters
        if "parameters" in backtest:
            parts.append("\nStrategy Parameters:")
            for param, value in backtest["parameters"].items():
                parts.append(f"  - {param}: {value}")

        # Add insights if available
        if "insights" in backtest:
            parts.append(f"\nInsights: {backtest['insights']}")

        return "\n".join(parts)

    def _format_trade_text(self, trade: dict[str, Any]) -> str:
        """Format trade data as natural language"""
        parts = [
            f"Trade: {trade.get('symbol', 'Unknown')} {trade.get('position_side', 'N/A')}",
            f"Entry Price: {trade.get('entry_price', 0)} | Exit Price: {trade.get('exit_price', 0)}",
            f"Quantity: {trade.get('quantity', 0)}",
            f"Realized PnL: {trade.get('realized_pnl', 0)} ({trade.get('pnl_percent', 0):.2f}%)",
            f"Duration: {trade.get('duration', 'N/A')}",
            f"Timestamp: {trade.get('time', 'N/A')}",
        ]

        if "strategy_name" in trade:
            parts.append(f"Strategy: {trade['strategy_name']}")

        if "notes" in trade:
            parts.append(f"Notes: {trade['notes']}")

        return "\n".join(parts)


# Convenience functions
def create_processor(
    chunk_size: int = 512, chunk_overlap: int = 50
) -> DocumentProcessor:
    """Create a document processor with default settings"""
    return DocumentProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
