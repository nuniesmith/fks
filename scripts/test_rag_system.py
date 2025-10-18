#!/usr/bin/env python3
"""
RAG System Test Script - Example usage of FKS Intelligence

This script demonstrates how to:
1. Initialize the RAG system with local or OpenAI models
2. Ingest trading data (signals, backtests, trades)
3. Query the knowledge base
4. Get trading recommendations
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from datetime import datetime
from web.rag.intelligence import FKSIntelligence, create_intelligence
from web.rag.ingestion import DataIngestionPipeline
from web.rag.local_llm import check_cuda_availability
from core.database import Session


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}\n")


def check_system_status():
    """Check CUDA availability and GPU info."""
    print_section("System Status Check")
    
    cuda_info = check_cuda_availability()
    print(f"CUDA Available: {cuda_info['cuda_available']}")
    
    if cuda_info['cuda_available']:
        print(f"CUDA Version: {cuda_info['cuda_version']}")
        print(f"GPUs: {cuda_info['device_count']}")
        for device in cuda_info['devices']:
            print(f"  [{device['index']}] {device['name']} ({device['total_memory_gb']:.1f} GB)")
    else:
        print("  Running on CPU (GPU acceleration not available)")
    
    return cuda_info['cuda_available']


def test_local_embeddings():
    """Test local embeddings generation."""
    print_section("Testing Local Embeddings")
    
    try:
        from web.rag.local_llm import create_local_embeddings
        
        print("Loading local embedding model...")
        embeddings = create_local_embeddings(model_name="all-MiniLM-L6-v2")
        
        # Test single embedding
        test_text = "Bitcoin shows strong support at 42k level"
        print(f"\nTest text: {test_text}")
        
        embedding = embeddings.generate_embedding(test_text)
        print(f"Embedding dimension: {len(embedding)}")
        print(f"First 5 values: {[f'{v:.4f}' for v in embedding[:5]]}")
        
        # Test batch embeddings
        test_texts = [
            "Bullish momentum building in BTCUSDT",
            "RSI indicates oversold conditions",
            "MACD crossover signals potential reversal"
        ]
        
        print(f"\nGenerating batch embeddings for {len(test_texts)} texts...")
        batch_embeddings = embeddings.generate_embeddings_batch(test_texts)
        print(f"Generated {len(batch_embeddings)} embeddings")
        
        return True
        
    except Exception as e:
        print(f"❌ Local embeddings test failed: {e}")
        return False


def test_local_llm():
    """Test local LLM generation."""
    print_section("Testing Local LLM")
    
    try:
        from web.rag.local_llm import create_local_llm
        
        print("Connecting to Ollama...")
        llm = create_local_llm(model_name="llama3.2:3b", backend="ollama")
        
        print("\nGenerating test response...")
        response = llm.generate(
            prompt="What is a good entry point for Bitcoin?",
            system_prompt="You are a helpful trading assistant. Keep responses brief.",
            max_tokens=100
        )
        
        print(f"\nResponse:\n{response}")
        
        return True
        
    except Exception as e:
        print(f"❌ Local LLM test failed: {e}")
        print("  Make sure Ollama is running: ollama serve")
        print("  And the model is installed: ollama pull llama3.2:3b")
        return False


def test_document_ingestion():
    """Test ingesting documents into RAG knowledge base."""
    print_section("Testing Document Ingestion")
    
    try:
        session = Session()
        pipeline = DataIngestionPipeline()
        
        # Test signal ingestion
        print("1. Ingesting trading signal...")
        signal_data = {
            'symbol': 'BTCUSDT',
            'action': 'BUY',
            'price': 42000.00,
            'timestamp': datetime.now().isoformat(),
            'timeframe': '1h',
            'indicators': {
                'rsi': 35.5,
                'macd': -50.2,
                'bb_position': 0.15
            },
            'confidence': 0.85,
            'reasoning': 'RSI oversold + MACD divergence + price near lower Bollinger Band'
        }
        
        signal_doc_id = pipeline.ingest_signal(signal_data, session=session)
        print(f"   ✓ Signal ingested as document {signal_doc_id}")
        
        # Test backtest ingestion
        print("\n2. Ingesting backtest results...")
        backtest_data = {
            'strategy_name': 'RSI Reversal',
            'symbol': 'ETHUSDT',
            'timeframe': '4h',
            'start_date': '2024-01-01',
            'end_date': '2024-10-01',
            'total_return': 45.2,
            'win_rate': 68.5,
            'sharpe_ratio': 2.1,
            'max_drawdown': -12.3,
            'total_trades': 85,
            'parameters': {
                'rsi_period': 14,
                'rsi_oversold': 30,
                'rsi_overbought': 70
            },
            'insights': 'Strategy performs well in ranging markets. Consider adding trend filter.'
        }
        
        backtest_doc_id = pipeline.ingest_backtest_result(backtest_data, session=session)
        print(f"   ✓ Backtest ingested as document {backtest_doc_id}")
        
        # Test market analysis ingestion
        print("\n3. Ingesting market analysis...")
        analysis = """
        Bitcoin Technical Analysis - October 18, 2024
        
        Current Price: $42,150
        
        Key Levels:
        - Support: $41,500 (strong buying interest)
        - Resistance: $43,200 (previous high)
        
        Technical Indicators:
        - RSI(14): 52 (neutral territory)
        - MACD: Bullish crossover forming
        - Volume: Above 20-day average (increased activity)
        
        Market Sentiment: Cautiously bullish
        
        Recommendation: Watch for break above $43,200 for continuation or
        bounce off $41,500 support for potential long entry.
        """
        
        analysis_doc_id = pipeline.ingest_market_analysis(
            analysis_text=analysis,
            symbol='BTCUSDT',
            timeframe='1d',
            metadata={'analyst': 'FKS System', 'confidence': 'high'},
            session=session
        )
        print(f"   ✓ Market analysis ingested as document {analysis_doc_id}")
        
        session.close()
        return True
        
    except Exception as e:
        print(f"❌ Document ingestion test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_queries():
    """Test querying the RAG knowledge base."""
    print_section("Testing RAG Queries")
    
    try:
        # Create intelligence service
        print("Initializing FKS Intelligence...")
        intelligence = create_intelligence(
            use_local=True,
            local_llm_model="llama3.2:3b",
            embedding_model="all-MiniLM-L6-v2"
        )
        
        # Test queries
        queries = [
            "What trading signals were generated for BTCUSDT?",
            "What are the key support and resistance levels for Bitcoin?",
            "What RSI reversal strategy parameters work best?",
        ]
        
        for i, query in enumerate(queries, 1):
            print(f"\n{i}. Query: {query}")
            print("-" * 70)
            
            result = intelligence.query(query, symbol='BTCUSDT', top_k=3)
            
            print(f"Answer:\n{result['answer']}\n")
            print(f"Context used: {result['context_used']} chunks")
            print(f"Response time: {result['response_time_ms']}ms")
            
            if result['sources']:
                print(f"\nSources:")
                for j, source in enumerate(result['sources'][:2], 1):
                    doc_type = source.get('doc_type', 'unknown')
                    similarity = source.get('similarity', 0)
                    print(f"  {j}. [{doc_type.upper()}] Relevance: {similarity:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ RAG query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_trading_recommendations():
    """Test getting trading recommendations."""
    print_section("Testing Trading Recommendations")
    
    try:
        intelligence = create_intelligence(use_local=True)
        
        # Test strategy suggestion
        print("1. Getting strategy suggestion for BTCUSDT...")
        result = intelligence.suggest_strategy(
            symbol='BTCUSDT',
            market_condition='trending'
        )
        
        print(f"\nRecommendation:\n{result['answer']}\n")
        print(f"Based on {result['context_used']} historical insights")
        
        # Test signal explanation
        print("\n2. Explaining current market conditions...")
        current_indicators = {
            'rsi': 35.5,
            'macd': -50.2,
            'bb_position': 0.15,
            'volume_ratio': 1.3
        }
        
        result = intelligence.explain_signal(
            symbol='BTCUSDT',
            current_indicators=current_indicators
        )
        
        print(f"\nAnalysis:\n{result['answer']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Trading recommendations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all RAG system tests."""
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║                   FKS Intelligence RAG System                     ║
    ║              AI-Powered Trading Knowledge Base                    ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Check system status
    has_cuda = check_system_status()
    
    # Run tests
    results = []
    
    print("\n" + "="*70)
    print(" Running Test Suite")
    print("="*70)
    
    tests = [
        ("Local Embeddings", test_local_embeddings),
        ("Local LLM", test_local_llm),
        ("Document Ingestion", test_document_ingestion),
        ("RAG Queries", test_rag_queries),
        ("Trading Recommendations", test_trading_recommendations),
    ]
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print_section("Test Results Summary")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status:<10} {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    
    if passed == total:
        print("\n🎉 All tests passed! RAG system is ready to use.")
    else:
        print("\n⚠️  Some tests failed. Check logs above for details.")
    
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
