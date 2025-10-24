# FKS Trading Systems - Development Guide

## 🎯 **OVERVIEW**

This guide covers development setup, GitHub Actions CI/CD, strategy implementation, and technical improvements for the FKS Trading Systems.

---

## 🚀 **CURRENT SYSTEM STATUS**

### ✅ **Completed:**
- Refactored strategy from 4000+ lines to 800 lines
- Created modular FKS_Strategy_Clean.cs
- Unified FKS AddOns system (Core, Calculations, Infrastructure, Market, Signals)
- Component health monitoring and error handling
- Basic signal coordination and filtering
- GitHub Actions CI/CD pipeline
- Two-stage deployment system

### ⚠️ **Critical Issues to Address:**

1. **Signal Quality Problems** (Priority 1)
   - Current thresholds too low (need 0.65+ minimum)
   - Weak setup detection logic

2. **Trading Logic Gaps** (Priority 2)
   - AO zero-line cross not properly integrated
   - Time-based filtering incomplete

3. **Risk Management Gaps** (Priority 3)
   - Dynamic position sizing not fully implemented
   - Daily limit system needs refinement

---

## 🔧 **LOCAL DEVELOPMENT SETUP**

### **Prerequisites**
- **Visual Studio 2022** with .NET 8 SDK
- **NinjaTrader 8** installed
- **Git** for version control
- **Docker Desktop** (for testing containers)
- **Node.js** (for web interface development)

### **Repository Setup**
```bash
# Clone the repository
git clone https://github.com/nuniesmith/ninja.git
cd ninja

# Set up development environment
# For Windows PowerShell:
.\scripts\windows\setup-dev-environment.ps1

# For WSL/Linux:
chmod +x scripts/setup-and-test.sh
./scripts/setup-and-test.sh
```

### **NinjaTrader Development**
```bash
# Build the strategy
dotnet build src/FKS.csproj

# Copy to NinjaTrader (Windows)
Copy-Item "bin\Debug\*.dll" "$env:USERPROFILE\Documents\NinjaTrader 8\bin\Custom\Strategy\"

# Or use the build task in VS Code
# Ctrl+Shift+P → "Tasks: Run Task" → "build"
```

---

## 📁 **PROJECT STRUCTURE**

```
ninja/
├── src/                           # NinjaTrader C# source code
│   ├── Strategies/
│   │   ├── FKS_Strategy_Clean.cs      # Main strategy (800 lines)
│   │   └── FKS_Strategy_Refactored.cs # Alternative implementation
│   ├── AddOns/
│   │   ├── FKS_Core.cs               # Core functionality
│   │   ├── FKS_Calculations.cs       # Math and calculations
│   │   ├── FKS_Infrastructure.cs     # Infrastructure services
│   │   ├── FKS_Market.cs            # Market data handling
│   │   └── FKS_Signals.cs           # Signal generation
│   └── FKS.csproj                   # Project file
├── python/                        # Python bridge and API
│   ├── fks_api.py                 # FastAPI server
│   ├── fks-python-bridge.py       # NinjaTrader bridge
│   └── requirements.txt           # Python dependencies
├── web/                          # React web interface
│   ├── src/                      # React components
│   ├── public/                   # Static assets
│   └── package.json             # Node dependencies
├── scripts/                     # Deployment and utility scripts
│   ├── StackScript.sh           # Linode deployment script
│   ├── start-dev-servers.sh     # Development server startup
│   └── windows/                 # Windows-specific scripts
└── docs/                       # Documentation (this file)
```

---

## 🔄 **GITHUB ACTIONS CI/CD**

### **Workflow Overview**
The system uses GitHub Actions for automated deployment with Tailscale for secure networking.

### **Required Secrets**
Configure these in **GitHub Settings → Secrets and variables → Actions**:

```
TAILSCALE_OAUTH_CLIENT_ID     # Tailscale OAuth client ID
TAILSCALE_OAUTH_SECRET        # Tailscale OAuth secret
NINJA_SSH_PRIVATE_KEY         # SSH private key for deployment
DISCORD_WEBHOOK               # Discord webhook (optional)
```

### **Workflow Triggers**
- **Automatic**: Pushes to `main` branch trigger staging deployment
- **Manual**: Production deployment via workflow dispatch
- **Testing**: All branches run tests and validation

### **Deployment Process**
1. **Connect to Tailscale VPN** for secure access
2. **Run tests** on Python components and configuration validation
3. **Deploy to staging** environment automatically
4. **Deploy to production** manually with approval workflow
5. **Health checks** verify deployment success
6. **Notifications** sent to Discord (if configured)

### **Setting Up OAuth Client**
1. Go to [Tailscale Admin Console](https://login.tailscale.com/admin)
2. Navigate to **Settings** → **OAuth clients**
3. Click **Generate OAuth client**
4. Configure:
   - **Name**: `GitHub Actions CI/CD`
   - **Scopes**: `devices:write`, `all:read`
   - **Tags**: `tag:ci-cd`
5. Copy Client ID and Secret to GitHub secrets

---

## 🏗️ **STRATEGY IMPLEMENTATION ROADMAP**

### **PHASE 1: IMMEDIATE FIXES (Week 1)**

#### **Step 1.1: Fix Core Signal Thresholds**
**File**: `src/Strategies/FKS_Strategy_Clean.cs`

```csharp
// Update these critical thresholds:
SignalThreshold = 0.65;           // Was likely too low
StrongSignalThreshold = 0.80;     // Raised for quality
MinComponentAgreement = 2;        // Require 2 of 3 components
```

#### **Step 1.2: Implement Proper VWAP**
**File**: `src/Strategies/FKS_Strategy_Clean.cs`

```csharp
// Replace SMA proxy with real VWAP
private VWAP vwap;  // Instead of SMA vwapProxy

// In InitializeIndicators():
vwap = VWAP(Close);  // Use NinjaTrader's built-in VWAP
```

#### **Step 1.3: Enhance Setup Detection**
**File**: `src/Strategies/FKS_Strategy_Clean.cs`

Add to `GenerateSimpleSignal()` method:

```csharp
// Enhanced bullish setup detection
private bool DetectBullishBreakout()
{
    bool priceAboveEMA = Close[0] > ema9[0];
    return priceAboveEMA && emaAboveVWAP && volumeConfirmation && aoSupport;
}
```

#### **Step 1.4: Add Component Agreement Logic**
**File**: `src/Strategies/FKS_Strategy_Clean.cs`

```csharp
private bool ValidateComponentAgreement(CompositeSignal signal)
{
    int agreeingComponents = 0;
    // Check each component
    if (signal.PriceAction.IsValid) agreeingComponents++;
    if (signal.Momentum.IsValid) agreeingComponents++;
    if (signal.Volume.IsValid) agreeingComponents++;
    
    return agreeingComponents >= MinComponentAgreement;
}
```

### **PHASE 2: ENHANCED FILTERING (Week 2)**

#### **Step 2.1: Market Condition Detection**
```csharp
private MarketCondition DetectMarketCondition()
{
    // Add ADX for trend strength
    double adxValue = adx[0];
    
    if (adxValue > 25) return MarketCondition.Trending;
    if (adxValue < 15) return MarketCondition.Ranging;
    return MarketCondition.Normal;
}
```

#### **Step 2.2: Time-Based Filtering Enhancement**
```csharp
private bool IsActiveTradingTime()
{
    var currentTime = Time[0].TimeOfDay;
    
    // Market-specific active hours
    if (Instrument.MasterInstrument.Name.Contains("GC"))
    {
        // Gold: 8:00 AM - 12:00 PM EST
        return currentTime >= new TimeSpan(8, 0, 0) && 
               currentTime <= new TimeSpan(12, 0, 0);
    }
    
    return true; // Default to allow trading
}
```

### **PHASE 3: ADVANCED FEATURES (Week 3-4)**

#### **Step 3.1: Dynamic Position Sizing**
```csharp
private int CalculateDynamicPosition(double signalQuality, MarketCondition condition)
{
    int baseSize = BaseContractSize;
    
    // Adjust for signal quality
    if (signalQuality > 0.85) baseSize = (int)(baseSize * 1.5);
    else if (signalQuality < 0.65) baseSize = Math.Max(1, baseSize - 1);
    
    // Adjust for market condition
    switch (condition)
    {
        case MarketCondition.Volatile:
            baseSize = (int)(baseSize * 0.5);
            break;
        case MarketCondition.Ranging:
            baseSize = (int)(baseSize * 0.7);
            break;
    }
    
    return Math.Min(baseSize, MaxContractSize);
}
```

---

## 🧪 **TESTING STRATEGY**

### **Unit Testing Approach**
```csharp
// Example test structure for strategy components
[TestMethod]
public void TestSignalQualityThreshold()
{
    var signal = new CompositeSignal 
    { 
        Quality = 0.75,
        Components = { /* test data */ }
    };
    
    Assert.IsTrue(ValidateSignalQuality(signal));
}
```

### **Backtesting Protocol**
1. **Historical Data**: Use 3-6 months of 5-minute data
2. **Markets**: Test on GC, NQ, CL separately
3. **Metrics**: Track win rate, R:R, max drawdown
4. **Validation**: Compare against manual trading results

### **Live Testing Phases**
1. **Monitor Only**: Strategy runs but doesn't place trades
2. **Single Contract**: Minimal risk live testing
3. **Scaled Testing**: Gradually increase position sizes
4. **Full Production**: Normal operation with all features

---

## 🔍 **DEBUGGING AND MONITORING**

### **NinjaTrader Debug Output**
```csharp
// Enhanced logging for development
Print($"{Time[0]:HH:mm:ss} - Signal Quality: {signalQuality:F2}, " +
      $"Components: {componentAgreement}, Action: {tradeAction}");
```

### **Python API Monitoring**
```python
# Health check endpoint for monitoring
@app.get("/healthz")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "ninja_connection": check_ninja_connection()
    }
```

### **Web Interface Integration**
```javascript
// React component for real-time strategy monitoring
const StrategyMonitor = () => {
    const [strategyStatus, setStrategyStatus] = useState({});
    
    useEffect(() => {
        const ws = new WebSocket('ws://localhost:8002/ws');
        ws.onmessage = (event) => {
            setStrategyStatus(JSON.parse(event.data));
        };
    }, []);
    
    return <div>Strategy Status: {strategyStatus.state}</div>;
};
```

---

## 🛠️ **DEVELOPMENT TOOLS**

### **VS Code Configuration**
```json
// .vscode/tasks.json
{
    "version": "1.0.0",
    "tasks": [
        {
            "label": "build",
            "type": "process",
            "command": "dotnet",
            "args": ["build", "src/FKS.csproj"],
            "group": {"kind": "build", "isDefault": true}
        }
    ]
}
```

### **Useful Development Commands**
```bash
# Build and test strategy
dotnet build src/FKS.csproj
dotnet test

# Start development servers
./start-dev-servers.sh

# Monitor logs
tail -f logs/strategy.log
docker-compose logs -f

# Check deployment status
ssh ninja@your-server "systemctl status ninja-trading"
```

---

## 📈 **PERFORMANCE OPTIMIZATION**

### **Strategy Performance**
- **Signal Processing**: Optimize indicator calculations
- **Memory Usage**: Efficient data series management
- **CPU Usage**: Minimize heavy calculations in OnBarUpdate
- **Network**: Efficient API communication

### **System Performance**
- **Docker**: Use multi-stage builds for smaller images
- **Database**: Index frequently queried fields
- **Caching**: Implement Redis for session data
- **Monitoring**: Use Prometheus/Grafana for metrics

---

## 🔄 **DEPLOYMENT WORKFLOW**

### **Development to Production**
1. **Feature Development**: Work on feature branch
2. **Local Testing**: Test with NinjaTrader Simulator
3. **PR Review**: Code review and automated tests
4. **Staging Deploy**: Automatic deployment to staging
5. **Production Deploy**: Manual approval and deployment
6. **Monitoring**: Watch metrics and logs post-deployment

### **Rollback Strategy**
```bash
# Quick rollback commands
git revert HEAD
git push origin main

# Or manual rollback on server
ssh ninja@your-server
cd /home/ninja/ninja
git reset --hard previous-commit
docker-compose restart
```

---

## 📚 **NEXT DEVELOPMENT PRIORITIES**

### **Short Term (1-2 weeks)**
1. Fix signal quality thresholds
2. Implement proper VWAP integration
3. Add component agreement validation
4. Enhance time-based filtering

### **Medium Term (1 month)**
1. Dynamic position sizing implementation
2. Advanced market regime detection
3. Enhanced backtesting framework
4. Real-time performance dashboard

### **Long Term (3 months)**
1. Machine learning signal enhancement
2. Multi-timeframe analysis
3. Portfolio management features
4. Advanced risk management system

Remember to always test changes thoroughly in simulation before deploying to live trading!
