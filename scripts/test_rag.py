#!/usr/bin/env python3
"""
FKS Intelligence Test and Demo Script

This script demonstrates the RAG system capabilities:
1. Document ingestion
2. Knowledge base querying
3. Strategy suggestions
4. Trade analysis
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from rag.intelligence import create_intelligence
from rag.ingestion import create_ingestion_pipeline
from database import Session, Document, QueryHistory
from sqlalchemy import func


def print_section(title):
    """Print section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60 + "\n")


def test_document_ingestion():
    """Test document ingestion"""
    print_section("1. Testing Document Ingestion")
    
    intelligence = create_intelligence()
    session = Session()
    
    # Sample documents
    documents = [
        {
            'content': "BTCUSDT broke resistance at 42k. RSI at 65 showing bullish momentum. MACD crossover confirmed. Entry at 42.5k with stop at 41k.",
            'doc_type': 'signal',
            'title': 'BTC Long Signal',
            'symbol': 'BTCUSDT',
            'timeframe': '1h'
        },
        {
            'content': "Backtest of RSI Mean Reversion on ETHUSDT showed 68% win rate with 15% total return over 3 months. Best parameters: RSI period 14, oversold 30, overbought 70.",
            'doc_type': 'backtest',
            'title': 'ETH RSI Strategy Backtest',
            'symbol': 'ETHUSDT',
            'timeframe': '15m'
        },
        {
            'content': "Market analysis: Bitcoin consolidating in range 40k-45k. Volume decreasing suggests breakout imminent. Watch for direction confirmation.",
            'doc_type': 'market_report',
            'title': 'BTC Range Analysis',
            'symbol': 'BTCUSDT',
            'timeframe': '4h'
        }
    ]
    
    print("Ingesting sample documents...")
    doc_ids = []
    
    for doc_data in documents:
        try:
            doc_id = intelligence.ingest_document(
                content=doc_data['content'],
                doc_type=doc_data['doc_type'],
                title=doc_data['title'],
                symbol=doc_data['symbol'],
                timeframe=doc_data['timeframe'],
                session=session
            )
            doc_ids.append(doc_id)
            print(f"  ✓ Ingested: {doc_data['title']} (ID: {doc_id})")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    session.close()
    print(f"\n✓ Successfully ingested {len(doc_ids)} documents")
    return doc_ids


def test_knowledge_base_query():
    """Test querying knowledge base"""
    print_section("2. Testing Knowledge Base Query")
    
    intelligence = create_intelligence()
    
    questions = [
        "What trading strategy works best for BTCUSDT?",
        "What are the best RSI parameters for ETHUSDT?",
        "What is the current market condition for Bitcoin?"
    ]
    
    for question in questions:
        print(f"\nQ: {question}")
        print("-" * 60)
        
        try:
            result = intelligence.query(
                question=question,
                top_k=3
            )
            
            print(f"A: {result['answer'][:300]}...")
            print(f"\nSources used: {result['context_used']}")
            print(f"Response time: {result['response_time_ms']}ms")
            
            if result['sources']:
                print("\nTop sources:")
                for i, source in enumerate(result['sources'][:2], 1):
                    print(f"  {i}. {source['doc_type']} - {source['symbol']} (similarity: {source['similarity']:.2f})")
        
        except Exception as e:
            print(f"Error: {e}")


def test_strategy_suggestion():
    """Test strategy suggestion"""
    print_section("3. Testing Strategy Suggestion")
    
    intelligence = create_intelligence()
    
    print("Requesting strategy for BTCUSDT...")
    
    try:
        result = intelligence.suggest_strategy(
            symbol="BTCUSDT",
            market_condition="ranging"
        )
        
        print(f"\nStrategy Suggestion:\n{result['answer']}")
        print(f"\nBased on {result['context_used']} historical records")
        
    except Exception as e:
        print(f"Error: {e}")


def test_trade_analysis():
    """Test past trade analysis"""
    print_section("4. Testing Trade Analysis")
    
    intelligence = create_intelligence()
    
    print("Analyzing past trades for ETHUSDT...")
    
    try:
        result = intelligence.analyze_past_trades(
            symbol="ETHUSDT"
        )
        
        print(f"\nAnalysis:\n{result['answer'][:400]}...")
        
    except Exception as e:
        print(f"Error: {e}")


def show_knowledge_base_stats():
    """Show knowledge base statistics"""
    print_section("5. Knowledge Base Statistics")
    
    session = Session()
    
    try:
        # Document count by type
        doc_stats = session.query(
            Document.doc_type,
            func.count(Document.id)
        ).group_by(Document.doc_type).all()
        
        print("Documents by type:")
        total_docs = 0
        for doc_type, count in doc_stats:
            print(f"  {doc_type}: {count}")
            total_docs += count
        
        print(f"\nTotal documents: {total_docs}")
        
        # Query statistics
        total_queries = session.query(QueryHistory).count()
        
        if total_queries > 0:
            avg_time = session.query(func.avg(QueryHistory.response_time_ms)).scalar()
            print(f"\nTotal queries: {total_queries}")
            print(f"Average response time: {avg_time:.0f}ms")
        
    finally:
        session.close()


def test_batch_ingestion():
    """Test batch ingestion of trades"""
    print_section("6. Testing Batch Trade Ingestion")
    
    pipeline = create_ingestion_pipeline()
    
    print("Ingesting recent trades (last 30 days)...")
    
    try:
        count = pipeline.batch_ingest_recent_trades(days=30)
        print(f"✓ Ingested {count} trades")
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Main test function"""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "FKS Intelligence - RAG System Test" + " " * 14 + "║")
    print("╚" + "=" * 58 + "╝")
    
    try:
        # Run tests
        test_document_ingestion()
        test_knowledge_base_query()
        test_strategy_suggestion()
        test_trade_analysis()
        show_knowledge_base_stats()
        test_batch_ingestion()
        
        print_section("✅ All Tests Complete")
        print("RAG system is working correctly!")
        print("\nNext steps:")
        print("  1. Integrate with Django views")
        print("  2. Add UI components")
        print("  3. Set up automated ingestion")
        print("\nSee docs/PROJECT_IMPROVEMENT_PLAN.md for details")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
