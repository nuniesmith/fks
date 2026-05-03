#!/usr/bin/env python3
"""
FKS Trading System — Printable Section Pages (v8)

Generates a single print-ready HTML file where each page corresponds
to one major system section.  Open in any browser and Ctrl+P to print.

CSS enforces 8.5"×11" landscape with correct margins.
Mermaid diagrams render via CDN (requires internet when opening in browser).

Run:   python scripts/generate_mermaid_html.py
Output: docs/fks_system_printable.html
"""

from pathlib import Path
from typing import Any

# =============================================================================
# SECTIONS — each becomes one printed page
# title:        page header
# subtitle:     short description printed under the title
# receives:     list of (label, page_num) tuples for incoming connections
# sends:        list of (label, page_num) tuples for outgoing connections
# mermaid:      standalone flowchart for this section
#               Use STUB nodes (class "stub") for cross-section references.
# =============================================================================

SECTIONS: list[dict[str, Any]] = [
    # ──────────────────────────────────────────────────────────────
    #  PAGE 1 — OVERVIEW
    # ──────────────────────────────────────────────────────────────
    {
        "title": "FKS System Overview",
        "subtitle": "Freddy Krueger Sniper — Janus (Rust) + Ruby (Python) monorepo architecture",
        "receives": [],
        "sends": [("all sections", "2–21")],
        "mermaid": """
flowchart LR
    subgraph External["🌐 External (p.2)"]
        EXT["APIs & Feeds"]
    end

    subgraph Infra["🏗️ Infrastructure (p.3)"]
        PG["Postgres"]
        RD["Redis"]
        QDB["QuestDB"]
        QDR["Qdrant"]
    end

    subgraph RubyStack["🐍 Ruby — Python  (p.4–15)"]
        direction TB
        RDATA["📥 Data Svc\n:8000 (p.5)"]
        RENG["⚙️ Engine\n(p.6)"]
        RWEB["🖥️ Web\n:8080 (p.14)"]
        RTRAIN["🏋️ Trainer\n:8200 (p.13)"]
        RCHART["📉 Charting\n(p.14)"]
        RRISK["🛡️ Risk (p.10)"]
        RPOS["📈 Positions (p.11)"]
        RBCORE["🔍 Breakout (p.8)"]
        RRUBY["💎 Ruby Sigs (p.7)"]
    end

    subgraph JanusStack["🦀 Janus — Rust  (p.16–21)"]
        direction TB
        JFWD["⚡ Forward\n:7000 (p.17)"]
        JBWD["💤 Backward\n(p.18)"]
        JEXEC["🎯 Execution\n(p.19)"]
        JNEURO["🧠 Neuromorphic\n(p.20)"]
        JCNS["🏥 CNS\n(p.21)"]
    end

    subgraph Mon["📊 Monitoring (p.15)"]
        PROM["Prometheus"]
        GRAF["Grafana"]
        NGINX["Nginx"]
    end

    EXT -->|OHLCV / WS / fills| RDATA
    RDATA <--> PG & RD
    RDATA -->|HTTP /bars/*| JFWD
    JFWD -->|signals| JEXEC
    JFWD <-->|regime + state| JBWD
    JNEURO --> JFWD
    JCNS --> JFWD & JBWD & JEXEC
    RENG --> RBCORE & RRUBY & RRISK
    RRISK --> RPOS
    JFWD & JEXEC -->|Redis pub/sub| RD
    RDATA -->|SSE| RWEB
    RDATA & JFWD -->|/metrics| PROM --> GRAF
    NGINX --> RWEB & JFWD & GRAF
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 2 — EXTERNAL DATA SOURCES
    # ──────────────────────────────────────────────────────────────
    {
        "title": "External Data Sources",
        "subtitle": "All third-party APIs and data providers feeding FKS",
        "receives": [("Discord webhooks ← Alerts", 15)],
        "sends": [
            ("OHLCV bars → Ruby Data Service", 5),
            ("WebSocket ticks → Kraken feed", 5),
            ("sentiment snapshots → Reddit job", 5),
            ("news scores → News Sentiment", 6),
            ("positions/fills → LiveRiskPublisher", 10),
            ("morning brief → Grok card", 6),
            ("live updates → Dashboard", 14),
            ("WS market data → Janus Forward", 17),
        ],
        "mermaid": """
flowchart TD
    subgraph External["🌐 External Data Sources"]
        A1["MassiveAPI
CME futures OHLCV
src/ruby/src/lib/integrations/massive_client.py"]
        A2["Kraken REST + WebSocket
Crypto spot pairs 24/7
src/ruby/src/lib/integrations/kraken_client.py"]
        A3["Reddit via PRAW + VADER
src/ruby/src/lib/integrations/reddit_watcher.py"]
        A4["Finnhub + Alpha Vantage
src/ruby/src/lib/integrations/news_client.py"]
        A5["Rithmic
Live CME account + order mgmt
src/ruby/src/lib/integrations/rithmic_client.py"]
        A6["Grok / xAI
Macro briefs + live updates
src/ruby/src/lib/integrations/grok_helper.py"]
        A7["Bybit + Binance
Crypto derivatives 24/7
src/janus/crates/bybit-client
src/janus/crates/exchanges"]
    end

    RDATA["→ Ruby Data Service  (p.5)"]:::stub
    NEWS_OUT["→ News Sentiment  (p.6)"]:::stub
    RISK_OUT["→ Live Risk  (p.10)"]:::stub
    WEB_OUT["→ Dashboard  (p.14)"]:::stub
    JANUS_OUT["→ Janus Forward  (p.17)"]:::stub
    ALERTS_IN["← Discord Alerts  (p.15)"]:::stub

    A1 -->|OHLCV bars| RDATA
    A2 -->|REST OHLCV + ticker| RDATA
    A2 -->|WebSocket ticks| RDATA
    A3 -->|sentiment snapshots| RDATA
    A4 -->|news scores| NEWS_OUT
    A5 -->|positions / fills| RISK_OUT
    A6 -->|morning brief| RDATA
    A6 -->|live updates| WEB_OUT
    A7 -->|WS market data| JANUS_OUT
    ALERTS_IN -->|webhooks inbound| A6

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 3 — INFRASTRUCTURE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Shared Infrastructure",
        "subtitle": "Docker containers: Postgres (dual DB), Redis, QuestDB, Qdrant, Nginx",
        "receives": [
            ("read/write ← Ruby Data Service", 5),
            ("read/write ← Janus Forward/Backward", 17),
        ],
        "sends": [
            ("shared state → all services", "all"),
            ("reverse proxy → Nginx", 15),
        ],
        "mermaid": """
flowchart TD
    subgraph Infra["🏗️ Shared Infrastructure"]
        subgraph Databases["Databases"]
            direction LR
            PG["PostgreSQL  :5432
fks_postgres
Databases: janus_db + ruby_db
trades · journal · risk_events
bars · audit · orb_events
src/sql/"]
            RD["Redis  :6379
fks_redis
Namespaced keys
Bar caches · focus assets · daily plan
risk state · Ruby signals · model events
live risk · swing states · Janus pub/sub"]
            QDB["QuestDB  :9000 / :9009
fks_questdb
Time-series market data
ILP ingest line protocol
janus-questdb-writer crate"]
            QDR["Qdrant  :6333 / :6334
fks_qdrant
Vector embeddings
Pattern replay · memory
janus-memory crate"]
        end
        subgraph Networking["Networking & Proxy"]
            NGINX["Nginx  :80 / :443
fks_nginx
SSL termination · reverse proxy
→ web :8080 · janus :7000
→ grafana :3000"]
        end
    end

    RUBY_IN["← Ruby Services  (p.4)"]:::stub
    JANUS_IN["← Janus Services  (p.16)"]:::stub
    MON_OUT["→ Monitoring Stack  (p.15)"]:::stub

    RUBY_IN <-->|ORM + cache| PG & RD
    JANUS_IN <-->|QuestDB + Qdrant + Redis| QDB & QDR & RD
    JANUS_IN -->|DataServiceProvider HTTP| RUBY_IN
    PG & RD & QDB -->|exporters| MON_OUT
    NGINX --> RUBY_IN & JANUS_IN

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 4 — RUBY STACK OVERVIEW
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Ruby Stack Overview (Python)",
        "subtitle": "src/ruby/ — ML models, data pipeline, web dashboard, GPU training",
        "receives": [
            ("OHLCV / ticks / sentiment ← External", 2),
            ("HTTP candle requests ← Janus DataServiceProvider", 17),
        ],
        "sends": [
            ("candles + bars → Janus Forward", 17),
            ("SSE stream → Dashboard", 14),
            ("signals / risk → Alerts", 15),
        ],
        "mermaid": """
flowchart TD
    EXT_IN["← External Data Sources  (p.2)"]:::stub
    JANUS_IN["← Janus DataServiceProvider  (p.17)"]:::stub
    WEB_OUT["→ Dashboard & Alerts  (p.14–15)"]:::stub
    INFRA["↔ Infrastructure  (p.3)"]:::stub

    subgraph Ruby["🐍 Ruby Stack  [src/ruby/]"]
        subgraph DockerSvcs["Docker Services"]
            direction LR
            DATA["📥 data :8000
FastAPI REST + SSE
fks_ruby  (p.5)"]
            ENGINE["⚙️ engine
Scheduler + analysis
fks_engine  (p.6)"]
            WEB["🖥️ web :8080
HTMX dashboard
fks_web  (p.14)"]
            TRAIN["🏋️ trainer :8200
GPU CNN training
fks_trainer  (p.13)"]
            CHART["📉 charting :8003
ApexCharts + nginx
fks_charting  (p.14)"]
        end
        subgraph CoreLibs["Core Libraries  (src/ruby/src/lib/)"]
            direction LR
            CORE["core/
config · cache · models
alerts · logging · db/"]
            IND["indicators/
momentum · trend
volatility · volume"]
            INTEG["integrations/
massive · kraken · rithmic
grok · reddit · pine/"]
            MODEL["model/
deep/ · ml/ · statistical/
ensemble/ · prediction/"]
            ANALYSIS["analysis/
ICT · wave · regime
cvd · volume_profile
signal_quality · sentiment/"]
            TRADING["trading/
strategies/rb/
ruby_signal_engine.py"]
        end
    end

    EXT_IN -->|OHLCV / ticks| DATA
    JANUS_IN -->|HTTP /bars/*| DATA
    DATA <--> INFRA
    ENGINE --> DATA
    WEB --> DATA
    TRAIN --> DATA
    CoreLibs --> DockerSvcs
    DATA & ENGINE -->|signals / risk| WEB_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 5 — RUBY DATA SERVICE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Ruby Data Service",
        "subtitle": "Docker: fks_ruby — DataResolver, FastAPI, Kraken WS, Reddit — single source of truth",
        "receives": [
            ("OHLCV / ticks / sentiment ← External", 2),
            ("HTTP candle requests ← Janus DataServiceProvider", 17),
        ],
        "sends": [
            ("Redis cmds → Scheduler / Engine", 6),
            ("asset specs ↔ Asset Registry", 6),
            ("SSE stream → Dashboard", 14),
            ("/metrics → Monitoring", 15),
            ("candles → Janus Forward (via HTTP)", 17),
        ],
        "mermaid": """
flowchart TD
    EXT_IN["← External Data Sources  (p.2)"]:::stub
    JANUS_IN["← Janus DataServiceProvider  (p.17)"]:::stub
    SCHED_OUT["→ Scheduler / Engine via Redis  (p.6)"]:::stub
    REG_IO["↔ Asset Registry  (p.6)"]:::stub
    WEB_OUT["→ Dashboard SSE  (p.14)"]:::stub
    MON_OUT["→ Monitoring /metrics  (p.15)"]:::stub

    subgraph Data["📥 Data Service  [Docker: fks_ruby :8000]"]
        B["DataResolver
Redis hot → Postgres durable → External fallback
services/data/resolver.py"]
        C["Redis :6379
Bar caches · focus assets · daily plan
risk state · Ruby signals · model events
live risk · swing states"]
        D["Postgres :5432  (ruby_db)
trades · journal · orb_events
risk_events · bars · audit
core/models.py + core/db/"]
        E["FastAPI data service  :8000
services/data/main.py
REST + SSE + API routers
/bars/{symbol}/candles
/bars/symbols · /bars/assets
/bars/gaps · /bars/fill
/bars/live-feed/status"]
        F["Kraken WebSocket feed
start_kraken_feed()
Bars pushed → Redis on bar close
services/data/main.py lifespan"]
        G["Reddit aggregation job
5-min polling loop
get_full_snapshot() → Redis
services/data/main.py"]
    end

    EXT_IN -->|OHLCV bars| B
    EXT_IN -->|WebSocket ticks| F
    EXT_IN -->|sentiment snapshots| G
    JANUS_IN -->|GET /bars/*/candles| E
    B -->|bars_1m / bars_15m / daily| C
    B -->|trades / journal / events| D
    E --> B
    F --> C
    G --> C
    B --> REG_IO
    C -->|Redis commands| SCHED_OUT
    C --> WEB_OUT
    E -->|/metrics :8000| MON_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 6 — ASSET REGISTRY + SCHEDULER (Ruby Engine)
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Ruby Engine: Asset Registry & Scheduler",
        "subtitle": "core/asset_registry.py + services/engine/scheduler.py — pre-market, ORB triggers",
        "receives": [
            ("Redis commands ← Data Service", 5),
            ("asset specs ↔ Data Service", 5),
        ],
        "sends": [
            ("triggers → Pre-Market Pipeline", 7),
            ("triggers → ORB Sessions", 9),
            ("triggers → Ruby Signal Engine", 7),
            ("triggers → Swing Detector", 12),
            ("triggers → Off-Hours Tasks", 13),
        ],
        "mermaid": """
flowchart TD
    DATA_IN["← Data Service / Redis cmds  (p.5)"]:::stub
    PRE_OUT["→ Pre-Market Pipeline  (p.7)"]:::stub
    ORB_OUT["→ ORB Sessions  (p.9)"]:::stub
    RUBY_OUT["→ Ruby Signal Engine  (p.7)"]:::stub
    SWING_OUT["→ Swing Detector  (p.12)"]:::stub
    OFF_OUT["→ Off-Hours Tasks  (p.13)"]:::stub

    subgraph Registry["📋 Asset Registry  (core/asset_registry.py)"]
        H["AssetRegistry
Futures: Metals · Energy · Equity Index
FX · Treasuries · Agriculture
Crypto: BTC · ETH · SOL + more
Micro + Full + Spot variants
Asset.compute_position_size()
Asset.dual_sizing()"]
    end

    subgraph Scheduler["⏰ ScheduleManager  (services/engine/scheduler.py)"]
        I1["EVENING  18:00–00:00 ET
CME · Sydney · Tokyo · Shanghai ORB sessions"]
        I2["PRE_MARKET  00:00–03:00 ET
COMPUTE_DAILY_FOCUS · GROK_MORNING_BRIEF
CHECK_NEWS_SENTIMENT 07:00 ET · PREP_ALERTS"]
        I3["ACTIVE  03:00–12:00 ET
London · LN-NY · US Open ORB
RUBY_RECOMPUTE every 5 min
GROK_LIVE_UPDATE every 15 min
CHECK_RISK_RULES · CHECK_NO_TRADE
CHECK_SWING every 2 min
CHECK_ORB_CME_SETTLE 14:00–15:30 ET
POSITION_CLOSE_WARNING 15:45 ET
EOD_POSITION_CLOSE 16:00 ET"]
        I4["OFF_HOURS  12:00–18:00 ET
HISTORICAL_BACKFILL · RUN_OPTIMIZATION
RUN_BACKTEST · GENERATE_CHART_DATASET
TRAIN_BREAKOUT_CNN · DAILY_REPORT
CHECK_NEWS_SENTIMENT_MIDDAY · NEXT_DAY_PREP"]
    end

    DATA_IN -->|Redis commands| Scheduler
    H -->|asset specs / tickers / sizing| DATA_IN
    Scheduler --> PRE_OUT
    Scheduler --> ORB_OUT
    Scheduler --> RUBY_OUT
    Scheduler --> SWING_OUT
    Scheduler --> OFF_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 7 — PRE-MARKET PIPELINE + RUBY SIGNAL ENGINE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Pre-Market Pipeline & Ruby Signal Engine",
        "subtitle": "Scoring, bias, daily plan, Grok brief + HMA/ORB signal path",
        "receives": [
            ("trigger ← Scheduler", 6),
            ("news scores ← External (Finnhub/AV)", 2),
            ("computed series ← Indicators", 12),
        ],
        "sends": [
            ("focus assets + daily plan → Breakout Core", 8),
            ("swing candidates → Swing Detector", 12),
            ("daily plan → Redis / Dashboard", 14),
            ("RubySignal → Risk Management", 10),
        ],
        "mermaid": """
flowchart TD
    SCHED_IN["← Scheduler trigger  (p.6)"]:::stub
    EXT_IN["← Finnhub + Alpha Vantage  (p.2)"]:::stub
    IND_IN["← Indicator Library  (p.12)"]:::stub
    BCORE_OUT["→ Breakout Core  (p.8)"]:::stub
    SWING_OUT["→ Swing Detector  (p.12)"]:::stub
    RISK_OUT["→ Risk Management  (p.10)"]:::stub
    WEB_OUT["→ Dashboard / Redis  (p.14)"]:::stub

    subgraph PreMarket["🌅 Pre-Market Pipeline  (00:00–03:00 ET)"]
        J["COMPUTE_DAILY_FOCUS
PreMarketScorer: NATR · RVOL · gap
momentum · catalyst scores
analysis/scorer.py"]
        K["DailyBiasAnalyzer + DailyPlanGenerator
trading/strategies/daily/bias_analyzer.py
trading/strategies/daily/daily_plan.py
SwingDetector candidates
trading/strategies/daily/swing_detector.py"]
        L["compute_daily_focus()
ConvictionStack multipliers:
news sentiment · crypto momentum
Grok brief · regime
services/engine/focus.py"]
        M["publish_focus_to_redis()
engine:focus_assets
engine:daily_plan → Redis"]
        N["GROK_MORNING_BRIEF
grok_helper.py
Macro context + daily plan
→ dashboard chat cards"]
        O["CHECK_NEWS_SENTIMENT  07:00 ET
Finnhub + Alpha Vantage + VADER
engine:news_sentiment:[SYM]  2h TTL
analysis/sentiment/news_sentiment.py"]
    end

    subgraph Ruby["💎 Ruby Signal Engine  (services/engine/ruby_signal_engine.py)"]
        RB1["RubySignalEngine
HMA channel + EMA bias · ORB/IB detection
VWAP alignment · ATR14 stop sizing
TP1/TP2/TP3 R-multiples · RSI + squeeze bands"]
        RB2["RubySignal
Compatible with PositionManager
Published → Redis engine:ruby:[SYM]"]
        RB3["handle_ruby_recompute()
Scans focus assets every 5 min
services/engine/handlers.py"]
    end

    SCHED_IN --> J & RB3
    EXT_IN -->|news scores| O
    IND_IN --> RB1
    J --> K --> L --> M
    M --> N --> O
    M -->|focus assets + daily plan| BCORE_OUT
    M -->|swing candidates| SWING_OUT
    M --> WEB_OUT
    RB1 --> RB2 --> RB3
    RB3 -->|RubySignal| RISK_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 8 — BREAKOUT DETECTION CORE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Breakout Detection Core",
        "subtitle": "trading/strategies/rb/ — 13 breakout types, quality filters, CNN inference",
        "receives": [
            ("focus assets + daily plan ← Pre-Market", 7),
            ("bar fetch + symbols ← ORB Sessions", 9),
            ("Kraken crypto data ← Kraken Portfolio", 14),
            ("hot-reload weights ← Training Pipeline", 13),
        ],
        "sends": [
            ("CNN verdict + features → Signal Quality", 9),
            ("breakout results → Postgres", 5),
            ("signal alerts → Alerts", 15),
        ],
        "mermaid": """
flowchart TD
    PRE_IN["← Pre-Market: focus assets + daily plan  (p.7)"]:::stub
    ORB_IN["← ORB Sessions: bar fetch + symbols  (p.9)"]:::stub
    KRAK_IN["← Kraken Portfolio  (p.14)"]:::stub
    TRAIN_IN["← Training: hot-reload model weights  (p.13)"]:::stub
    QUAL_OUT["→ Signal Quality & Confluence  (p.9)"]:::stub
    DB_OUT["→ Postgres: breakout results  (p.5)"]:::stub
    ALERTS_OUT["→ Alerts  (p.15)"]:::stub

    subgraph BreakoutCore["🔍 Breakout Detection  (trading/strategies/rb/)"]
        P["13 BreakoutTypes  (core/breakout_types.py)
ORB · PrevDay · InitialBalance
Consolidation · Weekly · Monthly
Asian · BollingerSqueeze · ValueArea
InsideDay · GapRejection · PivotPoints · Fibonacci"]
        Q["detect_range_breakout()
range_builders.py + breakout.py
detector.py facade · RangeConfig per type"]
        R["run_quality_filters()
NR7 · pre-market range · session window
lunch filter · VWAP confluence · MTF bias
services/engine/handlers.py
analysis/breakout_filters.py"]
        S["build_cnn_tabular_features()
25+ features: ATR trend · RVOL · daily bias
session overlap · crypto momentum · news score
regime · Ruby signal
services/engine/handlers.py"]
        T["HybridBreakoutCNN inference
PyTorch tabular + type/asset embeddings
→ LONG / SHORT / SKIP
analysis/ml/breakout_cnn.py
run_cnn_inference()"]
    end

    PRE_IN --> P
    ORB_IN --> P
    KRAK_IN --> P
    TRAIN_IN -->|model weights| T
    P --> Q --> R --> S --> T
    T -->|CNN verdict + tabular features| QUAL_OUT
    T --> DB_OUT
    T --> ALERTS_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 9 — ORB SESSIONS + SIGNAL QUALITY
    # ──────────────────────────────────────────────────────────────
    {
        "title": "ORB Sessions & Signal Quality",
        "subtitle": "services/engine/ — global session windows + MTF, regime, quality scoring",
        "receives": [
            ("session triggers ← Scheduler", 6),
            ("CNN verdict + features ← Breakout Core", 8),
            ("computed series ← Indicator Library", 12),
        ],
        "sends": [
            ("bar fetch + symbol list → Breakout Core", 8),
            ("enriched signal → No-Trade Guard", 10),
        ],
        "mermaid": """
flowchart TD
    SCHED_IN["← Scheduler session triggers  (p.6)"]:::stub
    BCORE_IN["← Breakout Core: CNN verdict + features  (p.8)"]:::stub
    IND_IN["← Indicator Library: computed series  (p.12)"]:::stub
    BCORE_OUT["→ Breakout Core: handle_orb_check / handle_breakout_check  (p.8)"]:::stub
    NT_OUT["→ No-Trade Guard: enriched signal  (p.10)"]:::stub

    SCHED_IN --> Evening & Morning & USDay & Multi

    subgraph ORB["📡 ORB Session Handlers"]
        subgraph Evening["🌙 Evening (ET)"]
            direction LR
            U1["CME 18:00–20:00"]
            U2["Sydney 18:30–20:30"]
            U3["Tokyo 19:00–21:00"]
            U4["Shanghai 21:00–23:00"]
        end
        subgraph Morning["🌅 Morning (ET)"]
            direction LR
            U5["London 03:00–05:00"]
            U6["LN-NY 08:00–10:00"]
            U7["US Open 09:30–11:00"]
        end
        subgraph USDay["☀️ US / Crypto"]
            direction LR
            U8["CME Settle 14:00–15:30"]
            U9["Crypto UTC0 + UTC12"]
        end
        subgraph Multi["🔄 Multi-Type  every 2 min"]
            U10["PDR · IB · Consolidation + 9 types"]
        end
    end

    subgraph Quality["✅ Signal Quality  (analysis/)"]
        subgraph TS["📈 Price & Regime"]
            direction LR
            V1["MTFAnalyzer
HTF bias + divergence"]
            V2["RegimeFilter
volatility regime
trend strength"]
            V4["CVD + VolumeProfile"]
            V7["SignalQuality
velocity · acceleration"]
        end
        subgraph XM["🌐 Cross-Market"]
            direction LR
            V3["CryptoMomentumScore"]
            V5["ICT: FVG · OB · liquidity"]
            V6["WaveAnalysis: EW"]
            V8["AssetFingerprint"]
        end
    end

    Evening & Morning & USDay & Multi --> BCORE_OUT
    BCORE_IN --> TS & XM
    IND_IN --> V1 & V2 & V4 & V7
    TS & XM -->|enriched signal| NT_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 10 — NO-TRADE GUARD + RISK MANAGEMENT
    # ──────────────────────────────────────────────────────────────
    {
        "title": "No-Trade Guard & Risk Management",
        "subtitle": "services/engine/patterns.py + risk.py + live_risk.py",
        "receives": [
            ("enriched signal ← Signal Quality", 9),
            ("RubySignal ← Ruby Engine", 7),
            ("swing signal ← Swing Detector", 12),
            ("positions/fills ← Rithmic / External", 2),
        ],
        "sends": [
            ("can_enter=True → Position Manager", 11),
            ("live_risk state → Redis", 5),
            ("risk events → Alerts", 15),
            ("no-trade alerts → Alerts", 15),
        ],
        "mermaid": """
flowchart TD
    QUAL_IN["← Signal Quality: enriched signal  (p.9)"]:::stub
    RUBY_IN["← Ruby Signal Engine: RubySignal  (p.7)"]:::stub
    SWING_IN["← Swing Detector: swing signal  (p.12)"]:::stub
    EXT_IN["← Rithmic: positions / fills  (p.2)"]:::stub
    POS_OUT["→ Position Manager: can_enter=True  (p.11)"]:::stub
    REDIS_OUT["→ Redis: live_risk state  (p.5)"]:::stub
    ALERTS_OUT["→ Alerts  (p.15)"]:::stub

    subgraph NoTrade["🚫 No-Trade Guard  (services/engine/patterns.py)"]
        NT["evaluate_no_trade()
NoTradeConditions:
• low market data quality
• extreme volatility
• daily loss limit hit
• consecutive loss limit
• late session / no setups
• session ended
publish_no_trade_alert() → Redis"]
    end

    subgraph Risk["🛡️ Risk Management  (services/engine/risk.py + live_risk.py)"]
        W["RiskManager.can_enter_trade()
Daily P&L gate
Consecutive loss limit
Open position cap
Overnight risk check
services/engine/risk.py"]
        X["LiveRiskState
Per-asset position snapshots
Dynamic sizing · Health score
compute_live_risk()
services/engine/live_risk.py"]
        Y["LiveRiskPublisher
Ticks every 5s
Publishes → Redis engine:live_risk
_load_rithmic_positions()"]
    end

    QUAL_IN -->|enriched signal| NT
    NT -->|no active block| W
    RUBY_IN -->|RubySignal| W
    SWING_IN -->|swing signal| W
    EXT_IN -->|positions / fills| Y
    W -->|can_enter=True| POS_OUT
    W --> X --> Y
    Y -->|live_risk state| REDIS_OUT
    Y -->|risk events| ALERTS_OUT
    NT -->|no-trade alerts| ALERTS_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 11 — POSITION & ORDER MANAGEMENT (Ruby)
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Ruby Position & Order Management",
        "subtitle": "services/engine/position_manager.py + copy_trader.py + rithmic_client.py",
        "receives": [("can_enter=True ← Risk Management", 10)],
        "sends": [
            ("positions + P&L + OrderCommands → Redis", 5),
        ],
        "mermaid": """
flowchart TD
    RISK_IN["← Risk Management: can_enter=True  (p.10)"]:::stub
    REDIS_OUT["→ Redis: positions + PnL + OrderCommands  (p.5)"]:::stub

    subgraph Positions["📈 Position & Order Management  (Ruby)"]
        Z["PositionManager.process_signal()
MicroPosition state machine
BracketPhase:
  ENTRY → TP1 → BE → TRAIL → TP3
SAR always-in reversal logic
Pyramid scaling via get_next_pyramid_level()
services/engine/position_manager.py"]
        AA["3-Phase Bracket
TP1 → move stop to BE
EMA9 trailing stop → TP3
_update_bracket_phase()
_check_stop_hit() / _check_tp3_hit()"]
        AB["CopyTrader.execute_order_commands()
Rithmic multi-account copy
Compliance checklist + RollingRateCounter
services/engine/copy_trader.py"]
        AC["RithmicAccountManager
Order placement on prop accounts
resolve_front_month()
EOD hard close 16:00 ET
integrations/rithmic_client.py"]
    end

    RISK_IN -->|can_enter=True| Z
    Z --> AA --> AB --> AC
    Z -->|positions + PnL + OrderCommands| REDIS_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 12 — INDICATORS, MODELS & SWING
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Indicators, Models & Swing Detector",
        "subtitle": "indicators/ + model/ + swing.py — computed series, ML models, swing trades",
        "receives": [
            ("trigger every 2 min ← Scheduler", 6),
            ("swing candidates ← Pre-Market", 7),
        ],
        "sends": [
            ("computed series → Signal Quality", 9),
            ("ATR/VWAP/EMA/squeeze → Ruby Engine", 7),
            ("deep/ml/statistical models → Training", 13),
            ("swing signal → Risk Management", 10),
        ],
        "mermaid": """
flowchart TD
    SCHED_IN["← Scheduler triggers  (p.6)"]:::stub
    PRE_IN["← Pre-Market: swing candidates  (p.7)"]:::stub
    QUAL_OUT["→ Signal Quality  (p.9)"]:::stub
    RUBY_OUT["→ Ruby Signal Engine  (p.7)"]:::stub
    TRAIN_OUT["→ Training Pipeline  (p.13)"]:::stub
    RISK_OUT["→ Risk Management  (p.10)"]:::stub

    subgraph Indicators["📐 Indicator Library  (indicators/)"]
        IND1["IndicatorManager + Registry
indicators/manager.py · registry.py · factory.py"]
        subgraph IndTypes["Indicator Types"]
            direction LR
            IND2["Trend: EMA · HMA · VWAP
Momentum: RSI · MACD"]
            IND3["Volume: OBV · CVD
Other: ATR · BB · KC"]
            IND4["CandlePatterns
AreasOfInterest
MarketTiming"]
        end
    end

    subgraph Models["🧠 Model Layer  (model/)"]
        MOD1["ModelService + ModelRegistry
model/service.py · registry.py · factory.py"]
        subgraph ModTypes["Model Types"]
            direction LR
            MOD2["Deep: CNN · LSTM
Transformer · TFT · NN"]
            MOD3["ML: XGBoost · LightGBM
CatBoost · Logistic"]
            MOD4["Statistical: ARIMA
GARCH · HMM · Prophet
Ensemble"]
        end
    end

    subgraph Swing["📊 Swing Detector  (services/engine/swing.py)"]
        AD["CHECK_SWING  every 2 min  03:00–15:30 ET
tick_swing_detector()
SwingState: PENDING → ACTIVE → CLOSED"]
        AE["Entry: Pullback · Breakout · Gap
15m + 5m bar fetch
Dashboard: accept / ignore / close / BE"]
    end

    IND1 --> IndTypes
    MOD1 --> ModTypes
    SCHED_IN --> AD
    PRE_IN -->|swing candidates| AD
    AD --> AE -->|swing signal| RISK_OUT
    IND1 -->|computed series| QUAL_OUT
    IND1 -->|ATR · VWAP · EMA · squeeze| RUBY_OUT
    MOD1 -->|deep / ml / statistical models| TRAIN_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 13 — TRAINING PIPELINE + OFF-HOURS
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Training Pipeline & Off-Hours Tasks",
        "subtitle": "Docker: fks_trainer — CNN train, backfill, optimization, backtest, daily report",
        "receives": [
            ("triggers ← Scheduler", 6),
            ("deep/ml models ← Model Layer", 12),
        ],
        "sends": [
            ("hot-reload model weights → Breakout Core", 8),
            ("daily report → Alerts", 15),
            ("/metrics → Monitoring", 15),
        ],
        "mermaid": """
flowchart TD
    SCHED_IN["← Scheduler OFF_HOURS triggers  (p.6)"]:::stub
    MOD_IN["← Model Layer: deep/ml/statistical models  (p.12)"]:::stub
    BCORE_OUT["→ Breakout Core: hot-reload model weights  (p.8)"]:::stub
    ALERTS_OUT["→ Alerts: daily report  (p.15)"]:::stub
    MON_OUT["→ Monitoring /metrics :8200  (p.15)"]:::stub

    subgraph Training["🏋️ Training Pipeline  [Docker: fks_trainer :8200]"]
        AF["OFF_HOURS triggers
GENERATE_CHART_DATASET → DatasetGenerator
RBSimulator
services/training/rb_simulator.py"]
        AG["dataset_generator.py
365-day lookback · 13 breakout types × all assets
_build_row() 25+ features
split_dataset() + validate_dataset()"]
        AH["TRAIN_BREAKOUT_CNN
HybridBreakoutCNN
PyTorch + Optuna walk-forward
train_model() + evaluate_model()
analysis/ml/breakout_cnn.py"]
        AI["Champion promotion
breakout_cnn_best.pt
breakout_cnn_best_meta.json
feature_contract.json → models/"]
        AJ["ModelWatcher hot-reload
watchdog inotify / polling fallback
invalidate_model_cache()
model_reloaded → Redis
services/engine/model_watcher.py"]
    end

    subgraph OffHours["⚙️ Off-Hours  (12:00–18:00 ET)"]
        subgraph DataPrep["Data & Optimization"]
            direction LR
            AK["HISTORICAL_BACKFILL
run_backfill()
Warms Redis + Postgres
MassiveAPI / Kraken / yfinance"]
            AL["RUN_OPTIMIZATION
Optuna nightly study
walk-forward 30–90 days"]
            AM["RUN_BACKTEST
P&L + win-rate stats"]
        end
        subgraph EOD["End-of-Day"]
            direction LR
            AN["DAILY_REPORT
P&L · trades · signals
Grok review → email + Discord"]
            AO["POSITION_CLOSE_WARNING 15:45 ET
EOD_POSITION_CLOSE 16:00 ET
Rithmic cancel_all + exit_all"]
        end
    end

    SCHED_IN --> AF & DataPrep & EOD
    MOD_IN --> AF
    AF --> AG --> AH --> AI --> AJ
    AJ -->|hot-reload weights| BCORE_OUT
    AH -->|/metrics :8200| MON_OUT
    AN -->|daily report| ALERTS_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 14 — DASHBOARD, CHARTING, PINE SCRIPT, KRAKEN
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Dashboard, Charting & Kraken Portfolio",
        "subtitle": "Docker: fks_web :8080 + fks_charting :8003 + Kraken 24/7 + Pine Script",
        "receives": [
            ("Redis SSE stream ← Data Service", 5),
            ("Grok live updates ← External", 2),
        ],
        "sends": [
            ("crypto data → Breakout Core", 8),
        ],
        "mermaid": """
flowchart TD
    REDIS_IN["← Redis SSE / Data Service  (p.5)"]:::stub
    BCORE_OUT["→ Breakout Core: crypto ORB  (p.8)"]:::stub

    subgraph Web["🖥️ Web / Dashboard  [Docker: fks_web :8080]"]
        AS["FastAPI web proxy  :8080
HTMX + SSE dashboard"]
        subgraph LiveOps["📊 Live Operations"]
            direction LR
            AT["Live Risk strip · P&L"]
            AU["Focus cards · Swing"]
            AW["Ruby signal panel"]
        end
        subgraph AI["🤖 AI & Models"]
            direction LR
            AV["Grok chat + review"]
            AX["CNN panel · Trainer log"]
        end
        subgraph Records["📋 Records & Config"]
            direction LR
            AY["Journal + audit"]
            AZ2["Settings · Tasks"]
        end
        subgraph TCtrl["⚙️ Trading Controls"]
            direction LR
            BB2["Copy trade panel"]
            BC2["Trading settings
Test Rithmic/Massive/Kraken"]
        end
    end

    subgraph Charting["📉 Charting  [Docker: fks_charting :8003]"]
        CH["ApexCharts + nginx
OHLCV candle charts"]
    end

    subgraph Pine["🌲 Pine Script  (integrations/pine/)"]
        PI["PineScriptGenerator
params.yaml → TradingView modules
/pine/* API"]
    end

    subgraph Kraken["💰 Kraken 24/7"]
        AP["KrakenDataProvider
REST OHLCV + portfolio"]
        AQ["Kraken WebSocket feed
Real-time OHLC + trades"]
        AR["Crypto ORB sessions
UTC0 + UTC12
Same 13-type pipeline"]
    end

    REDIS_IN --> AS
    AS --> LiveOps & AI & Records & TCtrl
    AS -->|proxied /charts/*| CH
    AS -->|proxied /pine/*| PI
    AP --> AQ --> AR -->|crypto data| BCORE_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 15 — ALERTS + MONITORING
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Alerts & Monitoring",
        "subtitle": "core/alerts.py · Docker: fks_prometheus + fks_grafana + fks_alertmanager",
        "receives": [
            ("signal alerts ← Breakout Core", 8),
            ("daily report ← Off-Hours", 13),
            ("risk events ← Risk Management", 10),
            ("no-trade alerts ← No-Trade Guard", 10),
            ("/metrics ← Data Service :8000", 5),
            ("/metrics ← Trainer Service :8200", 13),
            ("/metrics ← Janus :7000", 17),
            ("/metrics ← CNS :9090", 21),
        ],
        "sends": [("Discord webhooks → External", 2)],
        "mermaid": """
flowchart TD
    BCORE_IN["← Breakout Core: signal alerts  (p.8)"]:::stub
    OFF_IN["← Off-Hours: daily report  (p.13)"]:::stub
    RISK_IN["← Risk Mgmt: risk events  (p.10)"]:::stub
    NT_IN["← No-Trade Guard: alerts  (p.10)"]:::stub
    RDATA_IN["← Data Svc /metrics :8000  (p.5)"]:::stub
    TRAIN_IN["← Trainer /metrics :8200  (p.13)"]:::stub
    JANUS_IN["← Janus /metrics :7000  (p.17)"]:::stub
    CNS_IN["← CNS /metrics :9090  (p.21)"]:::stub
    EXT_OUT["→ External: Discord webhooks  (p.2)"]:::stub

    subgraph Alerts["🔔 Alerts  (core/alerts.py)"]
        AZ["Discord smart gate
Master toggle · Focus-only filter
Live breakout events · No-trade alerts
Gap alerts + daily report · Risk events"]
        AMGR["Alertmanager
fks_alertmanager :9093
Routes to Discord bridge
infrastructure/monitoring/alertmanager/"]
    end

    subgraph Monitoring["📈 Monitoring Stack"]
        BA["Prometheus  :9090
fks_prometheus
Scrapes: data · engine · trainer
janus · CNS · exporters"]
        BB["Grafana  :3000
fks_grafana
Dashboards: P&L · signal quality
CNN accuracy · risk · system health"]
        LOKI["Loki + Promtail
fks_loki · fks_promtail
Centralized log aggregation"]
        JAEGER["Jaeger  :16686
fks_jaeger
Distributed tracing"]
        subgraph Exporters["Exporters"]
            direction LR
            PGE["postgres-exporter :9187"]
            RDE["redis-exporter :9121"]
            QDE["questdb-exporter"]
        end
    end

    BCORE_IN -->|signal alerts| AZ
    OFF_IN -->|daily report| AZ
    RISK_IN -->|risk events| AZ
    NT_IN -->|no-trade alerts| AZ
    AZ -->|Discord webhooks| EXT_OUT
    AZ --> AMGR --> EXT_OUT

    RDATA_IN --> BA
    TRAIN_IN --> BA
    JANUS_IN --> BA
    CNS_IN --> BA
    Exporters --> BA
    BA --> BB
    LOKI --> BB

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 16 — JANUS STACK OVERVIEW
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Janus Stack Overview (Rust)",
        "subtitle": "src/janus/ — Brain-inspired neuro-symbolic trading engine",
        "receives": [
            ("candles via HTTP ← Ruby Data Service", 5),
            ("WS market data ← External (Bybit/Binance)", 2),
        ],
        "sends": [
            ("signals → Execution", 19),
            ("state → Redis pub/sub → Ruby", 5),
            ("/metrics → Monitoring", 15),
        ],
        "mermaid": """
flowchart TD
    RDATA_IN["← Ruby Data Service HTTP  (p.5)"]:::stub
    EXT_IN["← External: Bybit / Binance WS  (p.2)"]:::stub
    INFRA["↔ Infrastructure  (p.3)"]:::stub
    MON_OUT["→ Monitoring  (p.15)"]:::stub

    subgraph Janus["🦀 Janus Stack  [src/janus/]"]
        subgraph Services["Services  (services/)"]
            direction LR
            FWD["⚡ Forward :7000
janus-forward
Live signal generation
Real-time indicators
Execution embedded  (p.17)"]
            BWD["💤 Backward
janus-backward
Memory consolidation
Persistence + analytics  (p.18)"]
            EXEC["🎯 Execution
janus-execution
Order mgmt · sim/paper/live
Multi-exchange  (p.19)"]
            DATA["📡 Data
janus-data
DataServiceProvider
PythonDataClient
Gap detection"]
            CNS["🏥 CNS
Health monitoring
Circuit breakers
Auto-recovery  (p.21)"]
            OPT["🎯 Optimizer
Walk-forward
Optuna
janus-optimizer"]
        end
        subgraph Crates["Crates  (crates/)"]
            direction LR
            IND["janus-indicators
EMA · RSI · ATR
Bollinger · HMA"]
            STRAT["janus-strategies
Strategy impls"]
            RISK["janus-risk
Position limits
Drawdown protection"]
            MODELS["janus-models
Model types + traits"]
            DSP["janus-dsp
Signal processing
Fractal · FRAMA"]
            ML["janus-ml
ONNX inference
Candle (Rust ML)"]
            MEM["janus-memory
Qdrant vectors
Pattern replay"]
            LTN["janus-ltn
Logic Tensor Network
Neuro-symbolic"]
        end
        subgraph Brain["Neuromorphic  (neuromorphic/)  (p.20)"]
            direction LR
            AMYG["Amygdala
Fear · Kill switch"]
            HIPP["Hippocampus
Memory replay"]
            PFC["Prefrontal
Decision making"]
            THAL["Thalamus
Signal routing"]
        end
    end

    EXT_IN -->|WS market data| FWD
    RDATA_IN -->|HTTP /bars/*| DATA --> FWD
    FWD <-->|regime + state| BWD
    FWD --> EXEC
    Brain --> FWD
    CNS --> FWD & BWD & EXEC
    Crates --> Services
    Services <--> INFRA
    FWD & CNS -->|/metrics| MON_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 17 — JANUS FORWARD SERVICE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Janus Forward Service (Wake State)",
        "subtitle": "services/forward/ — low-latency live signal generation, indicator pipeline, execution",
        "receives": [
            ("candles ← DataServiceProvider → Ruby Data", 5),
            ("WS ticks ← Bybit/Binance", 2),
            ("neuromorphic outputs ← Brain regions", 20),
            ("optimized params ← Backward", 18),
        ],
        "sends": [
            ("signals → Execution", 19),
            ("state + bars → Backward (persistence)", 18),
            ("/metrics → Monitoring", 15),
        ],
        "mermaid": """
flowchart TD
    DATA_IN["← DataServiceProvider / Ruby  (p.5)"]:::stub
    WS_IN["← Bybit / Binance WebSocket  (p.2)"]:::stub
    BRAIN_IN["← Neuromorphic Brain  (p.20)"]:::stub
    BWD_IN["← Backward: optimized params  (p.18)"]:::stub
    EXEC_OUT["→ Execution Service  (p.19)"]:::stub
    BWD_OUT["→ Backward: state + bars  (p.18)"]:::stub
    MON_OUT["→ Monitoring /metrics  (p.15)"]:::stub

    subgraph Forward["⚡ Janus Forward  [fks_janus :7000 HTTP / :9051 gRPC]"]
        MAIN["main.rs
Tokio runtime
HTTP :7000 + gRPC :9051"]
        subgraph EventLoop["🔄 Event Loop"]
            EL["event_loop.rs
Tick processing pipeline
Sub-ms indicator updates"]
            FEAT["features.rs
Feature extraction
DiffGAF image generation"]
            INF["inference.rs
ONNX / Candle model inference
Signal classification"]
        end
        subgraph BrainRT["🧠 Brain Runtime"]
            BW["brain_wiring.rs
Neuromorphic module wiring"]
            BR["brain_runtime.rs
Brain region orchestration"]
            REG["regime.rs + regime_bridge.rs
Market regime detection
HMM state transitions"]
        end
        subgraph SubSystems["Sub-systems"]
            direction LR
            STRAT["strategies/
Strategy implementations
Regime-aware selection"]
            SIG["signal/
Signal generation
Confidence scoring"]
            RISK["risk/
Position limits
Circuit breakers"]
            PERS["persistence/
QuestDB writer
State snapshots"]
        end
        subgraph Connectivity["Connectivity"]
            direction LR
            WS["websocket/
Exchange WS feeds
Book + trade streams"]
            API["api/
REST endpoints
/health · /signals · /status"]
            SHM["shm.rs
Shared memory IPC
Arrow zero-copy to Backward"]
            PREL["param_reload/
Hot-reload config
Walk-forward params"]
        end
    end

    WS_IN --> WS --> EL
    DATA_IN --> EL
    BRAIN_IN --> BR --> EL
    BWD_IN --> PREL
    EL --> FEAT --> INF --> SIG --> STRAT --> RISK
    RISK -->|signals| EXEC_OUT
    PERS -->|state + bars| BWD_OUT
    API -->|/metrics| MON_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 18 — JANUS BACKWARD SERVICE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Janus Backward Service (Sleep State)",
        "subtitle": "services/backward/ — memory consolidation, persistence, analytics, training jobs",
        "receives": [
            ("state + bars ← Forward (Arrow IPC)", 17),
        ],
        "sends": [
            ("optimized params → Forward (hot-reload)", 17),
            ("training metrics → Monitoring", 15),
        ],
        "mermaid": """
flowchart TD
    FWD_IN["← Forward: state + bars via Arrow IPC  (p.17)"]:::stub
    FWD_OUT["→ Forward: optimized params  (p.17)"]:::stub
    MON_OUT["→ Monitoring  (p.15)"]:::stub

    subgraph Backward["💤 Janus Backward Service  (Sleep State)"]
        MAIN["main.rs
Tokio runtime
Apalis job queue worker"]
        subgraph Persistence["💾 Persistence"]
            direction LR
            PERS["persistence/
QuestDB writes
Signal + trade archival
Historical bar storage"]
            MIG["migrations/
Schema versioning
janus_db tables"]
        end
        subgraph Tasks["📋 Job Queue"]
            direction LR
            TASK1["Consolidation
Pattern replay
Memory optimization"]
            TASK2["Analytics
Win-rate computation
Strategy evaluation"]
            TASK3["Training
Walk-forward optimization
Param tuning
janus-training crate"]
        end
        subgraph Worker["⚙️ Worker"]
            SCHED["sched.rs
Apalis scheduler
Periodic + on-demand jobs"]
            WORK["worker.rs
Job handlers
Error recovery"]
            HTTP["http.rs
Status API
Job monitoring"]
        end
    end

    FWD_IN -->|Arrow IPC / shared memory| Persistence
    Persistence --> Tasks
    SCHED --> WORK --> Tasks
    Tasks -->|optimized params| FWD_OUT
    HTTP -->|/metrics| MON_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 19 — JANUS EXECUTION SERVICE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Janus Execution Service",
        "subtitle": "services/execution/ — multi-exchange order mgmt, sim/paper/live modes, gRPC",
        "receives": [
            ("signals ← Forward Service", 17),
        ],
        "sends": [
            ("fills + positions → QuestDB / Postgres", 3),
            ("order events → Monitoring", 15),
        ],
        "mermaid": """
flowchart TD
    FWD_IN["← Forward: trading signals via gRPC  (p.17)"]:::stub
    DB_OUT["→ QuestDB / Postgres: fills + positions  (p.3)"]:::stub
    MON_OUT["→ Monitoring: order events  (p.15)"]:::stub

    subgraph Execution["🎯 Execution Service  (services/execution/)"]
        MAIN["main.rs
Tokio runtime · gRPC server
Embedded in Janus Forward binary"]
        subgraph API["🔌 API Layer"]
            direction LR
            GRPC["gRPC handlers
Signal → Order conversion
Health + metrics endpoints"]
            STATE["state_broadcaster.rs
Real-time position updates
SSE / WebSocket broadcast"]
        end
        subgraph OrderMgmt["📋 Order Management"]
            direction LR
            ORDERS["orders/
Order placement
Cancellation · Status tracking
Rate limiting"]
            POS["positions/
Open position tracking
Real-time P&L calculation
Account margin / exposure"]
        end
        subgraph ExecEngine["⚡ Execution Engine"]
            direction LR
            EXEC["execution/
Order routing
Retry logic
Failover handling"]
            KSG["kill_switch_guard.rs
Emergency kill switch
Circuit breaker integration"]
        end
        subgraph Exchanges["🏦 Exchange Adapters"]
            direction LR
            BYBIT["Bybit V5
Spot + derivatives"]
            BINANCE["Binance
Spot + futures"]
            SIM["Simulation Engine
Internal matching
Configurable slippage
Instant / realistic fills"]
        end
        subgraph Strategies["📊 Execution Strategies"]
            direction LR
            STRAT["strategies/
TWAP · VWAP · Iceberg
Sniper · Adaptive"]
        end
    end

    FWD_IN -->|gRPC signals| GRPC
    GRPC --> ORDERS --> EXEC
    EXEC --> Exchanges
    EXEC --> KSG
    Exchanges --> POS --> STATE
    POS --> DB_OUT
    STATE --> MON_OUT

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 20 — NEUROMORPHIC BRAIN ARCHITECTURE
    # ──────────────────────────────────────────────────────────────
    {
        "title": "Neuromorphic Brain Architecture",
        "subtitle": "src/janus/neuromorphic/ — brain-region inspired modules with clear I/O contracts",
        "receives": [
            ("market data + indicators ← Forward event loop", 17),
        ],
        "sends": [
            ("decisions + risk gates → Forward pipeline", 17),
        ],
        "mermaid": """
flowchart TD
    FWD_IN["← Forward: market data + indicators  (p.17)"]:::stub
    FWD_OUT["→ Forward: decisions + risk gates  (p.17)"]:::stub

    subgraph Brain["🧠 Neuromorphic Architecture  (src/janus/neuromorphic/)"]
        subgraph Sensory["👁️ Sensory Input"]
            direction LR
            THAL["Thalamus  (thalamus/)
TRN gating · Signal routing
Attention filtering
Multi-source arbitration"]
            VIS["Visual Cortex  (visual_cortex/)
GAF image processing
DiffGAF-LSTM vision
Pattern recognition"]
        end
        subgraph Executive["🎯 Executive & Planning"]
            direction LR
            PFC["Prefrontal Cortex  (prefrontal/)
Decision making
Strategy selection
Meta-cognition"]
            HIPP["Hippocampus  (hippocampus/)
Memory consolidation
Pattern replay
Qdrant vector recall
Episodic memory"]
        end
        subgraph Action["⚡ Action & Regulation"]
            direction LR
            BG["Basal Ganglia  (basal_ganglia/)
Action selection
Reward learning
Go/No-Go gating"]
            CERE["Cerebellum  (cerebellum/)
Precision timing
Coordination
Error correction"]
        end
        subgraph Safety["🛡️ Safety & Homeostasis"]
            direction LR
            AMYG["Amygdala  (amygdala/)
Fear response
Circuit breakers
Kill switch
Drawdown detection"]
            HYPO["Hypothalamus  (hypothalamus/)
Homeostasis
Resource management
Capital allocation
Position sizing"]
        end
        subgraph Infra["🔧 Infrastructure"]
            direction LR
            DIST["Distributed  (distributed/)
Multi-node coordination
gRPC inter-region comms"]
            GPU["GPU  (gpu/)
CUDA acceleration
Batch inference"]
            INTEG["Integration  (integration/)
Region wiring
Pipeline orchestration"]
        end
    end

    FWD_IN --> THAL & VIS
    THAL --> PFC & HIPP
    VIS --> PFC
    HIPP --> PFC
    PFC --> BG --> CERE
    AMYG --> BG
    HYPO --> BG
    CERE --> FWD_OUT
    INTEG --> Sensory & Executive & Action & Safety
    GPU --> VIS & PFC

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
    # ──────────────────────────────────────────────────────────────
    #  PAGE 21 — CNS + JANUS CRATES DETAIL
    # ──────────────────────────────────────────────────────────────
    {
        "title": "CNS Health & Janus Crate Map",
        "subtitle": "crates/cns/ + all shared crates — monitoring backbone + library ecosystem",
        "receives": [
            ("health probes ← all Janus services", 16),
        ],
        "sends": [
            ("/metrics → Prometheus", 15),
            ("circuit breaker state → Forward", 17),
            ("auto-recovery actions → services", 16),
        ],
        "mermaid": """
flowchart TD
    JANUS_IN["← All Janus Services  (p.16)"]:::stub
    MON_OUT["→ Prometheus /metrics  (p.15)"]:::stub
    FWD_OUT["→ Forward: circuit breakers  (p.17)"]:::stub

    subgraph CNS["🏥 CNS — Central Nervous System  (crates/cns/)"]
        BRAIN["Brain coordinator
Orchestrates health checks
34+ Prometheus metrics"]
        PROBES["Probes — Sensory neurons
Service health detection
Latency tracking
Response time percentiles"]
        REFLEXES["Reflexes — Auto-recovery
Circuit breakers
Service restart
Graceful degradation"]
        METRICS["Metrics
janus_cns_system_health_score
janus_cns_system_status
janus_forward_orders_*
janus_backward_training_*"]
    end

    subgraph CrateMap["📦 Janus Crate Ecosystem"]
        subgraph Core["Core Libraries"]
            direction LR
            JCORE["janus-core
Types · config · signal bus"]
            JAPI["janus-api
HTTP handlers + routes"]
            JCOMMON["janus-common
Shared primitives"]
        end
        subgraph Trading["Trading"]
            direction LR
            JIND["janus-indicators
EMA · RSI · ATR · BB
HMA · VWAP · MACD"]
            JSTRAT["janus-strategies
Strategy impls"]
            JRISK["janus-risk
Position limits
Drawdown protection"]
            JBT["janus-backtest
Temporal Fortress
Zero-lookahead"]
            JOPT["janus-optimizer
Walk-forward
Optuna bridge"]
        end
        subgraph InfraC["Infrastructure"]
            direction LR
            JDATA["janus-data
DataServiceProvider
PythonDataClient"]
            JEXCH["janus-exchanges
Exchange abstraction"]
            JBY["janus-bybit-client
Bybit V5 API"]
            JQDB["janus-questdb-writer
Time-series writer"]
            JMEM["janus-memory
Qdrant vectors"]
            JRL["janus-rate-limiter"]
        end
        subgraph AI["AI / ML"]
            direction LR
            JDSP["janus-dsp
Fractal · FRAMA
Ehlers filters"]
            JLTN["janus-ltn
Logic Tensor Network"]
            JML["janus-ml
ONNX + Candle"]
            JMOD["janus-models
Model registry"]
            JREG["janus-regime
HMM regime detection"]
            JGAP["janus-gap-detection"]
        end
    end

    JANUS_IN --> PROBES --> BRAIN
    BRAIN --> REFLEXES --> FWD_OUT
    BRAIN --> METRICS --> MON_OUT
    Core --> Trading & InfraC & AI

    classDef stub fill:#e8e8e8,stroke:#aaa,stroke-dasharray:5 5,color:#555,font-style:italic
""",
    },
]

# =============================================================================
# HTML TEMPLATE
# =============================================================================

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>FKS Trading System — Printable Architecture Pages</title>
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  /* ── Base ─────────────────────────────────────────────────── */
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #fff; }}

  /* ── Print page setup ─────────────────────────────────────── */
  @page {{ size: letter landscape; margin: 0.35in 0.35in; }}

  /* ── Screen preview ──────────────────────────────────────── */
  .page {{
    width: 10.3in;
    height: 7.6in;          /* fixed — matches printable landscape height */
    margin: 0.25in auto;
    padding: 0.15in 0.25in 0.1in;
    border: 1px solid #ccc;
    box-shadow: 0 2px 8px rgba(0,0,0,.15);
    page-break-after: always;
    break-after: page;
    background: #fff;
    display: flex;
    flex-direction: column;
  }}
  .page:last-child {{ page-break-after: avoid; break-after: avoid; }}

  /* ── Page header ─────────────────────────────────────────── */
  .page-header {{
    flex-shrink: 0;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    border-bottom: 2px solid #1a3a5c;
    padding-bottom: 0.06in;
    margin-bottom: 0.07in;
  }}
  .page-header h1 {{
    font-size: 13pt;
    color: #1a3a5c;
    font-weight: 700;
    line-height: 1.2;
  }}
  .page-header .subtitle {{
    font-size: 7.5pt;
    color: #555;
    margin-top: 1px;
    font-style: italic;
  }}
  .page-num {{
    font-size: 8.5pt;
    color: #888;
    text-align: right;
    white-space: nowrap;
    padding-top: 2px;
    min-width: 55px;
  }}

  /* ── Diagram area ─────────────────────────────────────────────
     flex:1 makes this fill all space between header and footer.
     We let the SVG grow to fill height — so tall-narrow diagrams
     use vertical space instead of being squished to fit width.
  ──────────────────────────────────────────────────────────── */
  .diagram {{
    flex: 1;
    min-height: 0;          /* critical: allows flex child to shrink */
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }}
  .diagram .mermaid {{
    /* fill the full diagram area height */
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .diagram .mermaid svg {{
    /* scale to fill height; only shrink width if needed */
    max-height: 100% !important;
    max-width: 100% !important;
    height: auto !important;
    width: auto !important;
    display: block;
  }}

  /* ── Page footer ─────────────────────────────────────────── */
  .page-footer {{
    flex-shrink: 0;
    border-top: 1px solid #ddd;
    padding-top: 0.05in;
    margin-top: 0.06in;
    display: flex;
    gap: 0.15in;
    font-size: 7pt;
    color: #444;
    flex-wrap: wrap;
  }}
  .page-footer .col {{ flex: 1; min-width: 2in; }}
  .page-footer strong {{ color: #1a3a5c; }}
  .page-footer ul {{ list-style: none; padding: 0; margin: 1px 0 0 0; }}
  .page-footer ul li::before {{ content: "→ "; color: #888; }}
  .page-footer ul.receives li::before {{ content: "← "; color: #888; }}
  .page-footer .none {{ color: #aaa; font-style: italic; }}
</style>
</head>
<body>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    theme: 'neutral',
    flowchart: {{ htmlLabels: true, curve: 'basis', rankSpacing: 40, nodeSpacing: 30 }},
    fontSize: 11,
    securityLevel: 'loose',
  }});
</script>

{pages}

</body>
</html>
"""

PAGE_TEMPLATE = """
<div class="page">
  <div class="page-header">
    <div>
      <h1>{icon_title}</h1>
      <div class="subtitle">{subtitle}</div>
    </div>
    <div class="page-num">Page {page_num} / {total_pages}</div>
  </div>

  <div class="diagram">
    <div class="mermaid">
{mermaid}
    </div>
  </div>

  <div class="page-footer">
    <div class="col">
      <strong>Receives from:</strong>
      {receives_html}
    </div>
    <div class="col">
      <strong>Sends to:</strong>
      {sends_html}
    </div>
  </div>
</div>
"""


def build_connection_list(items: list, css_class: str) -> str:
    if not items:
        return '<span class="none">none</span>'
    lis = "\n".join(f'        <li>{label}  <em style="color:#1a3a5c">(p.{page})</em></li>' for label, page in items)
    return f'<ul class="{css_class}">\n{lis}\n      </ul>'


def generate_html() -> str:
    total = len(SECTIONS)
    pages_html = []

    for idx, section in enumerate(SECTIONS):
        page_num = idx + 1
        receives_html = build_connection_list(section["receives"], "receives")
        sends_html = build_connection_list(section["sends"], "sends")

        page_html = PAGE_TEMPLATE.format(
            icon_title=section["title"],
            subtitle=section["subtitle"],
            page_num=page_num,
            total_pages=total,
            mermaid=section["mermaid"].strip(),
            receives_html=receives_html,
            sends_html=sends_html,
        )
        pages_html.append(page_html)

    return HTML_TEMPLATE.format(pages="\n".join(pages_html))


def main() -> None:
    output_dir = Path(__file__).resolve().parents[1] / "docs"
    output_dir.mkdir(exist_ok=True)

    out_path = output_dir / "fks_system_printable.html"
    html = generate_html()
    out_path.write_text(html, encoding="utf-8")

    print(f"✅  Generated {len(SECTIONS)} pages → {out_path}")
    print()
    print("Pages:")
    for idx, section in enumerate(SECTIONS):
        print(f"  p.{idx + 1:>2}  {section['title']}")
    print()
    print("How to print:")
    print("  1. Open the HTML file in Chrome or Firefox")
    print("  2. Wait for all Mermaid diagrams to render  (~5 sec)")
    print("  3. Ctrl+P  →  Layout: Landscape  →  Paper: Letter  →  Margins: None/Minimum")
    print("  4. Print!  Each section is one page.")
    print()
    print("Tip: Pages are ordered so edges align when laid side by side.")
    print("     Use the Overview page (p.1) as your connection map.")


if __name__ == "__main__":
    main()
