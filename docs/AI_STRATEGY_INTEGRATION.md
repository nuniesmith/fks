# AI Strategy Integration Plan: LLM Strategy Generation & DL Regime Detection

**Status**: Implementation Ready (Oct 28, 2025)  
**Target Services**: fks_ai (GPU ML/RAG), fks_app (trading logic), fks_data (data collection)  
**Created**: October 24, 2025  
**Updated**: October 28, 2025  
**Priority**: High (Current Phase - AI Enhancement 12-phase plan active)

> **Note**: This document describes the original 5-phase AI plan. For the comprehensive 12-phase implementation roadmap including ASMBTR baseline, multi-agent LLM architecture, and advanced evaluation frameworks, see:
> - **Primary Reference**: `.github/copilot-instructions.md` (lines 866-1400) - Complete 12-phase plan
> - **Current Status**: `docs/PHASE_STATUS.md` - Progress tracker

## Executive Summary

This document outlines the integration of two advanced AI capabilities into the FKS Trading Platform:

1. **LLM-Based Strategy Generation**: Using local LLMs (Ollama/Llama-3) to generate backtestable trading strategies from market data, fundamentals, and technical indicators
2. **Deep Learning Regime Detection**: Using VAE + Transformer models to classify market conditions (calm/transition/volatile) for adaptive strategy execution

Both features align perfectly with FKS's microservices architecture and existing GPU infrastructure (fks_ai service with CUDA + Ollama).

### Key Benefits
- **Dynamic Adaptation**: Strategies automatically adjust to detected market regimes
- **Zero Cost**: Local LLM inference eliminates API fees
- **Proven Performance**: Research shows 90% returns (LLM strategies) and Sharpe ratios up to 11 (regime-aware trading)
- **Modular Integration**: No core architecture changes needed

### Feasibility Assessment
✅ **High Feasibility** - All required infrastructure exists:
- fks_ai: GPU support, PyTorch, Ollama local LLM, LangGraph for multi-agent orchestration
- fks_app: Backtesting framework, Optuna optimization
- fks_data: CCXT integration (can extend to EODHD for stocks/fundamentals)
- fks_execution: Order execution with circuit breaker
- **Current Status**: 15/16 services operational (93.75%), 69/69 tests passing

### Enhanced 12-Phase Roadmap (Oct 2025)
The original 5-phase plan has been expanded into a comprehensive 12-phase AI enhancement strategy:

**Phases 1-4: ASMBTR Baseline** (4 weeks)
- Non-AI probabilistic baseline using Binary Tree Representation for benchmarking
- Target: Calmar >0.3 on EUR/USD tick data

**Phases 5-7: Multi-Agent LLM System** (8 weeks)
- LangGraph orchestration with Bull/Bear/Manager agents
- 4 analyst types, 3 trader personas, adversarial debate architecture
- Target: >60% signal quality on validation set

**Phases 8-10: Advanced Models & Risk** (4 weeks)
- Confusion matrix evaluation with Bonferroni/BH corrections
- CNN-LSTM + LLM vetoes, Walk-Forward Optimization
- MDD protection, CPI-Gold hedging, Markov chain integration
- Target: Calmar >0.45, Sharpe ~0.5

**Phases 11-12: Production** (4 weeks)
- Grafana monitoring, Discord alerts
- Paper trading validation, A/B testing, ethics audit
- Target: Real-world Sharpe >2.5

See `.github/copilot-instructions.md` for complete phase details and implementation templates.

## Research Foundation

### Source Articles
1. **[Comparing 3 LLMs for Generating Profitable Trading Strategies](https://wire.insiderfinance.io/comparing-3-llms-for-generating-profitable-trading-strategies-6e9e9c8af8f7)**
   - Tests ChatGPT, Gemini, Perplexity on AAPL stock
   - Perplexity achieved 90% cumulative return, Sharpe 1.87
   - ChatGPT failed (0 trades due to overly strict rules)
   - Uses EODHD API for fundamentals (PE ratio, earnings growth)

2. **[Deep Learning for Hidden Market Regimes: VAE & Transformer Extension to LGMM](https://wire.insiderfinance.io/deep-learning-for-hidden-market-regimes-vae-transformer-extension-to-lgmm-8d2e1b5c8e8b)**
   - VAE + Transformer outperforms traditional Latent Gaussian Mixture Models
   - Classifies regimes: 0=calm, 1=transition, 2=volatile
   - Sharpe ratios 10-11 in calm regimes, 2-3 in volatile
   - Uses features: log returns, 21d vol, 5d momentum

### Industry Context
- **Deloitte 2023**: 65% of quant firms use ML for regime detection
- **arXiv 2024**: LLM trading agents show 20-50% improved returns with prompting
- **Examples**: TensorTrade (Transformer regimes), QuantConnect (LLM code gen), Alpaca (AI-driven trading)

## Architecture Integration

### Service Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│                    FKS AI Strategy System                    │
└─────────────────────────────────────────────────────────────┘

fks_data (Port 8003)
├── Extend CCXT for crypto technicals (RSI, MACD, SMA)
├── Add EODHD API integration for stock fundamentals
├── TimescaleDB: Add fundamentals table
└── Redis: Cache engineered features (21d vol, momentum)

fks_ai (Port 8006 - GPU)
├── LLM Strategy Generation
│   ├── Ollama/Llama-3 for local inference
│   ├── Prompt engineering framework
│   ├── Strategy parsing and validation
│   └── Endpoints: /ai/generate-strategy, /ai/validate-strategy
│
├── DL Regime Detection
│   ├── VAE (Variational Autoencoder) - nonlinear latent space
│   ├── Transformer - sequence modeling (16-day windows)
│   ├── KMeans clustering on latents (n_clusters=3)
│   ├── Training: Celery tasks (30-80 epochs)
│   ├── Inference: Real-time regime classification (<1s)
│   └── Endpoints: /ai/regime, /ai/train-regime-model
│
└── Model Management
    ├── HuggingFace cache for embeddings
    └── Version tracking (MLflow or custom)

fks_app (Port 8002)
├── Strategy Execution
│   ├── Ingest LLM-generated entry/exit rules
│   ├── Backtest strategies via TA-Lib + Pandas
│   ├── Validate metrics (Sharpe, drawdown, win rate)
│   └── Integrate with existing signal generation
│
├── Regime-Aware Trading
│   ├── Query fks_ai for current regime every 15m
│   ├── Adjust position sizing by regime:
│   │   ├── Calm (0): Increase leverage, momentum bias
│   │   ├── Transition (1): Reduce exposure, wait
│   │   └── Volatile (2): Hedge, mean-reversion bias
│   └── Log regime changes for analysis
│
└── Optuna Integration
    ├── Optimize strategy params per regime
    └── Cross-validate across regime transitions

fks_main (Port 8000)
├── Celery Beat Scheduler
│   ├── Regime updates: Every 15 minutes
│   ├── Model retraining: Daily (off-hours)
│   └── Strategy generation: On-demand or weekly
│
└── Monitoring (Grafana)
    ├── Regime distribution over time
    ├── Strategy win rate by regime
    └── LLM generation success rate

fks_web (Port 3001)
└── Dashboard Enhancements
    ├── Regime timeline visualization (Matplotlib/Seaborn)
    ├── LLM strategy editor (prompt → backtest)
    └── Regime-adjusted portfolio view
```

### Data Flow

**LLM Strategy Generation**:
```
User Prompt → fks_ai (LLM inference) → Strategy Rules → fks_app (backtest) 
→ Metrics (Sharpe, return) → fks_web (display) → User Approval 
→ fks_app (live execution) → fks_execution (orders)
```

**Regime Detection**:
```
Market Data → fks_data (feature engineering) → fks_ai (VAE → latents → KMeans) 
→ Regime Label (0/1/2) → fks_app (adjust strategy) → fks_execution (orders)
```

## Implementation Roadmap

### Phase 1: Data Foundation (2 weeks)
**Goal**: Extend fks_data to support fundamentals and engineered features

**Tasks**:
1. Add EODHD API integration to fks_data
   ```python
   # src/fks_data/integrations/eodhd.py
   def fetch_fundamentals(symbol: str, from_date: str, to_date: str):
       api_key = os.getenv('EODHD_API_KEY')
       url = f'https://eodhd.com/api/eod/{symbol}.US?api_token={api_key}&fmt=json&from={from_date}&to={to_date}'
       response = requests.get(url)
       return response.json()
   ```

2. Create fundamentals table in TimescaleDB
   ```sql
   CREATE TABLE fundamentals (
       time TIMESTAMPTZ NOT NULL,
       symbol TEXT NOT NULL,
       pe_ratio DOUBLE PRECISION,
       earnings_growth DOUBLE PRECISION,
       revenue DOUBLE PRECISION,
       debt_to_equity DOUBLE PRECISION
   );
   SELECT create_hypertable('fundamentals', 'time');
   ```

3. Add feature engineering endpoints
   ```python
   # Features for regime detection
   df['logret'] = np.log(df['close'] / df['close'].shift(1))
   df['vol_21d'] = df['logret'].rolling(21).std() * np.sqrt(252)
   df['momentum_5d'] = df['close'].pct_change(5)
   ```

4. Cache features in Redis (TTL: 1 hour)

**Deliverables**:
- EODHD integration in fks_data/integrations/
- Fundamentals hypertable with 2-year backfill for test symbols
- Feature engineering utils in fks_data/features.py
- API endpoints: /data/fundamentals/{symbol}, /data/features/{symbol}

**Testing**:
- Unit tests for EODHD parsing
- Integration tests: Fetch AAPL fundamentals, verify DB storage
- Validate feature calculations (compare to article's code)

---

### Phase 2: DL Regime Detection (3-4 weeks)
**Goal**: Implement VAE + Transformer for market regime classification

**Tasks**:
1. **VAE Implementation** (1 week)
   ```python
   # src/fks_ai/models/vae.py
   class VAE(nn.Module):
       def __init__(self, input_dim=3, latent_dim=2):
           super().__init__()
           self.encoder = nn.Sequential(
               nn.Linear(input_dim, 16), nn.ReLU(),
               nn.Linear(16, latent_dim * 2)  # mu + logvar
           )
           self.decoder = nn.Sequential(
               nn.Linear(latent_dim, 16), nn.ReLU(),
               nn.Linear(16, input_dim)
           )
       
       def encode(self, x):
           h = self.encoder(x)
           mu, logvar = h[:, :self.latent_dim], h[:, self.latent_dim:]
           return mu, logvar
       
       def reparameterize(self, mu, logvar):
           std = torch.exp(0.5 * logvar)
           eps = torch.randn_like(std)
           return mu + eps * std
       
       def forward(self, x):
           mu, logvar = self.encode(x)
           z = self.reparameterize(mu, logvar)
           return self.decoder(z), mu, logvar
   ```

2. **KMeans Clustering on Latents**
   ```python
   from sklearn.cluster import KMeans
   
   # Train VAE, extract latents
   with torch.no_grad():
       mu, _ = vae.encode(torch.tensor(features, dtype=torch.float32))
   
   # Cluster into 3 regimes
   kmeans = KMeans(n_clusters=3, random_state=42)
   labels = kmeans.fit_predict(mu.numpy())
   ```

3. **Transformer for Sequence Modeling** (1 week)
   ```python
   # src/fks_ai/models/transformer_regime.py
   class TransformerRegimeClassifier(nn.Module):
       def __init__(self, input_dim=3, d_model=64, nhead=4, num_layers=2, num_classes=3):
           super().__init__()
           self.embedding = nn.Linear(input_dim, d_model)
           encoder_layer = nn.TransformerEncoderLayer(d_model, nhead, batch_first=True)
           self.transformer = nn.TransformerEncoder(encoder_layer, num_layers)
           self.classifier = nn.Linear(d_model, num_classes)
       
       def forward(self, x):  # x: (batch, seq_len, input_dim)
           x = self.embedding(x)
           x = self.transformer(x)
           return self.classifier(x[:, -1, :])  # Use last time step
   ```

4. **Training Pipeline** (1 week)
   - Celery task for training (background job)
   - Hyperparameters: latent_dim=2, seq_len=16, epochs=50-80
   - Validation: 80/20 train/test split
   - Save models to ./ml_models volume

5. **Inference Endpoint** (3 days)
   ```python
   # src/fks_ai/api/regime.py
   @app.post("/ai/regime")
   async def get_regime(symbol: str):
       # Fetch latest 16 days of features from fks_data
       features = fetch_features(symbol, days=16)
       
       # Infer regime
       with torch.no_grad():
           x = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
           logits = transformer_model(x)
           regime = torch.argmax(logits, dim=1).item()
       
       return {"symbol": symbol, "regime": regime, "label": ["calm", "transition", "volatile"][regime]}
   ```

**Deliverables**:
- VAE model in fks_ai/models/vae.py
- Transformer classifier in fks_ai/models/transformer_regime.py
- Training script: fks_ai/tasks/train_regime_model.py (Celery task)
- API endpoints: POST /ai/regime, POST /ai/train-regime-model
- Model versioning (save to ./ml_models/regime_v{timestamp}.pth)

**Testing**:
- Unit tests: VAE forward pass, Transformer shapes
- Backtest: Compare regime labels to article (SPY example)
- Performance: Inference <1s for 16-day sequence
- Validate clustering: Plot latent space (2D), verify 3 clusters

---

### Phase 3: LLM Strategy Generation (3 weeks)
**Goal**: Use Ollama/Llama-3 to generate trading strategies from data

**Tasks**:
1. **Prompt Engineering Framework** (1 week)
   ```python
   # src/fks_ai/prompts/strategy_generation.py
   ANALYZE_PROMPT = """
   You are a quantitative analyst. Analyze this data for {symbol}:
   
   Historical Prices (last 2 years):
   {price_data}
   
   Technical Indicators:
   - RSI: {rsi_summary}
   - SMA: {sma_summary}
   - MACD: {macd_summary}
   
   Fundamentals:
   - PE Ratio: {pe_ratio}
   - Earnings Growth: {earnings_growth}
   
   Identify patterns, trends, and anomalies. Be specific.
   """
   
   STRATEGY_PROMPT = """
   Based on your analysis, propose a trading strategy with:
   1. Clear entry conditions (use fundamentals primarily)
   2. Exit conditions (profit target, stop loss)
   3. Position sizing rules
   4. Risk management
   
   Output as structured JSON:
   {{
       "name": "Strategy Name",
       "entry": {{"conditions": ["PE < 20", "earnings_growth > 10%"]}},
       "exit": {{"profit_target": 0.15, "stop_loss": 0.05}},
       "position_size": 0.10
   }}
   """
   ```

2. **Ollama Integration** (3 days)
   ```python
   # src/fks_ai/services/llm.py
   from ollama import Client
   
   class StrategyGenerator:
       def __init__(self, model='llama3'):
           self.client = Client()
           self.model = model
       
       def generate(self, symbol: str, data_summary: dict):
           # Step 1: Analyze
           analysis = self.client.generate(
               model=self.model,
               prompt=ANALYZE_PROMPT.format(**data_summary)
           )
           
           # Step 2: Propose strategy
           strategy = self.client.generate(
               model=self.model,
               prompt=STRATEGY_PROMPT + f"\nAnalysis:\n{analysis}"
           )
           
           return self._parse_strategy(strategy)
       
       def _parse_strategy(self, text: str):
           # Extract JSON from LLM output
           import json, re
           match = re.search(r'\{.*\}', text, re.DOTALL)
           return json.loads(match.group()) if match else None
   ```

3. **Strategy Validation** (4 days)
   ```python
   # src/fks_ai/validators/strategy.py
   def validate_strategy(strategy: dict):
       required = ['name', 'entry', 'exit', 'position_size']
       if not all(k in strategy for k in required):
           raise ValueError("Missing required fields")
       
       # Check entry conditions are parseable
       for condition in strategy['entry']['conditions']:
           # Validate syntax (e.g., "PE < 20")
           if not re.match(r'^\w+\s*[<>=!]+\s*[\d.]+', condition):
               raise ValueError(f"Invalid condition: {condition}")
       
       return True
   ```

4. **Backtesting Integration** (1 week)
   - Send LLM strategy to fks_app for backtesting
   - Use existing backtest framework (TA-Lib, Pandas)
   - Calculate metrics: Sharpe, cumulative return, max drawdown
   - Compare to benchmarks (buy-hold, equal-weight portfolio)

5. **API Endpoints** (2 days)
   ```python
   @app.post("/ai/generate-strategy")
   async def generate_strategy(request: StrategyRequest):
       # Fetch data from fks_data
       data = fetch_data_summary(request.symbol)
       
       # Generate strategy
       strategy = generator.generate(request.symbol, data)
       
       # Validate
       validate_strategy(strategy)
       
       # Backtest in fks_app
       backtest_result = await backtest_strategy(strategy)
       
       return {"strategy": strategy, "backtest": backtest_result}
   ```

**Deliverables**:
- Prompt templates in fks_ai/prompts/
- StrategyGenerator service in fks_ai/services/llm.py
- Validator in fks_ai/validators/strategy.py
- API endpoint: POST /ai/generate-strategy (returns strategy + backtest metrics)
- Documentation: Prompt tuning guide, example outputs

**Testing**:
- Unit tests: Prompt formatting, JSON parsing
- Integration tests: Generate strategy for BTCUSDT, validate structure
- Backtest: Compare Llama-3 vs. Perplexity (article benchmark)
- Edge cases: Handle empty responses, invalid JSON

---

### Phase 4: Integration & Orchestration (2 weeks)
**Goal**: Connect AI features to fks_app and fks_main for live trading

**Tasks**:
1. **Regime-Aware Strategy Execution** (1 week)
   ```python
   # src/fks_app/services/regime_trader.py
   class RegimeAwareTrader:
       def __init__(self):
           self.ai_client = httpx.AsyncClient(base_url="http://fks_ai:8006")
       
       async def get_regime(self, symbol: str):
           response = await self.ai_client.post("/ai/regime", json={"symbol": symbol})
           return response.json()["regime"]
       
       def adjust_position_size(self, base_size: float, regime: int):
           multipliers = {0: 1.5, 1: 0.5, 2: 0.3}  # calm/transition/volatile
           return base_size * multipliers.get(regime, 1.0)
       
       async def execute_signal(self, signal: Signal):
           regime = await self.get_regime(signal.symbol)
           adjusted_size = self.adjust_position_size(signal.quantity, regime)
           
           # Log regime context
           logger.info(f"Regime {regime} detected, adjusted size {signal.quantity} → {adjusted_size}")
           
           # Execute via fks_execution
           await execution_client.place_order(
               symbol=signal.symbol,
               quantity=adjusted_size,
               side=signal.side
           )
   ```

2. **Celery Task Scheduling** (3 days)
   ```python
   # src/fks_main/celery_beat_schedule.py
   CELERYBEAT_SCHEDULE = {
       'update-regimes': {
           'task': 'fks_ai.tasks.update_regimes',
           'schedule': crontab(minute='*/15'),  # Every 15 minutes
       },
       'retrain-regime-model': {
           'task': 'fks_ai.tasks.train_regime_model',
           'schedule': crontab(hour=2, minute=0),  # Daily at 2 AM
       },
       'generate-weekly-strategies': {
           'task': 'fks_ai.tasks.generate_strategies',
           'schedule': crontab(day_of_week=1, hour=0),  # Monday midnight
       },
   }
   ```

3. **Monitoring & Alerting** (4 days)
   - Add Grafana dashboard panels:
     - Regime distribution (pie chart)
     - Strategy win rate by regime (bar chart)
     - LLM generation success rate (time series)
   - Prometheus metrics:
     ```python
     from prometheus_client import Counter, Histogram
     
     regime_updates = Counter('regime_updates_total', 'Regime update count')
     llm_generation_time = Histogram('llm_generation_seconds', 'LLM generation latency')
     strategy_backtest_sharpe = Histogram('strategy_sharpe', 'Backtest Sharpe ratio')
     ```

4. **Web UI Enhancements** (4 days)
   - Regime timeline visualization (Seaborn lineplot)
   - LLM strategy editor: Prompt → Generate → Backtest → Approve
   - Portfolio view with regime overlay (highlight regime changes)

**Deliverables**:
- RegimeAwareTrader in fks_app/services/regime_trader.py
- Celery Beat schedule in fks_main/django/celery.py
- Grafana dashboards in monitoring/grafana/dashboards/ai_strategy.json
- Web UI updates in fks_web/templates/ai_strategy/

**Testing**:
- Integration tests: End-to-end regime detection → position adjustment
- Performance tests: Celery task execution time (<5s per regime update)
- UI tests: Verify regime timeline renders, strategy editor works

---

### Phase 5: Validation & Optimization (2 weeks)
**Goal**: Backtest, tune hyperparameters, validate against research

**Tasks**:
1. **Historical Backtests** (1 week)
   - Run regime-aware strategies on 2-year historical data
   - Compare to baselines: buy-hold, momentum, mean-reversion
   - Metrics: Sharpe, Sortino, max drawdown, win rate
   - Validate against article (Sharpe 10+ in calm regimes)

2. **Hyperparameter Tuning** (3 days)
   - Optuna optimization:
     - VAE latent_dim (1-5)
     - Transformer seq_len (8-32)
     - Position size multipliers by regime
   - Cross-validation: Walk-forward analysis (retrain monthly)

3. **LLM Model Comparison** (2 days)
   - Test Llama-3 variants (8B, 70B)
   - Compare to Perplexity benchmark (90% return)
   - Fine-tune on finance data (optional)

4. **Risk Analysis** (2 days)
   - Stress test: Regime transitions during high volatility (2020 crash, 2022 bear)
   - Edge cases: Data gaps, model failures, LLM hallucinations
   - Failsafes: Fallback to non-regime strategies if AI unavailable

**Deliverables**:
- Backtest report: docs/AI_STRATEGY_BACKTEST_RESULTS.md
- Hyperparameter configs: fks_ai/config/regime_model_params.yaml
- Risk analysis: docs/AI_STRATEGY_RISK_ANALYSIS.md

**Testing**:
- Reproduce article results on SPY (regime detection)
- Validate LLM strategies: Backtest on AAPL, compare to Perplexity
- Load testing: 1000 regime inferences/minute

---

## Technical Specifications

### Model Architecture Details

**VAE (Variational Autoencoder)**:
```
Input: [logret, vol_21d, momentum_5d] (3 features)
Encoder: Linear(3 → 16) → ReLU → Linear(16 → 4) [mu + logvar]
Latent: 2D (reparameterization trick)
Decoder: Linear(2 → 16) → ReLU → Linear(16 → 3)
Loss: Reconstruction (MSE) + KL divergence
Optimizer: Adam (lr=0.001)
Epochs: 50
```

**Transformer**:
```
Input: (batch, seq_len=16, features=3)
Embedding: Linear(3 → 64)
Encoder: 2 layers, 4 heads, d_model=64
Classifier: Linear(64 → 3) [calm/transition/volatile]
Loss: CrossEntropyLoss
Optimizer: Adam (lr=0.0001)
Epochs: 80
```

**KMeans**:
```
n_clusters: 3
init: k-means++
random_state: 42
```

### LLM Configuration

**Ollama Models**:
- **Primary**: llama3:8b (balance of speed/quality)
- **Fallback**: mistral:7b (faster inference)
- **Premium**: llama3:70b (highest quality, slower)

**Prompt Parameters**:
- Temperature: 0.7 (creativity vs. consistency)
- Max tokens: 1024 (sufficient for strategy JSON)
- Top-p: 0.9
- Repeat penalty: 1.1

### Data Requirements

**Minimum Data for Training**:
- **Regime Detection**: 2 years daily data (730 samples)
- **LLM Strategy Gen**: 1 year + fundamentals (quarterly)

**Feature Engineering**:
| Feature | Calculation | Purpose |
|---------|-------------|---------|
| logret | log(close / close.shift(1)) | Normalized returns |
| vol_21d | logret.rolling(21).std() * sqrt(252) | Annualized volatility |
| momentum_5d | close.pct_change(5) | Short-term momentum |

**Storage Estimates**:
- Fundamentals table: ~50 MB/year/symbol
- VAE model: ~100 KB
- Transformer model: ~500 KB
- LLM cache: ~4 GB (Llama-3 8B)

### API Specifications

**POST /ai/regime**:
```json
Request:
{
  "symbol": "BTCUSDT",
  "features": [[0.01, 0.15, 0.03], ...],  // Optional (auto-fetch if empty)
  "model_version": "v1.2"  // Optional
}

Response:
{
  "symbol": "BTCUSDT",
  "regime": 0,
  "label": "calm",
  "confidence": 0.87,
  "timestamp": "2025-10-24T10:30:00Z",
  "model_version": "v1.2"
}
```

**POST /ai/generate-strategy**:
```json
Request:
{
  "symbol": "AAPL",
  "model": "llama3:8b",
  "prompt_type": "fundamental",  // or "technical"
  "backtest_years": 2
}

Response:
{
  "strategy": {
    "name": "AAPL Fundamental Value",
    "entry": {"conditions": ["PE < 20", "earnings_growth > 10%"]},
    "exit": {"profit_target": 0.15, "stop_loss": 0.05},
    "position_size": 0.10
  },
  "backtest": {
    "sharpe": 1.87,
    "cumulative_return": 0.90,
    "max_drawdown": -0.12,
    "win_rate": 0.68,
    "num_trades": 47
  },
  "generation_time": 12.4,
  "model_version": "llama3:8b"
}
```

**POST /ai/train-regime-model**:
```json
Request:
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "start_date": "2023-01-01",
  "end_date": "2025-10-24",
  "hyperparams": {
    "latent_dim": 2,
    "seq_len": 16,
    "epochs_vae": 50,
    "epochs_transformer": 80
  }
}

Response:
{
  "status": "training_started",
  "task_id": "abc-123-def",
  "estimated_time": "15-20 minutes",
  "model_version": "v1.3"
}
```

## Performance Benchmarks

### Research Targets (from Articles)

**LLM Strategy Generation**:
| Model | Cumulative Return | Sharpe Ratio | Max Drawdown | Win Rate |
|-------|-------------------|--------------|--------------|----------|
| Perplexity | 90% | 1.87 | -15% | 68% |
| Gemini | 45% | 1.23 | -20% | 55% |
| ChatGPT | 0% | N/A | N/A | 0% (0 trades) |

**Regime Detection**:
| Model | Sharpe (Calm) | Sharpe (Transition) | Sharpe (Volatile) | Avg Sharpe |
|-------|---------------|---------------------|-------------------|------------|
| LGMM | 5.2 | 2.1 | 1.8 | 3.0 |
| VAE | 8.7 | 3.4 | 2.9 | 5.0 |
| Transformer | 11.2 | 4.1 | 3.2 | 6.2 |

### FKS Platform Targets

**Latency Requirements**:
- Regime inference: <1 second
- LLM strategy generation: <30 seconds
- Model training (VAE): ~10 minutes
- Model training (Transformer): ~20 minutes

**Throughput**:
- Regime updates: 100/minute (all symbols)
- LLM generations: 10/hour (quality over quantity)

**Resource Usage**:
- GPU VRAM: <4 GB (Llama-3 8B + models)
- CPU: <50% during inference
- Disk: ~10 GB (models + cache)

## Risk Management & Mitigations

### Identified Risks

**1. LLM Hallucinations**
- **Risk**: Generated strategies may be unprofitable or unbacktestable
- **Example**: ChatGPT's overly strict rules → 0 trades
- **Mitigation**:
  - Mandatory backtesting before live execution
  - Human review in fks_web UI (approve/reject)
  - Validation layer (check syntax, logic)
  - Track success rate (disable LLM if <40% profitable)

**2. Model Overfitting**
- **Risk**: Regime models fit to historical bull markets, fail in new conditions
- **Mitigation**:
  - Walk-forward validation (retrain monthly)
  - Stress test on 2020 crash, 2022 bear market
  - Ensemble models (combine VAE + LGMM)
  - Monitor regime stability (alert if transitions >10/day)

**3. Data Quality**
- **Risk**: Missing fundamentals, gaps in OHLCV
- **Mitigation**:
  - Data validation in fks_data (check nulls, outliers)
  - Fallback to technical-only strategies if fundamentals unavailable
  - Alert on data staleness (>1 hour old)

**4. Computational Limits**
- **Risk**: GPU OOM, training fails
- **Mitigation**:
  - Batch size tuning (reduce if OOM)
  - Fallback to CPU (slower but stable)
  - Schedule training off-hours (2 AM)
  - Monitor GPU usage (alert at >90%)

**5. Regime Misclassification**
- **Risk**: Model labels calm as volatile → incorrect position sizing
- **Mitigation**:
  - Confidence thresholds (require >0.7 for action)
  - Gradual adjustments (smooth transitions, not instant)
  - Fallback to non-regime strategies if uncertainty high
  - Human override in dashboard

### Failsafe Mechanisms

```python
# src/fks_app/services/failsafe.py
class AIFailsafe:
    def __init__(self):
        self.ai_failures = 0
        self.max_failures = 5
    
    async def safe_regime_query(self, symbol: str):
        try:
            regime = await ai_client.get_regime(symbol)
            self.ai_failures = 0
            return regime
        except Exception as e:
            self.ai_failures += 1
            logger.error(f"AI regime query failed: {e}")
            
            if self.ai_failures >= self.max_failures:
                # Disable AI, use default strategy
                logger.critical("AI disabled after 5 failures")
                return {"regime": 1, "label": "transition", "fallback": True}
            
            # Retry with exponential backoff
            await asyncio.sleep(2 ** self.ai_failures)
            return await self.safe_regime_query(symbol)
```

## Testing Strategy

### Unit Tests (pytest)
```python
# tests/unit/test_ai_strategy/test_vae.py
def test_vae_forward_pass():
    vae = VAE(input_dim=3, latent_dim=2)
    x = torch.randn(10, 3)
    recon, mu, logvar = vae(x)
    assert recon.shape == (10, 3)
    assert mu.shape == (10, 2)

# tests/unit/test_ai_strategy/test_llm.py
def test_strategy_parser():
    text = '{"name": "Test", "entry": {"conditions": ["PE < 20"]}}'
    strategy = parse_strategy(text)
    assert strategy['name'] == "Test"
```

### Integration Tests
```python
# tests/integration/test_ai_strategy/test_regime_flow.py
async def test_regime_detection_flow():
    # 1. Fetch data from fks_data
    features = await data_client.get_features("BTCUSDT", days=16)
    
    # 2. Get regime from fks_ai
    regime = await ai_client.get_regime("BTCUSDT")
    assert regime['regime'] in [0, 1, 2]
    
    # 3. Adjust position in fks_app
    adjusted = trader.adjust_position_size(0.1, regime['regime'])
    assert 0.01 <= adjusted <= 0.15
```

### Backtesting Validation
```python
# tests/validation/test_ai_strategy/test_regime_backtest.py
def test_regime_strategy_vs_baseline():
    # Historical data: 2 years
    data = load_historical_data("BTCUSDT", years=2)
    
    # Run regime-aware strategy
    regime_result = backtest_with_regimes(data)
    
    # Run baseline (no regimes)
    baseline_result = backtest_baseline(data)
    
    # Assert improvement
    assert regime_result.sharpe > baseline_result.sharpe * 1.2
    assert regime_result.max_drawdown < baseline_result.max_drawdown
```

## Monitoring & Observability

### Grafana Dashboards

**AI Strategy Dashboard**:
- **Regime Distribution**: Pie chart (% time in calm/transition/volatile)
- **Strategy Performance**: Line chart (cumulative return by regime)
- **LLM Success Rate**: Gauge (% backtests with Sharpe > 1.0)
- **Model Health**: Table (last training time, accuracy, version)

**Prometheus Metrics**:
```python
# fks_ai/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Regime detection
regime_updates_total = Counter('regime_updates_total', 'Total regime updates', ['symbol'])
regime_inference_seconds = Histogram('regime_inference_seconds', 'Regime inference latency')
regime_confidence = Gauge('regime_confidence', 'Current regime confidence', ['symbol'])

# LLM generation
llm_generations_total = Counter('llm_generations_total', 'Total LLM generations', ['model'])
llm_generation_seconds = Histogram('llm_generation_seconds', 'LLM generation time')
llm_validation_failures = Counter('llm_validation_failures', 'Invalid LLM outputs')

# Strategy performance
strategy_sharpe = Histogram('strategy_sharpe', 'Backtest Sharpe ratio', ['strategy_name'])
strategy_trades = Counter('strategy_trades_total', 'Total trades executed', ['strategy_name', 'regime'])
```

### Logging Standards
```python
# Use structured logging
logger.info(
    "Regime detected",
    extra={
        "symbol": "BTCUSDT",
        "regime": 0,
        "confidence": 0.87,
        "model_version": "v1.2",
        "inference_time": 0.42
    }
)

# Log all AI decisions
logger.info(
    "Position adjusted for regime",
    extra={
        "original_size": 0.10,
        "adjusted_size": 0.15,
        "regime": 0,
        "multiplier": 1.5
    }
)
```

## Security & Compliance

### Data Security
- **API Keys**: Store EODHD key in .env (never commit)
- **Model Files**: Secure ./ml_models volume (read-only for web service)
- **User Inputs**: Sanitize LLM prompts (prevent injection)

### Compliance
- **Prop Firms**: Ensure regime-adjusted strategies comply with FXIFY/Topstep rules (e.g., daily loss limits)
- **Backtesting**: Log all strategy generations for audit trail
- **Human-in-Loop**: Require approval for LLM strategies before live execution

### Rate Limiting
```python
# fks_ai/middleware/rate_limit.py
@limiter.limit("10/hour")  # Max 10 LLM generations per hour
async def generate_strategy(request: StrategyRequest):
    # ... implementation
```

## Cost Analysis

### Infrastructure Costs
- **GPU**: No additional cost (use existing fks_ai CUDA setup)
- **LLM**: Zero cost (local Ollama vs. $0.03/1K tokens OpenAI)
- **Data**: EODHD $80/month (optional for stocks; crypto via CCXT is free)
- **Storage**: Negligible (~10 GB models + cache)

### ROI Estimate
**Assumptions**:
- Trading capital: $10,000
- Baseline Sharpe: 1.5 (momentum strategy)
- Regime-aware Sharpe: 2.5 (research target)
- Annual return improvement: +15%

**Savings**:
- LLM API fees avoided: ~$200/month (if using OpenAI for 100 generations)
- Improved risk-adjusted returns: +$1,500/year (15% on $10K)

**Total ROI**: $1,700/year savings + performance gains

### Development Costs
- **Phase 1-5**: ~12 weeks development time
- **Ongoing**: ~4 hours/month maintenance (model retraining, monitoring)

## Future Enhancements

### Phase 6: Multi-Asset Expansion (post-launch)
- Extend to stocks (AAPL, SPY) via EODHD
- Futures regime detection for fks_ninja (ES, NQ contracts)
- Cross-asset correlations (e.g., BTC/SPY regime synchronization)

### Phase 7: Advanced LLM Features
- Fine-tune Llama-3 on finance corpus (earnings calls, SEC filings)
- Multi-agent LLM (analyst + risk manager + trader personas)
- Reinforcement learning from backtests (reward successful strategies)

### Phase 8: Ensemble Models
- Combine LGMM + VAE + Transformer (voting classifier)
- Meta-learning: Learn which model works best per asset
- Adaptive regime thresholds (dynamic n_clusters)

### Phase 9: Real-Time Adaptations
- Intraday regime updates (5-minute windows)
- News sentiment integration (RAG-powered news analysis)
- Order flow regime detection (exchange API feeds)

## Success Criteria

### Phase 1-3 (MVP) Success Metrics
- ✅ Regime model accuracy >70% (validate on held-out test set)
- ✅ LLM strategy backtest Sharpe >1.5 (match Gemini baseline)
- ✅ Inference latency <1s (regime), <30s (LLM)
- ✅ Zero crashes during 1-week continuous operation

### Phase 4-5 (Production) Success Metrics
- ✅ Regime-aware strategy Sharpe >2.0 (vs. baseline 1.5)
- ✅ LLM generation success rate >60% (profitable in backtest)
- ✅ Max drawdown reduction >20% (vs. non-regime baseline)
- ✅ User approval: 80% of traders enable AI features

### Long-Term (6-12 months)
- ✅ Multi-asset support (crypto + stocks + futures)
- ✅ Automated strategy evolution (retrain weekly, auto-deploy if Sharpe >2.0)
- ✅ Community contributions (open-source regime models)

## Conclusion

This integration plan leverages FKS's existing GPU infrastructure and microservices architecture to add cutting-edge AI capabilities with minimal architectural changes. The phased approach (data → DL regimes → LLM strategies → integration → validation) ensures incremental progress with testable milestones.

Key advantages:
- **Zero API Costs**: Local LLM inference via Ollama
- **Proven Performance**: Research shows Sharpe ratios up to 11 in calm regimes
- **Modular Design**: Isolated in fks_ai service, easy to disable/rollback
- **Transparent**: Monitoring, logging, and user control

Start with **Phase 2 (DL Regime Detection)** for immediate ROI, then add **Phase 3 (LLM Strategies)** for long-term adaptability. This positions FKS as a next-generation adaptive trading platform.

---

**Next Steps**:
1. Review plan with team, prioritize phases
2. Set up EODHD API account (optional for stocks)
3. Create feature branch: `feature/ai-strategy-integration`
4. Start Phase 1: Data foundation in fks_data
5. Track progress in GitHub Issues (link to project board)

**References**:
- Article 1: [Comparing 3 LLMs for Trading Strategies](https://wire.insiderfinance.io/comparing-3-llms-for-generating-profitable-trading-strategies-6e9e9c8af8f7)
- Article 2: [Deep Learning for Market Regimes](https://wire.insiderfinance.io/deep-learning-for-hidden-market-regimes-vae-transformer-extension-to-lgmm-8d2e1b5c8e8b)
- Deloitte 2023 Quant Finance Report
- arXiv: LLM Trading Agents
- TensorTrade, QuantConnect, Alpaca APIs
