# src/database.py

from datetime import datetime

import pytz
from sqlalchemy import (
    DECIMAL,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from framework.config.constants import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
Base = declarative_base()
Session = sessionmaker(bind=engine)

TIMEZONE = pytz.timezone("America/Toronto")

# ============================================================================
# MODELS
# ============================================================================


class Account(Base):
    """Track multiple personal and prop firm accounts"""

    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    account_type = Column(String(50), nullable=False)
    broker = Column(String(100))
    initial_balance = Column(DECIMAL(20, 8), nullable=False)
    current_balance = Column(DECIMAL(20, 8), nullable=False)
    currency = Column(String(10), default="USDT")
    api_key_encrypted = Column(Text)
    api_secret_encrypted = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(TIMEZONE),
        onupdate=lambda: datetime.now(TIMEZONE),
    )
    account_metadata = Column(JSONB)

    # Relationships
    positions = relationship(
        "Position", back_populates="account", cascade="all, delete-orphan"
    )
    trades = relationship(
        "Trade", back_populates="account", cascade="all, delete-orphan"
    )
    balance_history = relationship(
        "BalanceHistory", back_populates="account", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "account_type IN ('personal', 'prop_firm')", name="check_account_type"
        ),
    )


class OHLCVData(Base):
    """Time-series OHLCV data for all symbols and timeframes (TimescaleDB hypertable)"""

    __tablename__ = "ohlcv_data"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(20), primary_key=True, nullable=False)
    timeframe = Column(String(10), primary_key=True, nullable=False)
    open = Column(DECIMAL(20, 8), nullable=False)
    high = Column(DECIMAL(20, 8), nullable=False)
    low = Column(DECIMAL(20, 8), nullable=False)
    close = Column(DECIMAL(20, 8), nullable=False)
    volume = Column(DECIMAL(30, 8), nullable=False)
    quote_volume = Column(DECIMAL(30, 8))
    trades_count = Column(Integer)
    taker_buy_base_volume = Column(DECIMAL(30, 8))
    taker_buy_quote_volume = Column(DECIMAL(30, 8))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))


class Position(Base):
    """Current open positions per account"""

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    position_type = Column(String(10))
    quantity = Column(DECIMAL(20, 8), nullable=False)
    entry_price = Column(DECIMAL(20, 8), nullable=False)
    current_price = Column(DECIMAL(20, 8))
    stop_loss = Column(DECIMAL(20, 8))
    take_profit = Column(DECIMAL(20, 8))
    unrealized_pnl = Column(DECIMAL(20, 8))
    unrealized_pnl_percent = Column(DECIMAL(10, 4))
    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(TIMEZONE),
        onupdate=lambda: datetime.now(TIMEZONE),
    )
    position_metadata = Column(JSONB)

    # Relationships
    account = relationship("Account", back_populates="positions")

    __table_args__ = (
        CheckConstraint(
            "position_type IN ('LONG', 'SHORT')", name="check_position_type"
        ),
    )


class Trade(Base):
    """Complete trading history (TimescaleDB hypertable)"""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    time = Column(DateTime(timezone=True), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    trade_type = Column(String(10), nullable=False)
    position_side = Column(String(10))
    quantity = Column(DECIMAL(20, 8), nullable=False)
    price = Column(DECIMAL(20, 8), nullable=False)
    fee = Column(DECIMAL(20, 8))
    fee_currency = Column(String(10))
    realized_pnl = Column(DECIMAL(20, 8))
    stop_loss = Column(DECIMAL(20, 8))
    take_profit = Column(DECIMAL(20, 8))
    order_type = Column(String(20))
    order_id = Column(String(100))
    is_entry = Column(Boolean, default=True)
    notes = Column(Text)
    strategy_name = Column(String(100))
    trade_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))

    # Relationships
    account = relationship("Account", back_populates="trades")

    __table_args__ = (
        CheckConstraint("trade_type IN ('BUY', 'SELL')", name="check_trade_type"),
        CheckConstraint(
            "position_side IN ('LONG', 'SHORT', 'BOTH')", name="check_position_side"
        ),
    )


class BalanceHistory(Base):
    """Account balance snapshots over time (TimescaleDB hypertable)"""

    __tablename__ = "balance_history"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    account_id = Column(
        Integer, ForeignKey("accounts.id"), primary_key=True, nullable=False
    )
    balance = Column(DECIMAL(20, 8), nullable=False)
    equity = Column(DECIMAL(20, 8), nullable=False)
    margin_used = Column(DECIMAL(20, 8))
    margin_available = Column(DECIMAL(20, 8))
    daily_pnl = Column(DECIMAL(20, 8))
    cumulative_pnl = Column(DECIMAL(20, 8))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))

    # Relationships
    account = relationship("Account", back_populates="balance_history")


class SyncStatus(Base):
    """Track data synchronization state for each symbol/timeframe"""

    __tablename__ = "sync_status"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)
    last_sync_time = Column(DateTime(timezone=True))
    oldest_data_time = Column(DateTime(timezone=True))
    newest_data_time = Column(DateTime(timezone=True))
    total_candles = Column(Integer, default=0)
    sync_status = Column(String(20), default="pending")
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(TIMEZONE),
        onupdate=lambda: datetime.now(TIMEZONE),
    )

    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", name="uq_symbol_timeframe"),
        CheckConstraint(
            "sync_status IN ('pending', 'syncing', 'completed', 'error')",
            name="check_sync_status",
        ),
    )


class IndicatorsCache(Base):
    """Pre-calculated technical indicators (TimescaleDB hypertable)"""

    __tablename__ = "indicators_cache"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    symbol = Column(String(20), primary_key=True, nullable=False)
    timeframe = Column(String(10), primary_key=True, nullable=False)
    indicator_name = Column(String(50), primary_key=True, nullable=False)
    value = Column(DECIMAL(20, 8))
    indicator_metadata = Column(JSONB)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))


class StrategyParameters(Base):
    """Store optimized strategy parameters"""

    __tablename__ = "strategy_parameters"

    id = Column(Integer, primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(20))
    timeframe = Column(String(10))
    parameters = Column(JSONB, nullable=False)
    performance_metrics = Column(JSONB)
    is_active = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(TIMEZONE),
        onupdate=lambda: datetime.now(TIMEZONE),
    )


# ============================================================================
# RAG KNOWLEDGE BASE MODELS
# ============================================================================


class Document(Base):
    """Store source documents for RAG knowledge base"""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    doc_type = Column(
        String(50), nullable=False
    )  # 'signal', 'backtest', 'trade_analysis', 'market_report', 'strategy', 'log'
    title = Column(String(500))
    content = Column(Text, nullable=False)
    source = Column(String(255))  # file path, url, or source identifier
    symbol = Column(String(20))  # related trading pair
    timeframe = Column(String(10))  # related timeframe
    doc_metadata = Column(JSONB)  # additional context (strategy name, metrics, etc.) - renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(TIMEZONE),
        onupdate=lambda: datetime.now(TIMEZONE),
    )

    # Relationships
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "doc_type IN ('signal', 'backtest', 'trade_analysis', 'market_report', 'strategy', 'log', 'insight', 'other')",
            name="check_doc_type",
        ),
    )


class DocumentChunk(Base):
    """Store document chunks with embeddings for semantic search"""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)  # order within document
    content = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float))  # pgvector will be used via raw SQL
    token_count = Column(Integer)
    chunk_metadata = Column(JSONB)  # chunk-specific metadata - renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))

    # Relationships
    document = relationship("Document", back_populates="chunks")

    __table_args__ = (Index("idx_document_chunks_document_id", "document_id"),)


class QueryHistory(Base):
    """Track RAG queries and responses for analysis"""

    __tablename__ = "query_history"

    id = Column(Integer, primary_key=True)
    query = Column(Text, nullable=False)
    response = Column(Text)
    retrieved_chunks = Column(JSONB)  # list of chunk IDs and relevance scores
    model_used = Column(String(50))
    query_type = Column(
        String(50)
    )  # 'strategy_suggestion', 'market_analysis', 'trade_insight', etc.
    response_time_ms = Column(Integer)
    user_feedback = Column(Integer)  # rating 1-5
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))

    __table_args__ = (Index("idx_query_history_created_at", "created_at"),)


class TradingInsight(Base):
    """Curated trading insights and lessons learned"""

    __tablename__ = "trading_insights"

    id = Column(Integer, primary_key=True)
    insight_type = Column(
        String(50), nullable=False
    )  # 'lesson_learned', 'pattern_observed', 'strategy_improvement', 'risk_observation'
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    symbol = Column(String(20))
    related_trades = Column(JSONB)  # trade IDs
    related_backtests = Column(JSONB)  # backtest IDs
    impact = Column(String(20))  # 'high', 'medium', 'low'
    category = Column(
        String(50)
    )  # 'technical', 'fundamental', 'risk_management', 'psychology'
    tags = Column(ARRAY(String))
    insight_metadata = Column(JSONB)  # renamed from 'metadata' to avoid SQLAlchemy conflict
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(TIMEZONE))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(TIMEZONE),
        onupdate=lambda: datetime.now(TIMEZONE),
    )

    __table_args__ = (
        CheckConstraint(
            "insight_type IN ('lesson_learned', 'pattern_observed', 'strategy_improvement', 'risk_observation', 'market_condition', 'other')",
            name="check_insight_type",
        ),
        CheckConstraint("impact IN ('high', 'medium', 'low')", name="check_impact"),
        Index("idx_trading_insights_symbol", "symbol"),
        Index("idx_trading_insights_category", "category"),
    )


# ============================================================================
# LEGACY COMPATIBILITY (keep old Trade model name for backward compatibility)
# ============================================================================
# This is kept for any existing code that imports Trade from database
# The new Trade model above replaces this completely


# Create all tables (will skip if they already exist from init.sql)
def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(engine)
    print("Database tables initialized successfully")


if __name__ == "__main__":
    init_db()
