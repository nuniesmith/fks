#!/usr/bin/env python3
"""
Simple RAG System Example - Quick Start Guide

This script shows basic usage of the FKS Intelligence RAG system.
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datetime import datetime
from web.rag.intelligence import create_intelligence
from web.rag.ingestion import DataIngestionPipeline


def example_1_ingest_signal():
    """Example 1: Ingest a trading signal."""
    print("\n" + "="*70)
    print("Example 1: Ingest Trading Signal")
    print("="*70)
    
    # Create ingestion pipeline
    pipeline = DataIngestionPipeline()
    
    # Sample signal data
    signal = {
        'symbol': 'BTCUSDT',
        'action': 'BUY',
        'price': 42000.00,
        'timestamp': datetime.now().isoformat(),
        'timeframe': '1h',
        'indicators': {
            'rsi': 35.5,
            'macd': -50.2,
        },
        'confidence': 0.85,
        'reasoning': 'RSI oversold + MACD divergence'
    }
    
    # Ingest signal
    doc_id = pipeline.ingest_signal(signal)
    print(f"✓ Signal ingested as document {doc_id}")


def example_2_query_knowledge():
    """Example 2: Query the knowledge base."""
    print("\n" + "="*70)
    print("Example 2: Query Knowledge Base")
    print("="*70)
    
    # Create intelligence service
    intelligence = create_intelligence(use_local=True)
    
    # Query
    result = intelligence.query(
        "What are good entry points for Bitcoin?",
        symbol='BTCUSDT',
        top_k=5
    )
    
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nContext used: {result['context_used']} chunks")
    print(f"Response time: {result['response_time_ms']}ms")


def example_3_get_strategy_recommendation():
    """Example 3: Get trading strategy recommendation."""
    print("\n" + "="*70)
    print("Example 3: Trading Strategy Recommendation")
    print("="*70)
    
    intelligence = create_intelligence(use_local=True)
    
    # Get strategy suggestion
    result = intelligence.suggest_strategy(
        symbol='BTCUSDT',
        market_condition='trending'
    )
    
    print(f"\nRecommendation:\n{result['answer']}")


def example_4_explain_indicators():
    """Example 4: Explain signal based on indicators."""
    print("\n" + "="*70)
    print("Example 4: Explain Trading Signal")
    print("="*70)
    
    intelligence = create_intelligence(use_local=True)
    
    # Current indicators
    indicators = {
        'rsi': 35.5,
        'macd': -50.2,
        'bb_position': 0.15
    }
    
    result = intelligence.explain_signal(
        symbol='BTCUSDT',
        current_indicators=indicators
    )
    
    print(f"\nAnalysis:\n{result['answer']}")


def main():
    """Run all examples."""
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║              FKS Intelligence RAG System Examples                 ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    examples = [
        example_1_ingest_signal,
        example_2_query_knowledge,
        example_3_get_strategy_recommendation,
        example_4_explain_indicators,
    ]
    
    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\n❌ Example failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*70)
    print("Examples complete!")
    print("="*70)


if __name__ == "__main__":
    main()
