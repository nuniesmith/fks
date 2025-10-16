"""
Intelligence API views for RAG-powered trading insights.
Provides REST API endpoints for querying the knowledge base.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import json
import traceback
from datetime import datetime
from typing import Dict, Any, Optional

from ..models import Trade, Signal, BacktestResult
from rag.intelligence import create_intelligence, FKSIntelligence
from rag.ingestion import create_ingestion_pipeline, IngestionPipeline


# Global intelligence instance (cached)
_intelligence_instance: Optional[FKSIntelligence] = None
_ingestion_pipeline: Optional[IngestionPipeline] = None


def get_intelligence() -> FKSIntelligence:
    """Get or create intelligence service instance."""
    global _intelligence_instance
    if _intelligence_instance is None:
        _intelligence_instance = create_intelligence(
            use_local=True,
            local_llm_model="llama3.2:3b",
            embedding_model="all-MiniLM-L6-v2"
        )
    return _intelligence_instance


def get_ingestion() -> IngestionPipeline:
    """Get or create ingestion pipeline instance."""
    global _ingestion_pipeline
    if _ingestion_pipeline is None:
        _ingestion_pipeline = create_ingestion_pipeline(use_local=True)
    return _ingestion_pipeline


@require_http_methods(["POST"])
@csrf_exempt
def query_knowledge_base(request):
    """
    Query the RAG knowledge base.
    
    POST /api/intelligence/query/
    Body: {
        "query": "What strategy works best for BTCUSDT?",
        "top_k": 5,
        "include_sources": true
    }
    """
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        top_k = data.get('top_k', 5)
        include_sources = data.get('include_sources', True)
        
        if not query:
            return JsonResponse({
                'success': False,
                'error': 'Query is required'
            }, status=400)
        
        # Check cache first
        cache_key = f"rag_query:{query}:{top_k}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return JsonResponse({
                'success': True,
                'cached': True,
                **cached_result
            })
        
        # Query RAG system
        intelligence = get_intelligence()
        result = intelligence.query(query, top_k=top_k)
        
        # Format response
        response_data = {
            'answer': result['answer'],
            'query': query,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if include_sources and 'sources' in result:
            response_data['sources'] = [
                {
                    'content': src['content'],
                    'similarity': src.get('similarity', 0),
                    'metadata': src.get('metadata', {})
                }
                for src in result['sources']
            ]
            response_data['num_sources'] = len(result['sources'])
        
        # Cache for 5 minutes
        cache.set(cache_key, response_data, 300)
        
        return JsonResponse({
            'success': True,
            'cached': False,
            **response_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def suggest_strategy(request):
    """
    Get strategy suggestions for a symbol.
    
    POST /api/intelligence/strategy/
    Body: {
        "symbol": "BTCUSDT",
        "market_condition": "trending",  // optional
        "timeframe": "4h"  // optional
    }
    """
    try:
        data = json.loads(request.body)
        symbol = data.get('symbol', '').upper()
        market_condition = data.get('market_condition')
        timeframe = data.get('timeframe', '1h')
        
        if not symbol:
            return JsonResponse({
                'success': False,
                'error': 'Symbol is required'
            }, status=400)
        
        # Check cache
        cache_key = f"rag_strategy:{symbol}:{market_condition}:{timeframe}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return JsonResponse({
                'success': True,
                'cached': True,
                **cached_result
            })
        
        # Get strategy suggestions
        intelligence = get_intelligence()
        result = intelligence.suggest_strategy(
            symbol=symbol,
            market_condition=market_condition,
            timeframe=timeframe
        )
        
        response_data = {
            'strategy': result['answer'],
            'symbol': symbol,
            'market_condition': market_condition,
            'timeframe': timeframe,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if 'sources' in result:
            response_data['sources'] = result['sources']
            response_data['num_sources'] = len(result['sources'])
        
        # Cache for 10 minutes
        cache.set(cache_key, response_data, 600)
        
        return JsonResponse({
            'success': True,
            'cached': False,
            **response_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["GET"])
def analyze_trades(request, symbol):
    """
    Analyze past trades for a symbol.
    
    GET /api/intelligence/trades/{symbol}/
    Query params:
        ?days=30  // optional, default 30
        ?min_trades=5  // optional, default 5
    """
    try:
        days = int(request.GET.get('days', 30))
        min_trades = int(request.GET.get('min_trades', 5))
        
        # Check cache
        cache_key = f"rag_trades:{symbol}:{days}:{min_trades}"
        cached_result = cache.get(cache_key)
        if cached_result:
            return JsonResponse({
                'success': True,
                'cached': True,
                **cached_result
            })
        
        # Get analysis
        intelligence = get_intelligence()
        result = intelligence.analyze_past_trades(
            symbol=symbol,
            days=days,
            min_trades=min_trades
        )
        
        response_data = {
            'analysis': result['answer'],
            'symbol': symbol,
            'period_days': days,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if 'sources' in result:
            response_data['sources'] = result['sources']
            response_data['num_sources'] = len(result['sources'])
        
        # Cache for 15 minutes
        cache.set(cache_key, response_data, 900)
        
        return JsonResponse({
            'success': True,
            'cached': False,
            **response_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def explain_signal(request):
    """
    Explain current market signal.
    
    POST /api/intelligence/signal/
    Body: {
        "symbol": "BTCUSDT",
        "indicators": {
            "rsi": 35,
            "macd": -0.5,
            "sma_20": 49500
        }
    }
    """
    try:
        data = json.loads(request.body)
        symbol = data.get('symbol', '').upper()
        indicators = data.get('indicators', {})
        
        if not symbol:
            return JsonResponse({
                'success': False,
                'error': 'Symbol is required'
            }, status=400)
        
        if not indicators:
            return JsonResponse({
                'success': False,
                'error': 'Indicators are required'
            }, status=400)
        
        # Get explanation
        intelligence = get_intelligence()
        result = intelligence.explain_signal(
            symbol=symbol,
            current_indicators=indicators
        )
        
        response_data = {
            'explanation': result['answer'],
            'symbol': symbol,
            'indicators': indicators,
            'timestamp': datetime.utcnow().isoformat(),
        }
        
        if 'sources' in result:
            response_data['sources'] = result['sources']
        
        return JsonResponse({
            'success': True,
            **response_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def ingest_data(request):
    """
    Manually trigger data ingestion.
    
    POST /api/intelligence/ingest/
    Body: {
        "type": "trades|signals|backtests|all",
        "days": 30,  // optional
        "limit": 100  // optional
    }
    """
    try:
        data = json.loads(request.body)
        ingest_type = data.get('type', 'all')
        days = data.get('days', 30)
        limit = data.get('limit', 100)
        
        pipeline = get_ingestion()
        ingested = []
        
        if ingest_type in ['trades', 'all']:
            # Ingest recent completed trades
            count = pipeline.batch_ingest_recent_trades(days=days)
            ingested.append({'type': 'trades', 'count': count})
        
        if ingest_type in ['signals', 'all']:
            # Ingest recent signals
            count = pipeline.batch_ingest_recent_signals(days=days, limit=limit)
            ingested.append({'type': 'signals', 'count': count})
        
        if ingest_type in ['backtests', 'all']:
            # Ingest recent backtests
            count = pipeline.batch_ingest_recent_backtests(limit=limit)
            ingested.append({'type': 'backtests', 'count': count})
        
        return JsonResponse({
            'success': True,
            'message': 'Data ingestion completed',
            'ingested': ingested,
            'total_documents': sum(item['count'] for item in ingested),
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["GET"])
def stats(request):
    """
    Get RAG system statistics.
    
    GET /api/intelligence/stats/
    """
    try:
        from database import Document, DocumentChunk, QueryHistory
        from sqlalchemy import func
        
        intelligence = get_intelligence()
        session = intelligence.session
        
        # Get document stats
        total_documents = session.query(func.count(Document.id)).scalar() or 0
        total_chunks = session.query(func.count(DocumentChunk.id)).scalar() or 0
        
        # Get document types
        doc_types = session.query(
            Document.doc_type,
            func.count(Document.id).label('count')
        ).group_by(Document.doc_type).all()
        
        # Get query stats
        total_queries = session.query(func.count(QueryHistory.id)).scalar() or 0
        
        return JsonResponse({
            'success': True,
            'stats': {
                'total_documents': total_documents,
                'total_chunks': total_chunks,
                'total_queries': total_queries,
                'document_types': [
                    {'type': dt, 'count': count}
                    for dt, count in doc_types
                ],
                'use_local_llm': intelligence.use_local,
                'embedding_model': intelligence.embeddings_service.model_name if hasattr(intelligence.embeddings_service, 'model_name') else 'unknown',
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@require_http_methods(["GET"])
def health(request):
    """
    Health check endpoint.
    
    GET /api/intelligence/health/
    """
    try:
        intelligence = get_intelligence()
        
        # Test database connection
        session = intelligence.session
        session.execute("SELECT 1")
        
        # Test embedding service
        test_embedding = intelligence.embeddings_service.generate_embedding("test")
        
        return JsonResponse({
            'success': True,
            'status': 'healthy',
            'components': {
                'database': 'ok',
                'embeddings': 'ok',
                'llm': 'ok' if intelligence.use_local else 'disabled',
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'status': 'unhealthy',
            'error': str(e)
        }, status=503)
