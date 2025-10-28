# FKS Trading Systems

## 🎯 **System Overview**

FKS (Freddy Krueger Sniper) is a professional-grade algorithmic trading platform that combines AI-enhanced signals with traditional technical analysis for futures markets. The system features a bulletproof NinjaTrader 8 implementation with comprehensive Python tools and cross-platform development environment.

### **Key Features:**
- **🤖 AI-Enhanced Signals**: Advanced pattern recognition with quality scoring (60-95% confidence)
- **📊 Multi-Component Analysis**: FKS_AI (S/R), FKS_AO (Momentum), FKS_Dashboard (Regime)  
- **⚖️ Bulletproof Risk Management**: Dynamic position sizing, daily limits, ATR-based stops
- **🎯 Tier-Based Trading**: Premium (Tier 1), Strong (Tier 2), Standard (Tier 3) signals
- **🏗️ Modular Architecture**: Clean 800-line strategy with unified AddOns system
- **💰 Multi-Market Support**: Gold (GC), Nasdaq (NQ), Crude Oil (CL), Bitcoin futures
- **🐳 Docker Development**: Complete containerized development environment
- **🔄 CI/CD Pipeline**: GitHub Actions with Tailscale VPN security

### **System Status:**
- ✅ **Strategy Refactored**: 4000+ lines → 800 lines (modular, clean)
- ✅ **Python Implementation**: Complete strategy + monitoring tools  
- ✅ **Risk Management**: $150k account optimized, 1% risk per trade
- ✅ **Deployment Pipeline**: Two-stage Linode deployment with GitHub Actions
- ⚠️ **Active Development**: Signal quality enhancements, VWAP integration

## 📚 **Documentation Hub**

Complete documentation organized by user type and use case:

### **📈 For Traders:**
- **[Trading Guide](docs/TRADING_GUIDE.md)** - Complete manual: signals, setups, risk management
- **[Market Parameters](docs/TRADING_GUIDE.md#market-specific-parameters)** - GC, NQ, CL configurations

### **🚀 For System Admins:**  
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)** - Linode setup, GitHub Actions, security
- **[Troubleshooting Guide](docs/TROUBLESHOOTING_GUIDE.md)** - Common issues and solutions

### **⚙️ For Developers:**
- **[Development Guide](docs/DEVELOPMENT_GUIDE.md)** - Code development, testing, roadmap
- **[Python Implementation](python/README.md)** - Python strategy and monitoring tools

### **📦 NinjaTrader 8 Package:**
- **[NT8 Import Package](FKS_TradingSystem_v1.0.0.zip)** - Ready-to-import NinjaTrader package
- **[Package Documentation](README_NT8_Package.md)** - Installation and usage guide
- **[Build Scripts](create_nt8_package.sh)** - Linux/macOS build automation
- **[Windows Build](create_nt8_package.ps1)** - PowerShell build script

### **📋 Quick Navigation:**
- **New to FKS?** → Start with [Trading Guide](docs/TRADING_GUIDE.md)
- **Setting up system?** → Follow [Deployment Guide](docs/DEPLOYMENT_GUIDE.md)  
- **Developing features?** → Use [Development Guide](docs/DEVELOPMENT_GUIDE.md)
- **Having issues?** → Check [Troubleshooting Guide](docs/TROUBLESHOOTING_GUIDE.md)

## 🏗️ **Architecture**

### **Core Components**
```
┌─────────────────────────────────────────────────────────────┐
│                    FKS Trading Systems                       │
├─────────────────────────────────────────────────────────────┤
│  🎯 NinjaTrader 8 Strategy                                  │
│  ├── FKS_Strategy_Clean.cs (800 lines, refactored)         │
│  ├── FKS AddOns System (Unified components)                │
│  │   ├── FKS_Core.cs           # Core functionality         │
│  │   ├── FKS_Calculations.cs   # Technical analysis        │
│  │   ├── FKS_Infrastructure.cs # Memory & performance      │
│  │   ├── FKS_Market.cs         # Market data handling      │
│  │   └── FKS_Signals.cs        # Signal processing         │
│  └── Indicators: FKS_AI, FKS_AO, FKS_Dashboard                 │
├─────────────────────────────────────────────────────────────┤
│  🐍 Python Bridge & API                                     │
│  ├── FastAPI Server (Port 8002)                            │
│  ├── Real-time WebSocket Data                              │
│  ├── Strategy Implementation (fks_strategy.py)             │
│  └── Monitoring Tools (fks_api.py)                         │
├─────────────────────────────────────────────────────────────┤
│  🌐 Web Interface                                           │
│  ├── React Trading Dashboard (Port 3000)                   │
│  ├── VS Code Server (Port 8081)                            │
│  └── VNC Remote Access (Port 6080)                         │
├─────────────────────────────────────────────────────────────┤
│  ☁️ Infrastructure                                          │
│  ├── Docker Containerization                               │
│  ├── GitHub Actions CI/CD                                  │
│  ├── Tailscale VPN Security                                │
│  └── Linode Cloud Hosting                                  │
└─────────────────────────────────────────────────────────────┘
```

### **Signal Processing Flow**
```
Market Data → FKS_AI (S/R) → Quality Assessment (60-95%)
             ↓
FKS_AO (Momentum) → Component Agreement → Tier Classification
             ↓                              ↓
FKS_Dashboard (Regime) → Risk Management → Position Sizing → Execution
```

### **Trading Signal Hierarchy**
- **🟢 Tier 1 (Premium)**: 85%+ quality, 2.0+ wave ratio → 4-5 contracts
- **🟡 Tier 2 (Strong)**: 70-85% quality, 1.5-2.0 wave → 2-3 contracts  
- **⚪ Tier 3 (Standard)**: 60-70% quality, 1.5+ wave → 1-2 contracts

## 📁 **Project Structure**

```
FKS Trading Systems/
├── README.md                           # Main overview (this file)
├── docs/                              # Core documentation (4 files)
│   ├── TRADING_GUIDE.md              # Complete trading manual
│   ├── DEPLOYMENT_GUIDE.md           # System setup & deployment
│   ├── DEVELOPMENT_GUIDE.md          # Code development & roadmap
│   ├── TROUBLESHOOTING_GUIDE.md      # Problem resolution
│   └── archived/                     # Historical documentation
├── src/                              # NinjaTrader C# source code
│   ├── Strategies/                   # Trading strategies
│   │   ├── FKS_Strategy.cs          # Original (4000+ lines)
│   │   ├── FKS_Strategy_Refactored.cs # Modular version
│   │   └── FKS_Strategy_Clean.cs    # Current clean version (800 lines)
│   ├── Indicators/                   # Custom indicators
│   │   ├── FKS_AI.cs                # AI signal generation
│   │   ├── FKS_AO.cs                # Awesome Oscillator
│   │   └── FKS_Dashboard.cs              # Performance dashboard
│   └── AddOns/                       # Shared infrastructure
│       ├── FKS_Core.cs              # Core functionality
│       ├── FKS_Calculations.cs      # Technical calculations
│       ├── FKS_Infrastructure.cs    # Memory management
│       ├── FKS_Market.cs            # Market analysis
│       └── FKS_Signals.cs           # Signal processing
├── python/                           # Python implementation & tools
│   ├── fks_strategy.py              # Strategy implementation
│   ├── fks_ao.py                    # AO indicator
│   ├── fks_api.py                   # FastAPI server
│   ├── fks_python-bridge.py         # NT bridge
│   ├── requirements.txt             # Dependencies
│   └── README.md                    # Python documentation
├── web/                             # React web interface
├── docker/                          # Development environment
├── scripts/                         # Build and deployment scripts
└── packages/                        # Compiled NT packages
```

## � **Quick Start**

### **🎯 For Traders (NinjaTrader Setup):**
```bash
# 1. Download latest package
# Download FKS_Trading_Systems_v1.0.0.zip from packages/

# 2. Import into NinjaTrader 8
# File → Utilities → Import NinjaScript → Select ZIP file

# 3. Configure indicators
# Add FKS_AI, FKS_AO, FKS_Dashboard to your charts
# See docs/TRADING_GUIDE.md for detailed settings

# 4. Start trading
# Begin in monitoring mode, follow signal hierarchy
```

### **🐍 For Python Development:**
```bash
# 1. Clone repository
git clone https://github.com/nuniesmith/ninja.git
cd ninja

# 2. Set up Python environment
cd python
pip install -r requirements.txt

# 3. Test strategy
python test_fks_strategy.py

# 4. Run monitoring tools
python fks_api.py
```

### **🐳 For Full Development Environment:**
```bash
# 1. Start Docker environment
chmod +x scripts/linux/start-services.sh
./scripts/linux/start-services.sh

# 2. Access interfaces
# Trading Interface: http://localhost:3000
# VS Code Server: http://localhost:8081 (password: fksdev123)
# Python API: http://localhost:8002

# 3. Build and package
dotnet build src/FKS.csproj
./scripts/linux/build-and-package.sh
```

### **Development Workflow:**
1. **Edit Code**: Use VS Code in browser (port 8081) or local IDE
2. **Build**: Use React UI or API endpoints
3. **Test**: Monitor via Python tools and dashboard
4. **Package**: Generate NinjaTrader-ready ZIP files
5. **Deploy**: Import into NinjaTrader for testing

## � **Performance & Status**

### **✅ Completed Features**
- **Strategy Refactoring**: 4000+ lines → 800 lines (clean, modular)
- **Python Implementation**: Complete strategy + monitoring tools ($150k account optimized)
- **Unified AddOns System**: Consistent component architecture
- **Risk Management**: Dynamic position sizing, daily limits, ATR-based stops
- **GitHub Actions CI/CD**: Automated deployment with Tailscale VPN security
- **Multi-Platform Support**: NinjaTrader, Python, Docker development environment

### **🎯 Performance Targets**
| Metric | Target | Current Status |
|--------|--------|----------------|
| **Win Rate** | 55-65% | ✅ Quality over quantity approach |
| **Risk/Reward** | 1:1.5 minimum | ✅ ATR-based stops implemented |
| **Signal Quality** | 65%+ average | ⚠️ Thresholds being optimized |
| **Monthly Return** | 8-15% | ✅ Conservative risk management |
| **Max Drawdown** | <5% | ✅ Daily limits & position sizing |

### **⚠️ Active Development** (see [Development Guide](docs/DEVELOPMENT_GUIDE.md))
1. **Signal Quality Enhancement**: Raising thresholds to 65%+ minimum
2. **VWAP Integration**: Replacing SMA proxy with real VWAP indicator
3. **Component Agreement**: Implementing 2-of-3 component validation
4. **Time-Based Filtering**: Market hours and session optimization

### **🏆 Supported Markets**
| Market | Symbol | Tick Value | Best Hours (EST) | Position Limits |
|--------|--------|------------|------------------|-----------------|
| **Gold Futures** | GC | $10/tick | 8:00 AM - 12:00 PM | 1-5 contracts |
| **NASDAQ Futures** | NQ | $5/tick | 9:30-10:30 AM, 3-4 PM | 1-4 contracts |
| **Crude Oil** | CL | $10/tick | 9:00 AM - 2:30 PM | 1-5 contracts |
| **Bitcoin Futures** | BTC | Variable | 24/7 | 1-2 contracts |

## 🔧 **Development & Building**

### **Build Commands**
```bash
# Build NinjaTrader strategy
dotnet build src/FKS.csproj

# Run available VS Code tasks:
# - build: Build the solution
# - create-addon: Create AddOn directory structure  
# - package-ninjatrader: Package for NT8 distribution

# Package for distribution
./scripts/linux/build-and-package.sh
# Output: packages/FKS_Trading_Systems_v1.0.0.zip
```

### **Testing Strategy**
```bash
# Python strategy testing
cd python
python test_fks_strategy.py

# Full backtest with $150k account
python lgmm.py

# Monitor live signals
python fks_api.py
```

### **Development Workflow**
1. **Code Changes**: Edit in VS Code server (port 8081) or local IDE
2. **Build**: Use dotnet build or VS Code tasks
3. **Test**: Python testing tools and NinjaTrader simulation mode
4. **Package**: Generate NinjaTrader-ready ZIP files
5. **Deploy**: Import into NinjaTrader or deploy via GitHub Actions

## 🛡️ **Risk Management Summary**

### **Account Configuration ($150k Account)**
- **Risk Per Trade**: 1% ($1,500 maximum)
- **Daily Loss Limit**: $3,000 (hard stop)
- **Daily Profit Target**: $4,500 (consider stopping)
- **Position Limits**: 1-5 contracts based on signal tier
- **Margin Requirements**: $15,000 per GC contract

### **Signal-Based Position Sizing**
```
Tier 1 (85%+ quality, 2.0+ wave): 4-5 contracts ($60k-75k margin)
Tier 2 (70-85% quality, 1.5-2.0 wave): 2-3 contracts ($30k-45k margin)  
Tier 3 (60-70% quality, 1.5+ wave): 1-2 contracts ($15k-30k margin)
```

### **Market Regime Adjustments**
- **Trending Market**: Full position sizes
- **Volatile Market**: -50% position reduction
- **Ranging Market**: -30% position reduction

## 🤝 **Contributing & Support**

### **Code Standards**
- Follow C# conventions and NinjaTrader best practices
- Use unified FKS AddOns system for shared functionality
- Comprehensive error handling and logging
- Python code follows PEP 8 standards

### **Testing Requirements**
- **Simulation Mode**: Test all changes in monitoring mode first
- **Backtesting**: Use Python tools for historical validation
- **Risk Validation**: Verify position sizing and risk calculations
- **Documentation**: Update relevant guides for any changes

### **Development Phases** (see [Development Guide](docs/DEVELOPMENT_GUIDE.md))
- **Phase 1**: Core signal quality improvements (in progress)
- **Phase 2**: Enhanced filtering and VWAP integration
- **Phase 3**: Advanced features and optimization

### **Quick Commands**
```bash
# Start development environment
./scripts/linux/start-services.sh

# Build and package for NinjaTrader
dotnet build src/FKS.csproj
./scripts/linux/build-and-package.sh

# Test Python implementation
cd python && python test_fks_strategy.py

# Stop services
./scripts/linux/stop-services.sh
```

---

## ⚠️ **Important Disclaimers**

**This system combines discretionary pattern recognition with systematic signal confirmation.**

- **Start in Monitoring Mode**: Always test thoroughly before live trading
- **Risk Management**: Never exceed 1% risk per trade or daily limits
- **Signal Quality**: Only trade signals with 60%+ quality scores
- **Market Awareness**: Maintain situational awareness beyond signals
- **Account Protection**: System includes multiple safety mechanisms

**Remember: Trust the signals, but always maintain trading discipline and risk awareness.**

---

## 📦 Docker Artifact Usage (External Build / Packaging)

The repository now ships a multi-stage Dockerfile that produces a portable tarball (`fks_ninja_package.tgz`) containing:

- `FKS.dll` (compiled with Mono for net48)  
- All AddOn / Indicator / Strategy source files (left uncompiled for NinjaTrader to compile natively)  
- `manifest.xml` and ancillary metadata

### Build All Stages

```bash
# From repo root (fks_ninja)
docker build -t fks_ninja:artifact .
```

### Extract Package Tarball

```bash
CID=$(docker create fks_ninja:artifact)
docker cp "$CID:/fks_ninja_package.tgz" .
docker rm -v "$CID"
sha256sum fks_ninja_package.tgz
tar -tzf fks_ninja_package.tgz | head
```

### Import Into NinjaTrader 8

1. Copy `fks_ninja_package.tgz` to your workstation.  
2. (Optional) Rename to `FKS_TradingSystem_v1.0.0.tgz` for version clarity.  
3. Extract the tarball; place `FKS.dll` plus the `bin/Custom/...` source tree into your NinjaTrader `Documents/NinjaTrader 8/bin/Custom/` folder (or import via a ZIP you create containing that structure).  
4. Restart NinjaTrader and verify `FKS` appears under Indicators / Strategies.  

### Using docker-compose (Dev)

```bash
# Build dev + artifact services
docker compose -f docker-compose.dev.yml up -d --build
# Copy out tarball from artifact container
docker cp $(docker ps --filter ancestor=fks_ninja:artifact -q | head -n1):/fks_ninja_package.tgz ./
```

### Helper Script

See `scripts/extract_ninja_package.sh` (added) for an automated extraction workflow with checksum validation.

> Note: Build warning MSB3277 (System.Text.Json version conflict between Mono-resolved package and NinjaTrader reference shim) is intentionally suppressed in this external build. The DLL is compiled with compile-time reference only (`ExcludeAssets=runtime`), allowing NinjaTrader to load its own runtime assembly without duplication.

### Create Importable ZIP

Once you have `fks_ninja_package.tgz` you can generate a NinjaTrader 8 import ZIP:

```bash
./scripts/package_zip_from_tar.sh  # creates FKS_TradingSystem_v1.0.0.zip
```

If you need a different version tag:

```bash
FKS_VERSION=1.1.0 ./scripts/package_zip_from_tar.sh
```

Resulting ZIP includes `FKS.dll` at root plus `bin/Custom/Indicators` & `bin/Custom/Strategies` sources for NT8 compile/import.
