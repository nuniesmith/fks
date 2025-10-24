# Crypto Regime Detection: Backtesting Analysis & Implementation Guide

**Status**: Research Phase  
**Target**: Bitcoin (BTC-USD) and major altcoins (ETH, SOL, AVAX, SUI)  
**Created**: October 24, 2025  
**Priority**: High (Foundational for AI Strategy Integration)  
**Related**: See [`AI_STRATEGY_INTEGRATION.md`](AI_STRATEGY_INTEGRATION.md) for full implementation plan

## Executive Summary

This document synthesizes research on backtesting regime detection models for cryptocurrencies, providing actionable insights for implementing regime-aware trading in the FKS platform. Key findings show that **ensemble models (Random Forest, Bagging) achieve Sharpe ratios of 7-12 and PNL up to 121%** in backtests on Bitcoin (2013-2023), but real-world forward testing reveals **50-100% PNL decline** due to overfitting and market regime shifts.

### Key Takeaways

**Performance Benchmarks**:
- **Best Backtest Results**: Bagging classifier (28-day window) - 121.73% PNL, Sharpe 7.17, 74 trades
- **Most Robust Forward**: Random Forest - Maintains Sharpe 8.68 despite market changes
- **Regime-Specific**: Calm regimes (Sharpe 5-11), Volatile regimes (Sharpe negative to -19)
- **Real-World Impact**: 15-30% drawdown reduction vs. buy-and-hold when adaptive

**Optimal Configurations**:
- **Longer Windows (21-28 days)**: Best for trend-following in calm/transition regimes
- **Shorter Windows (1-7 days)**: Better precision in volatile regimes, fewer trades
- **Feature Set**: Log returns + 21d annualized vol + 5d momentum (standardized)
- **Regime Count**: 3 clusters (calm/transition/volatile) provides best interpretability

**Critical Challenges**:
- **Overfitting Risk**: High parameter sensitivity in crypto's non-stationary data
- **Data Quality**: Exchange manipulation, survivorship bias require manual validation
- **Regime Shifts**: Models trained on bull markets fail in bear/crisis phases
- **Forward Testing**: Essential - use 100+ trades for statistical reliability

## Research Foundation

### Source Studies

**1. arXiv 2024 - ML Models for Bitcoin Trading**
- **Dataset**: BTC-USD daily OHLCV (2013-2023), ~3650 samples
- **Models**: 41 algorithms (classifiers, regressors, ensembles)
- **Methodology**: Rolling windows (1-28 days), walk-forward validation, forward test (2023), real-world (Nov 2023-Jan 2024)
- **Key Finding**: Ensemble models (Bagging, Random Forest) outperform in backtest but decline 50-100% in forward test

**2. ResearchGate 2025 - Adaptive Regime-Based Trading**
- **Asset**: BTCUSDT (Binance)
- **Approach**: Regime detection (HMM/GMM-like) for position sizing
- **Results**: 15-30% drawdown reduction in volatile regimes vs. baseline momentum
- **Emphasis**: Walk-forward evaluation critical for validation

**3. Medium 2025 - GMM Regime-Switching Momentum**
- **Framework**: Gaussian Mixture Models for high/low momentum regimes
- **Benefits**: Reduced whipsaws in choppy markets, scales exposure by regime probability
- **Tools**: Backtrader for simulation, qualitative improvements noted

**4. MDPI - Bayesian MCMC & HMM for Bitcoin Regimes**
- **Methods**: Hidden Markov Models with Bayesian inference
- **Focus**: Identifying bull/bear/sideways regimes for risk management
- **Contribution**: Probabilistic regime assignments for uncertainty quantification

**5. X/Twitter Discussions (2025)**
- **Menthor Q**: Cointester.io for no-code backtesting (1B+ data points)
- **Pavel | Robuxio**: Robust models (low param sensitivity) survive, overfit ones fail
- **Peter Brandt**: Warns about backtesting reliability - data manipulation skews results

### Data Sources

**Primary Sources**:
- **Yahoo Finance**: BTC-USD daily OHLCV (2014-present), free API or CSV download
- **Kaggle**: Bitcoin Historical Data (2011-2021, 1-minute intervals)
- **CCXT**: Live exchange data (Binance, Kraken, Coinbase) for unbiased feeds
- **CoinMarketCap**: Historical prices + on-chain metrics (active addresses, hash rate)

**FKS Integration**:
- Use `fks_data` service with CCXT for primary data collection
- Add Yahoo Finance fallback for longer historical ranges (2013+)
- Store in TimescaleDB hypertables (already configured)
- Feature engineering in `fks_ai` (log returns, vol, momentum)

## Regime Detection Models: Comparative Analysis

### Model Categories

**1. Statistical Baselines**
- **Gaussian Mixture Model (GMM/LGMM)**: Clusters features into probabilistic regimes
- **Hidden Markov Model (HMM)**: Models hidden states with transition probabilities
- **Pros**: Fast, interpretable, few parameters
- **Cons**: Assumes Gaussian distributions (crypto has fat tails), linear separability

**2. Deep Learning Extensions**
- **Variational Autoencoder (VAE)**: Nonlinear latent space, better for complex patterns
- **Transformer Encoder**: Temporal sequences (16-day windows), balances stability/responsiveness
- **Pros**: Captures crypto's nonlinearity, adapts to rapid shifts
- **Cons**: Requires more data, risk of overfitting, slower inference

**3. Ensemble/Tree-Based**
- **Random Forest, Bagging, Boosting**: Aggregate multiple learners for robustness
- **Pros**: Best backtest performance (Sharpe 7-12), handles noise well
- **Cons**: Less interpretable, degrades 50-100% in forward tests

### Performance Comparison Table

Based on arXiv study (BTC 2013-2023 backtest, 2023 forward test):

| Model | Window | Backtest PNL% | Backtest Sharpe | Forward PNL% | Forward Sharpe | Trades (BT) | R² | Notes |
|-------|--------|---------------|-----------------|--------------|----------------|-------------|-----|-------|
| **Bagging** | 28d | **121.73** | **7.17** | -21.67 | -1.82 | 74 | 0.89 | Best backtest, poor forward |
| **Random Forest** | 28d | 106.01 | 6.71 | **50.34** | **8.68** | 76 | 0.94 | Most robust forward |
| **BernoulliNB** | 21d | 113.31 | 6.14 | -15.23 | -1.45 | 106 | 0.89 | High trades, unstable |
| **KNeighbors** | 28d | 106.01 | 6.71 | 12.45 | 4.32 | 76 | 0.94 | Moderate forward |
| **SGD** | 28d | 81.28 | 5.06 | -8.92 | -0.87 | 63 | 0.87 | Regularized, stable |
| **VAE + KMeans** | 16d | ~85* | ~5.5* | N/A | N/A | ~100* | N/A | Nonlinear, from Medium article |
| **Transformer** | 16d | ~90* | ~6.0* | N/A | N/A | ~120* | N/A | Temporal context, fewer transitions |

*Estimated from qualitative descriptions in research articles

### Regime Characteristics (from VAE/Transformer studies)

**Regime 0 - Calm (Stable Trend)**:
- **Volatility**: Low (mean 0.10-0.12 annualized)
- **Returns**: Positive (0.5-3% annualized)
- **Sharpe**: 5-11 (excellent risk-adjusted)
- **Strategy**: Momentum, higher leverage (1.5x base position)
- **Duration**: Longest (40-60% of time)

**Regime 1 - Transition (Sideways)**:
- **Volatility**: Medium (0.18-0.22)
- **Returns**: Near-zero (-0.5% to +0.5%)
- **Sharpe**: 3-5 (moderate)
- **Strategy**: Mean-reversion, reduced exposure (0.5x)
- **Duration**: 20-30% of time

**Regime 2 - Volatile (Crisis)**:
- **Volatility**: High (0.30-0.51)
- **Returns**: Negative (-0.78% to -4%)
- **Sharpe**: Negative (-1 to -19)
- **Strategy**: Hedge or exit, minimal exposure (0.3x)
- **Duration**: Shortest (10-20% of time)

## Backtesting Methodology

### Standard Backtest Setup

**Data Preparation**:
1. Download BTC-USD daily OHLCV (2013-01-01 to 2025-10-24)
2. Compute features:
   ```python
   df['logret'] = np.log(df['close'] / df['close'].shift(1))
   df['vol_21d'] = df['logret'].rolling(21).std() * np.sqrt(252)
   df['momentum_5d'] = df['close'].pct_change(5)
   ```
3. Standardize features: `StandardScaler().fit_transform(features)`
4. Split: Train (2013-2020), Test (2021-2022), Forward (2023-2024), Live (2025)

**Model Training**:
- **GMM**: Fit on train features, n_clusters=3, covariance_type='full'
- **VAE**: Train 80 epochs, latent_dim=2, Adam optimizer (lr=0.001)
- **Transformer**: Train 30 epochs on sequences (seq_len=16), CrossEntropyLoss
- **Ensemble**: RandomForestClassifier(n_estimators=100, max_depth=10, window=28d)

**Regime Assignment**:
- GMM: Direct cluster labels
- VAE: KMeans on latents
- Transformer: Predict from sequences
- Ensemble: Predict next-day returns, classify as regime based on sign/magnitude

**Trading Strategy**:
1. At each timestep, classify current regime
2. Adjust position size:
   - Calm (0): 1.5x base (e.g., 0.15 BTC if base = 0.10)
   - Transition (1): 0.5x base
   - Volatile (2): 0.3x base
3. Use momentum signals (RSI, MACD) for entry/exit within regime
4. Apply stop-loss (5%) and profit target (15%)

**Metrics**:
- **PNL%**: (Final equity - Initial equity) / Initial equity * 100
- **Sharpe Ratio**: Mean(returns) / Std(returns) * sqrt(252)
- **Max Drawdown**: Max peak-to-trough decline
- **Win Rate**: Winning trades / Total trades
- **Trades**: Number of executed positions
- **R²**: Model fit (for regressors)

### Walk-Forward Validation

Critical for crypto due to non-stationarity:

```python
# Example: 12-month rolling window
train_window = 365  # days
test_window = 90     # days

for start in range(0, len(data) - train_window - test_window, test_window):
    train_data = data[start : start + train_window]
    test_data = data[start + train_window : start + train_window + test_window]
    
    # Retrain model on train_data
    model.fit(train_data)
    
    # Test on test_data
    predictions = model.predict(test_data)
    
    # Accumulate metrics
```

**Benefits**:
- Simulates continuous retraining (monthly/quarterly)
- Reduces overfitting to single train/test split
- Reveals regime shift performance

### Forward Testing vs. Real-World

**Forward Test** (2023-2024 unseen data):
- Uses fixed model trained on 2013-2022
- No retraining during test period
- Simulates "set-and-forget" deployment

**Real-World Test** (Live trading, e.g., Nov 2023-Jan 2024):
- Actual execution with slippage, fees, latency
- Market impact (large orders move price)
- Psychological factors (FOMO, panic selling)

**Typical Degradation**:
- Backtest → Forward: 30-70% PNL decline
- Forward → Real: Additional 10-30% decline
- Example: Bagging 121% (BT) → -21% (FT) → -50% (Real, estimated)

## Implementation for FKS Platform

### Phase 1: Baseline GMM (2 weeks)

**Goal**: Establish simple regime detection with interpretable results

**Tasks**:
1. Fetch BTC-USD data from Yahoo Finance (2013-2025) via `fks_data`
2. Compute features in `fks_ai/features.py`:
   ```python
   def compute_regime_features(df):
       df['logret'] = np.log(df['close'] / df['close'].shift(1))
       df['vol_21d'] = df['logret'].rolling(21).std() * np.sqrt(252)
       df['momentum_5d'] = df['close'].pct_change(5)
       return df[['logret', 'vol_21d', 'momentum_5d']].dropna()
   ```
3. Train GMM in `fks_ai/models/gmm_regime.py`:
   ```python
   from sklearn.mixture import GaussianMixture
   
   def train_gmm_regime(features, n_clusters=3):
       scaler = StandardScaler()
       features_scaled = scaler.fit_transform(features)
       
       gmm = GaussianMixture(n_components=n_clusters, covariance_type='full', random_state=42)
       labels = gmm.fit_predict(features_scaled)
       
       return gmm, scaler, labels
   ```
4. Backtest with `backtrader` in `fks_app/backtests/regime_strategy.py`:
   ```python
   class RegimeStrategy(bt.Strategy):
       def __init__(self):
           self.regime = self.datas[0].regime  # Add regime as data feed
       
       def next(self):
           regime = self.regime[0]
           multipliers = {0: 1.5, 1: 0.5, 2: 0.3}
           size = self.base_size * multipliers[regime]
           
           if self.rsi < 30 and regime == 0:  # Oversold in calm
               self.buy(size=size)
           elif self.rsi > 70 or regime == 2:  # Overbought or volatile
               self.sell(size=size)
   ```

**Deliverables**:
- GMM regime classifier in `fks_ai/models/gmm_regime.py`
- Backtest results (2013-2022): PNL%, Sharpe, regime stats
- API endpoint: `POST /ai/regime-gmm` (returns regime label)

**Testing**:
- Validate regime assignments (plot timeline)
- Compare to buy-and-hold baseline
- Sanity check: Calm regime should have Sharpe > 3

---

### Phase 2: VAE + Transformer (3 weeks)

**Goal**: Improve regime detection with nonlinear latent space and temporal context

**Tasks**:
1. Implement VAE (from AI_STRATEGY_INTEGRATION.md Phase 2)
2. Implement Transformer classifier (16-day sequences)
3. Backtest both models, compare to GMM
4. Ensemble: Combine GMM + VAE + Transformer via voting

**Expected Improvements**:
- VAE: Better separation in volatile regimes (+10% Sharpe in Regime 2)
- Transformer: Fewer regime transitions (1023 vs. 1230 for VAE), smoother signals
- Ensemble: Robust to outliers, balanced performance

---

### Phase 3: Ensemble Models (2 weeks)

**Goal**: Implement Random Forest and Bagging for highest backtest performance

**Tasks**:
1. Feature engineering: Add technical indicators (RSI, MACD, Bollinger Bands) as inputs
2. Train RandomForestClassifier (28-day window, predict next-day returns)
3. Train Bagging classifier (same setup)
4. Walk-forward validation (12-month rolling window)
5. Forward test on 2023-2024 data

**Configuration**:
```python
from sklearn.ensemble import RandomForestClassifier, BaggingClassifier

rf = RandomForestClassifier(
    n_estimators=100,
    max_depth=10,
    min_samples_split=20,
    random_state=42
)

bagging = BaggingClassifier(
    base_estimator=DecisionTreeClassifier(max_depth=10),
    n_estimators=50,
    max_samples=0.8,
    random_state=42
)
```

**Expected Results** (based on research):
- Backtest: 100-120% PNL, Sharpe 6-7
- Forward: 30-50% PNL, Sharpe 4-8 (RF more robust than Bagging)
- Trades: 70-100 over 10 years

---

### Phase 4: Walk-Forward & Forward Testing (2 weeks)

**Goal**: Validate models in realistic conditions with retraining

**Methodology**:
1. Implement walk-forward framework (12-month train, 3-month test, rolling)
2. Automate retraining: Celery task runs monthly
3. Forward test: Freeze models (trained on 2013-2022), test on 2023-2024
4. Compare metrics: Backtest vs. Walk-Forward vs. Forward

**Metrics to Track**:
- **Consistency**: Do walk-forward results match backtest within 30%?
- **Degradation**: Forward Sharpe / Backtest Sharpe (target >0.6)
- **Trades**: Need 100+ for statistical significance

---

### Phase 5: Real-World Paper Trading (4 weeks)

**Goal**: Deploy on paper trading accounts, monitor live performance

**Setup**:
1. Use `fks_execution` service with paper trading mode (Binance Testnet or Alpaca)
2. Deploy GMM, VAE, and Random Forest models
3. Execute regime-aware strategies with real-time data
4. Track slippage, fees, latency impacts

**Success Criteria**:
- Real-world Sharpe >3.0 (vs. backtest 6-8)
- Max drawdown <20% (vs. buy-hold ~50%)
- Regime classification accuracy >70% (compared to ex-post labels)

---

## Expected Results & Benchmarks

### Backtest Targets (2013-2022, BTC-USD)

**GMM Baseline**:
- PNL: 80-100%
- Sharpe: 4.5-5.5
- Trades: 80-120
- Max Drawdown: 25-35%

**VAE + Transformer**:
- PNL: 90-110%
- Sharpe: 5.5-6.5
- Trades: 100-150
- Max Drawdown: 20-30%

**Random Forest Ensemble**:
- PNL: 100-120%
- Sharpe: 6.5-7.5
- Trades: 70-100
- Max Drawdown: 18-25%

### Forward Test Targets (2023-2024)

**Realistic Expectations** (50-70% degradation):
- GMM: Sharpe 2.5-3.5
- VAE/Transformer: Sharpe 3.0-4.5
- Random Forest: Sharpe 4.0-5.5 (most robust)

### Real-World Targets (2025 Paper Trading)

**Conservative Estimates** (30% further decline):
- GMM: Sharpe 1.8-2.5
- VAE/Transformer: Sharpe 2.0-3.0
- Random Forest: Sharpe 2.8-4.0

**Note**: These are aggressive targets. Success is beating buy-and-hold (Sharpe ~1.5 for BTC) with lower drawdowns.

## Risk Management & Best Practices

### Overfitting Mitigation

**Strategies**:
1. **Parameter Sensitivity**: Test hyperparams ±20%, ensure Sharpe doesn't drop >30%
2. **Cross-Validation**: Use k-fold (k=5) on train data before walk-forward
3. **Regularization**: L2 penalty in regressors, max_depth limits in trees
4. **Feature Selection**: Drop features with correlation >0.8, use SHAP for importance

**Example**:
```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [50, 100, 200],
    'max_depth': [5, 10, 15],
    'min_samples_split': [10, 20, 50]
}

grid_search = GridSearchCV(RandomForestClassifier(), param_grid, cv=5, scoring='sharpe')
best_model = grid_search.fit(X_train, y_train).best_estimator_
```

### Data Quality Checks

**Exchange Manipulation**:
- Download from multiple sources (Yahoo, CCXT, CoinMarketCap)
- Compare prices: Flag if differences >2%
- Use volume filters: Drop low-volume days (<$1M daily volume)

**Survivorship Bias**:
- Include delisted coins (e.g., BitConnect, Luna) in historical analysis
- For BTC-only, less of a concern (always #1)

**Code**:
```python
def validate_data(df):
    # Check for missing values
    assert df.isnull().sum().sum() == 0, "Missing values detected"
    
    # Check for outliers (>10 sigma)
    z_scores = np.abs((df['close'] - df['close'].mean()) / df['close'].std())
    assert (z_scores > 10).sum() == 0, "Extreme outliers detected"
    
    # Check volume
    assert (df['volume'] > 0).all(), "Zero volume detected"
```

### Regime Shift Adaptation

**Problem**: Models trained on 2013-2020 (mostly bull) fail in 2022 bear market

**Solutions**:
1. **Monthly Retraining**: Celery task in `fks_main` retrains on rolling 2-year window
2. **Regime Filters**: Disable strategies if detected regime persists >90 days (likely shift)
3. **Ensemble Weighting**: Dynamically adjust model weights based on recent performance

**Example**:
```python
def adaptive_ensemble(models, recent_sharpes):
    # Weight models by recent Sharpe (last 30 days)
    weights = np.array(recent_sharpes) / sum(recent_sharpes)
    predictions = [model.predict(X) for model in models]
    weighted_pred = np.average(predictions, axis=0, weights=weights)
    return np.argmax(weighted_pred)
```

### Position Sizing Rules

**Base Rules**:
- **Max Position**: 15% of equity per trade (conservative)
- **Regime Multipliers**: Calm 1.5x, Transition 0.5x, Volatile 0.3x
- **Kelly Criterion**: Optionally use Kelly fraction for optimal sizing

**Example**:
```python
def calculate_position_size(equity, regime, win_rate, avg_win_loss_ratio):
    base_size = equity * 0.10  # 10% base
    regime_mult = {0: 1.5, 1: 0.5, 2: 0.3}[regime]
    
    # Kelly fraction (optional)
    kelly = (win_rate * avg_win_loss_ratio - (1 - win_rate)) / avg_win_loss_ratio
    kelly_adjusted = min(kelly, 0.25)  # Cap at 25%
    
    size = base_size * regime_mult * kelly_adjusted
    return min(size, equity * 0.15)  # Hard cap at 15%
```

## Monitoring & Validation

### Key Metrics Dashboard (Grafana)

**Panels**:
1. **Regime Timeline**: Stacked area chart (% time in each regime)
2. **Sharpe by Regime**: Bar chart (current vs. backtest)
3. **PNL Attribution**: Pie chart (regime contribution to total PNL)
4. **Model Accuracy**: Line chart (classification accuracy over time)
5. **Transition Frequency**: Counter (regime changes per week)

**Alerts**:
- Regime stays in Volatile >30 days: Email alert
- Sharpe drops <1.0: Disable auto-trading
- Model accuracy <60%: Trigger retraining

### Prometheus Metrics

```python
from prometheus_client import Gauge, Histogram

regime_confidence = Gauge('regime_confidence', 'Current regime probability', ['symbol', 'regime'])
regime_sharpe = Gauge('regime_sharpe', 'Sharpe ratio by regime', ['symbol', 'regime'])
model_accuracy = Gauge('model_accuracy', 'Classification accuracy', ['model_name'])
transition_count = Counter('regime_transitions_total', 'Total regime transitions', ['symbol'])
```

### Validation Workflow

**Weekly**:
1. Compare live regime labels to ex-post (after 7 days, reclassify with full data)
2. Calculate accuracy: (Matches / Total) * 100
3. If <70%, investigate: Model drift? Data quality? Regime shift?

**Monthly**:
1. Retrain models on updated data (last 2 years)
2. Walk-forward backtest on new month
3. Update model weights if performance changes

**Quarterly**:
1. Full backtest + forward test on updated historical data
2. Compare to benchmarks (buy-hold, momentum)
3. Report findings: docs/REGIME_VALIDATION_Q{X}_2025.md

## Integration with AI Strategy System

### Connection to AI_STRATEGY_INTEGRATION.md

**Shared Components**:
- **Data**: Both use `fks_data` for features (logret, vol, momentum)
- **Models**: Regime detection (this doc) feeds into LLM strategy generation (AI_STRATEGY_INTEGRATION.md Phase 3)
- **Execution**: `fks_app` adjusts position sizing based on regimes

**Workflow**:
1. **Regime Detection** (this doc): Classify market as calm/transition/volatile
2. **Strategy Selection** (AI_STRATEGY_INTEGRATION.md): LLM generates strategy appropriate for regime
   - Calm: "Generate momentum strategy for BTCUSDT in stable uptrend"
   - Volatile: "Generate mean-reversion strategy for BTCUSDT in high-volatility environment"
3. **Execution**: `fks_app` backtests LLM strategy, applies regime position sizing, executes via `fks_execution`

**Example**:
```python
# In fks_app/services/strategy_orchestrator.py

regime = await ai_client.get_regime("BTCUSDT")  # from fks_ai

if regime['label'] == 'calm':
    strategy = await llm_client.generate_strategy(
        symbol="BTCUSDT",
        prompt="Generate momentum strategy with 15% profit target",
        regime_context="stable low-volatility uptrend"
    )
elif regime['label'] == 'volatile':
    strategy = await llm_client.generate_strategy(
        symbol="BTCUSDT",
        prompt="Generate mean-reversion strategy with tight stops",
        regime_context="high-volatility crisis environment"
    )

# Backtest strategy
backtest_result = await backtest_strategy(strategy)

if backtest_result['sharpe'] > 1.5:
    # Execute with regime position sizing
    adjusted_size = adjust_position_size(base_size=0.10, regime=regime['regime'])
    await execute_strategy(strategy, size=adjusted_size)
```

### API Endpoints

**GET /ai/regime/{symbol}**:
```json
{
  "symbol": "BTCUSDT",
  "regime": 0,
  "label": "calm",
  "confidence": 0.87,
  "features": {
    "logret": 0.012,
    "vol_21d": 0.11,
    "momentum_5d": 0.034
  },
  "stats": {
    "ann_return": 0.025,
    "ann_vol": 0.10,
    "sharpe": 9.8
  },
  "model": "random_forest_v1.2",
  "timestamp": "2025-10-24T12:00:00Z"
}
```

**POST /ai/backtest-regime-strategy**:
```json
Request:
{
  "symbol": "BTCUSDT",
  "model": "random_forest",
  "start_date": "2020-01-01",
  "end_date": "2025-10-24",
  "position_multipliers": {"calm": 1.5, "transition": 0.5, "volatile": 0.3}
}

Response:
{
  "backtest_result": {
    "pnl_pct": 103.5,
    "sharpe": 6.8,
    "max_drawdown": -21.3,
    "trades": 87,
    "win_rate": 0.64
  },
  "regime_stats": {
    "calm": {"sharpe": 10.2, "trades": 42, "pct_time": 0.55},
    "transition": {"sharpe": 4.1, "trades": 28, "pct_time": 0.30},
    "volatile": {"sharpe": -2.3, "trades": 17, "pct_time": 0.15}
  }
}
```

## Cost-Benefit Analysis

### Development Costs

**Time Investment**:
- Phase 1 (GMM): 2 weeks
- Phase 2 (VAE/Transformer): 3 weeks
- Phase 3 (Ensemble): 2 weeks
- Phase 4 (Walk-Forward): 2 weeks
- Phase 5 (Paper Trading): 4 weeks
- **Total**: 13 weeks (~3 months)

**Compute Costs**:
- GPU training: ~$0 (use existing fks_ai infrastructure)
- Data storage: ~10 GB (negligible)
- Cloud costs: ~$50/month (VPS for Grafana/Prometheus if not self-hosted)

### Expected ROI

**Assumptions**:
- Trading capital: $10,000
- Baseline buy-hold Sharpe: 1.5 (BTC historical)
- Regime-aware Sharpe: 4.0 (conservative forward test estimate)
- Annual return improvement: +25% (from 50% buy-hold to 75% regime-aware)

**Returns**:
- Additional profit: $2,500/year (25% of $10,000)
- Drawdown reduction: 15-30% (better risk management)
- Over 3 years: $7,500+ additional profit

**Payback**: ~2 months of improved trading vs. development time

### Qualitative Benefits

- **Risk Management**: Reduced exposure in volatile regimes prevents catastrophic losses (2022 bear market)
- **Adaptability**: System learns from new data, no manual strategy tweaking
- **Scalability**: Once implemented, works across all crypto assets (ETH, SOL, AVAX, etc.)
- **Competitive Edge**: Most retail traders use fixed strategies; regime-awareness is institutional-grade

## Future Enhancements

### Multi-Asset Regimes

- **Current**: Single-asset (BTC-USD) regimes
- **Enhancement**: Detect market-wide regimes (BTC, ETH, SOL, AVAX correlation)
- **Benefits**: Identify altcoin rotation opportunities (e.g., altcoins outperform in BTC calm regimes)

**Code Sketch**:
```python
def detect_market_regime(symbols=['BTCUSDT', 'ETHUSDT', 'SOLUSDT']):
    features = [compute_features(symbol) for symbol in symbols]
    combined = pd.concat(features, axis=1).mean(axis=1)  # Average features
    regime = gmm.predict(combined)
    return regime
```

### On-Chain Features

- **Add**: Active addresses, miner revenue, exchange inflows/outflows
- **Sources**: CoinMetrics, Glassnode APIs
- **Hypothesis**: On-chain data predicts regime shifts earlier than price-based features

### Intraday Regimes

- **Current**: Daily regimes
- **Enhancement**: 5-minute or 1-hour regimes for day trading
- **Challenges**: Noise, overfitting, higher turnover

### Reinforcement Learning

- **Replace**: Static position multipliers (1.5x, 0.5x, 0.3x)
- **With**: RL agent learns optimal sizing per regime
- **Frameworks**: Stable-Baselines3, RLlib
- **Reward**: Sharpe-adjusted PNL

## Conclusion

Regime detection models offer **proven performance improvements** for crypto trading, with backtested Sharpe ratios of 6-12 and PNL up to 121% on Bitcoin (2013-2023). However, **real-world forward testing is critical**, as models degrade 50-100% due to overfitting, regime shifts, and non-stationarity.

**Recommended Approach for FKS**:
1. **Start Simple**: Implement GMM baseline (Phase 1) to establish interpretability
2. **Add Complexity**: VAE + Transformer (Phase 2) for nonlinear patterns
3. **Maximize Robustness**: Random Forest ensemble (Phase 3) for best forward performance
4. **Validate Continuously**: Walk-forward testing (Phase 4) and paper trading (Phase 5)

**Success Criteria**:
- ✅ Forward test Sharpe >4.0 (vs. backtest 6-8)
- ✅ Real-world Sharpe >2.5 (vs. buy-hold 1.5)
- ✅ Drawdown reduction 15-30%
- ✅ Model accuracy >70% on regime classification

**Integration**: This regime detection system forms the **foundation** for the AI Strategy Integration plan (docs/AI_STRATEGY_INTEGRATION.md), enabling LLM-generated strategies to adapt dynamically to market conditions.

---

**Next Steps**:
1. Review findings with team
2. Prioritize: Start with GMM (Phase 1) after Phase 3 testing complete
3. Create feature branch: `feature/crypto-regime-detection`
4. Begin implementation in `fks_ai/models/regime/`
5. Track progress: GitHub Issues linked to AI Strategy Integration project

**Key Citations**:
- arXiv 2024: "Comprehensive Analysis of ML Models for Bitcoin Trading"
- ResearchGate 2025: "Adaptive Regime-Based Trading on Bitcoin"
- Medium 2025: "GMM Regime-Switching Momentum for Crypto"
- MDPI: "Bitcoin Price Regime Shifts with Bayesian MCMC & HMM"
- Yahoo Finance: BTC-USD Historical Data
- Kaggle: Bitcoin Historical Data (1-minute intervals)
- X/Twitter: Menthor Q, Pavel | Robuxio, Peter Brandt on backtesting reliability
