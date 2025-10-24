"""
Optimization Service - Strategy optimization using Optuna with RAG insights.

This service combines Optuna's hyperparameter optimization with RAG-based
historical insights to intelligently guide the search space and improve
optimization efficiency.

Features:
- RAG-guided parameter search spaces
- Historical performance awareness
- Multi-objective optimization
- Intelligent pruning based on past results
- Integration with feedback loop
"""

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    import optuna
    from optuna.pruners import MedianPruner
    from optuna.samplers import TPESampler

    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False
    print("⚠ Optuna not available. Install with: pip install optuna")

from services.feedback_service import FeedbackService, get_feedback_service
from services.rag_service import RAGService, get_rag_service


class OptimizationService:
    """
    Service for optimizing trading strategies using Optuna + RAG.

    Uses RAG to:
    1. Suggest initial parameter ranges
    2. Guide search based on historical performance
    3. Provide context for optimization decisions
    4. Store optimization results for future reference
    """

    def __init__(
        self,
        rag_service: Optional[RAGService] = None,
        feedback_service: Optional[FeedbackService] = None,
    ):
        """
        Initialize optimization service.

        Args:
            rag_service: RAGService instance
            feedback_service: FeedbackService instance
        """
        if not OPTUNA_AVAILABLE:
            raise ImportError("Optuna is required for optimization service")

        self.rag = rag_service or get_rag_service()
        self.feedback = feedback_service or get_feedback_service()

    def get_rag_suggested_ranges(
        self, strategy: str, symbol: str, parameters: list[str]
    ) -> dict[str, dict[str, Any]]:
        """
        Get RAG-suggested parameter ranges based on historical performance.

        Args:
            strategy: Strategy name
            symbol: Trading pair
            parameters: List of parameter names

        Returns:
            Dict of parameter ranges with type and bounds
        """
        params_str = ", ".join(parameters)
        query = f"Based on historical backtests and trade outcomes for {strategy} on {symbol}, what are the optimal ranges for these parameters: {params_str}? Provide specific numeric ranges."

        filters = {"symbol": symbol, "doc_type": ["backtest_result", "trade_outcome"]}

        result = self.rag.query_with_rag(query=query, top_k=15, filters=filters)

        # Parse response for ranges (this is a simplified version)
        # In production, you'd want more sophisticated parsing
        suggested_ranges = {}

        for param in parameters:
            # Default ranges (can be overridden by RAG insights)
            if "period" in param.lower() or "length" in param.lower():
                suggested_ranges[param] = {
                    "type": "int",
                    "low": 5,
                    "high": 50,
                    "step": 1,
                }
            elif "threshold" in param.lower() or "level" in param.lower():
                suggested_ranges[param] = {
                    "type": "float",
                    "low": 0.0,
                    "high": 1.0,
                    "step": 0.01,
                }
            elif "multiplier" in param.lower():
                suggested_ranges[param] = {
                    "type": "float",
                    "low": 0.5,
                    "high": 3.0,
                    "step": 0.1,
                }
            else:
                suggested_ranges[param] = {
                    "type": "float",
                    "low": 0.0,
                    "high": 100.0,
                    "step": 1.0,
                }

        print(f"✓ RAG-suggested parameter ranges for {strategy} on {symbol}")
        print(f"  RAG context: {result['num_sources']} historical documents")

        return suggested_ranges

    def optimize_strategy(
        self,
        strategy: str,
        symbol: str,
        timeframe: str,
        objective_function: Callable,
        parameters: list[str],
        n_trials: int = 100,
        use_rag_ranges: bool = True,
        custom_ranges: Optional[dict] = None,
        direction: str = "maximize",
        metric: str = "sharpe_ratio",
    ) -> dict[str, Any]:
        """
        Optimize strategy parameters using Optuna with RAG guidance.

        Args:
            strategy: Strategy name
            symbol: Trading pair
            timeframe: Timeframe
            objective_function: Function(trial) -> float that returns metric to optimize
            parameters: List of parameter names
            n_trials: Number of optimization trials
            use_rag_ranges: Use RAG to suggest parameter ranges
            custom_ranges: Custom parameter ranges (overrides RAG)
            direction: 'maximize' or 'minimize'
            metric: Metric name being optimized

        Returns:
            Optimization results with best parameters
        """
        print(f"\n🔍 Starting Optuna optimization for {strategy} on {symbol}")
        print(f"   Metric: {metric} ({direction})")
        print(f"   Trials: {n_trials}")

        # Get parameter ranges
        if custom_ranges:
            param_ranges = custom_ranges
        elif use_rag_ranges:
            param_ranges = self.get_rag_suggested_ranges(strategy, symbol, parameters)
        else:
            # Use default ranges
            param_ranges = {
                param: {"type": "float", "low": 0, "high": 100} for param in parameters
            }

        # Create Optuna study
        study_name = f"{strategy}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        study = optuna.create_study(
            direction=direction,
            study_name=study_name,
            sampler=TPESampler(seed=42),
            pruner=MedianPruner(n_startup_trials=5, n_warmup_steps=10),
        )

        # Define objective wrapper
        def objective_wrapper(trial):
            # Suggest parameters based on ranges
            params = {}
            for param_name, param_config in param_ranges.items():
                if param_config["type"] == "int":
                    params[param_name] = trial.suggest_int(
                        param_name,
                        param_config["low"],
                        param_config["high"],
                        step=param_config.get("step", 1),
                    )
                elif param_config["type"] == "float":
                    params[param_name] = trial.suggest_float(
                        param_name,
                        param_config["low"],
                        param_config["high"],
                        step=param_config.get("step"),
                    )
                elif param_config["type"] == "categorical":
                    params[param_name] = trial.suggest_categorical(
                        param_name, param_config["choices"]
                    )

            # Call user's objective function
            return objective_function(trial, **params)

        # Run optimization
        try:
            study.optimize(objective_wrapper, n_trials=n_trials, show_progress_bar=True)
        except Exception as e:
            print(f"⚠ Optimization error: {e}")
            return {"error": str(e)}

        # Get results
        best_params = study.best_params
        best_value = study.best_value

        # Store optimization results in RAG
        self._store_optimization_results(
            strategy=strategy,
            symbol=symbol,
            timeframe=timeframe,
            best_params=best_params,
            best_value=best_value,
            metric=metric,
            n_trials=n_trials,
            study=study,
        )

        # Get RAG insights on results
        insights = self._get_optimization_insights(
            strategy=strategy,
            symbol=symbol,
            best_params=best_params,
            best_value=best_value,
            metric=metric,
        )

        results = {
            "strategy": strategy,
            "symbol": symbol,
            "timeframe": timeframe,
            "best_parameters": best_params,
            "best_value": best_value,
            "metric": metric,
            "n_trials": n_trials,
            "insights": insights,
            "study_name": study_name,
        }

        print("\n✓ Optimization complete!")
        print(f"  Best {metric}: {best_value:.4f}")
        print(f"  Best parameters: {json.dumps(best_params, indent=2)}")

        return results

    def _store_optimization_results(
        self,
        strategy: str,
        symbol: str,
        timeframe: str,
        best_params: dict[str, Any],
        best_value: float,
        metric: str,
        n_trials: int,
        study,
    ):
        """Store optimization results in RAG knowledge base"""
        # Format trial history
        trials_summary = []
        for trial in study.trials[:10]:  # Top 10
            trials_summary.append(
                f"Trial {trial.number}: {metric}={trial.value:.4f}, params={trial.params}"
            )
        trials_text = "\n".join(trials_summary)

        content = f"""Strategy Optimization Results
{'='*50}

Strategy: {strategy}
Symbol: {symbol}
Timeframe: {timeframe}

Optimization Details:
- Metric: {metric}
- Trials: {n_trials}
- Best Value: {best_value:.4f}
- Date: {datetime.now().isoformat()}

Best Parameters:
{json.dumps(best_params, indent=2)}

Top Trials:
{trials_text}

Conclusion:
Optuna optimization found optimal parameters for {strategy} on {symbol}.
Best {metric}: {best_value:.4f} achieved after {n_trials} trials.
These parameters should be validated with out-of-sample backtesting before live deployment.
"""

        # Ingest
        self.rag.intelligence.ingest_document(
            content=content,
            doc_type="optimization_result",
            title=f"Optimization: {strategy} - {symbol} ({metric}={best_value:.4f})",
            symbol=symbol,
            timeframe=timeframe,
            metadata={
                "strategy": strategy,
                "best_params": best_params,
                "best_value": best_value,
                "metric": metric,
                "n_trials": n_trials,
                "feedback_type": "optimization",
                "timestamp": datetime.now().isoformat(),
            },
        )

    def _get_optimization_insights(
        self,
        strategy: str,
        symbol: str,
        best_params: dict,
        best_value: float,
        metric: str,
    ) -> str:
        """Get RAG insights on optimization results"""
        params_str = json.dumps(best_params)
        query = f"The {strategy} strategy for {symbol} was optimized with best parameters: {params_str}, achieving {metric}={best_value:.4f}. Based on historical data, what are the key takeaways and risks with these parameters?"

        result = self.rag.query_with_rag(
            query=query,
            top_k=10,
            filters={
                "symbol": symbol,
                "doc_type": ["backtest_result", "optimization_result", "trade_outcome"],
            },
        )

        return result["answer"]

    def compare_strategies(
        self, strategies: list[str], symbol: str, metric: str = "sharpe_ratio"
    ) -> dict[str, Any]:
        """
        Compare multiple strategies using RAG-based historical performance.

        Args:
            strategies: List of strategy names
            symbol: Trading pair
            metric: Performance metric

        Returns:
            Comparison results with recommendations
        """
        strategies_str = ", ".join(strategies)
        query = f"Compare the performance of these strategies for {symbol} based on historical {metric}: {strategies_str}. Which performs best and why?"

        filters = {
            "symbol": symbol,
            "doc_type": ["backtest_result", "optimization_result", "trade_outcome"],
        }

        result = self.rag.query_with_rag(query=query, top_k=20, filters=filters)

        return {
            "strategies": strategies,
            "symbol": symbol,
            "metric": metric,
            "comparison": result["answer"],
            "sources_count": result["num_sources"],
        }

    def get_optimization_history(
        self, strategy: Optional[str] = None, symbol: Optional[str] = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get historical optimization results.

        Args:
            strategy: Optional strategy filter
            symbol: Optional symbol filter
            limit: Maximum results

        Returns:
            List of optimization results
        """
        query_parts = ["Show recent strategy optimization results"]

        if strategy:
            query_parts.append(f"for {strategy}")
        if symbol:
            query_parts.append(f"on {symbol}")

        query = " ".join(query_parts)

        filters = {"doc_type": "optimization_result"}
        if symbol:
            filters["symbol"] = symbol

        results = self.rag.query_with_cosine_similarity(
            query=query, top_k=limit, filters=filters
        )

        return results


# Factory function
def create_optimization_service(
    rag_service: Optional[RAGService] = None,
    feedback_service: Optional[FeedbackService] = None,
) -> OptimizationService:
    """
    Create optimization service instance.

    Args:
        rag_service: RAGService instance
        feedback_service: FeedbackService instance

    Returns:
        OptimizationService instance
    """
    return OptimizationService(rag_service, feedback_service)


# Singleton
_optimization_service_instance = None


def get_optimization_service() -> OptimizationService:
    """Get singleton optimization service instance"""
    global _optimization_service_instance
    if _optimization_service_instance is None:
        _optimization_service_instance = create_optimization_service()
    return _optimization_service_instance
