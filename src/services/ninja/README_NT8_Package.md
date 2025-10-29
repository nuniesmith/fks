# FKS Trading Systems - NinjaTrader 8 Package

A comprehensive trading system for NinjaTrader 8 that includes advanced indicators, automated strategies, and utility AddOns for professional trading.

## Package Contents

### Compiled Assembly
- **FKS.dll** - Main compiled assembly containing all components

### Indicators
- **FKS_AI.cs** - AI-powered trading indicator with machine learning capabilities
- **FKS_AO.cs** - Advanced Oscillator indicator for momentum analysis  
- **FKS_Dashboard.cs** - Information display indicator for market insights
- **FKS_PythonBridge.cs** - Bridge for Python integration and external analytics

### Strategies
- **FKS_Strategy.cs** - Main automated trading strategy with risk management

### AddOns (Utility Classes)
- **FKS_Core.cs** - Core foundation classes and unified types
- **FKS_Calculations.cs** - Technical calculation engines and buffers
- **FKS_Infrastructure.cs** - Infrastructure utilities and performance tracking
- **FKS_Market.cs** - Market regime analysis and state detection
- **FKS_Signals.cs** - Signal generation and coordination

## Installation Instructions

### Method 1: Using the Pre-built Package (Recommended)

1. **Download the Package**
   - Download `FKS_TradingSystem_v1.0.0.zip` 

2. **Import into NinjaTrader 8**
   - Open NinjaTrader 8
   - Go to `Tools` > `Import NinjaScript...`
   - Click `Browse` and select the downloaded zip file
   - Follow the import wizard prompts
   - Click `Import` to complete the installation

3. **Restart NinjaTrader**
   - Close and restart NinjaTrader 8 for best results
   - The components will be available in their respective categories

### Method 2: Building from Source

If you want to build the package yourself:

#### Prerequisites
- .NET Framework 4.8 Developer Pack
- Visual Studio 2019+ or VS Code with C# extension
- NinjaTrader 8 installed

#### Linux/macOS Build
```bash
# Navigate to the project directory
cd /path/to/fks/trading/system

# Run the build script
./create_nt8_package.sh
```

#### Windows Build
```powershell
# Navigate to the project directory in PowerShell
cd "C:\path\to\fks\trading\system"

# Run the build script
.\create_nt8_package.ps1
```

## Usage

### Indicators

#### FKS_AI
- Add to chart: Right-click chart > Indicators > FKS_AI
- Provides AI-powered market analysis and predictions
- Configurable parameters for different market conditions

#### FKS_AO (Advanced Oscillator)
- Add to chart: Right-click chart > Indicators > FKS_AO  
- Advanced momentum oscillator with multiple signal types
- Supports trend and momentum analysis

#### FKS_Dashboard
- Add to chart: Right-click chart > Indicators > FKS_Dashboard
- Displays real-time market information and statistics
- Customizable information panels

#### FKS_PythonBridge
- Add to chart: Right-click chart > Indicators > FKS_PythonBridge
- Enables integration with Python analytics
- Requires Python environment setup

### Strategies

#### FKS_Strategy
- Apply to chart: Right-click chart > Strategies > FKS_Strategy
- Automated trading with built-in risk management
- Multiple entry and exit conditions
- Configurable position sizing and risk parameters

## Configuration

### Key Configuration Areas

1. **Risk Management**
   - Position sizing rules
   - Stop loss and take profit levels
   - Maximum drawdown limits

2. **Signal Processing**
   - Signal confirmation requirements
   - Time frame analysis
   - Market regime filtering

3. **Performance Optimization**
   - Memory management settings
   - Calculation frequency
   - Cache configuration

## System Requirements

- **NinjaTrader 8.1.2.1** or later
- **Windows 10/11** (for NinjaTrader)
- **.NET Framework 4.8**
- **Minimum 8GB RAM** (16GB recommended for optimal performance)
- **SSD storage** recommended for better performance

## File Structure

The package follows NinjaTrader's standard import structure:

```
FKS_TradingSystem_v1.0.0.zip
├── manifest.xml                    # Package manifest
├── Info.xml                        # NinjaTrader version info
└── bin/
    ├── FKS.dll                     # Compiled assembly
    └── Custom/
        ├── AddOns/
        │   ├── FKS_Core.cs
        │   ├── FKS_Calculations.cs
        │   ├── FKS_Infrastructure.cs
        │   ├── FKS_Market.cs
        │   └── FKS_Signals.cs
        ├── Indicators/
        │   ├── FKS_AI.cs
        │   ├── FKS_AO.cs
        │   ├── FKS_Dashboard.cs
        │   └── FKS_PythonBridge.cs
        └── Strategies/
            └── FKS_Strategy.cs
```

## Troubleshooting

### Common Issues

1. **Import Fails**
   - Ensure NinjaTrader 8.1.2.1 or later is installed
   - Close all chart windows before importing
   - Try importing as Administrator

2. **Compilation Errors**
   - Restart NinjaTrader after import
   - Check that all dependencies are available
   - Verify .NET Framework 4.8 is installed

3. **Performance Issues**
   - Adjust calculation frequency in AddOn settings
   - Increase available memory for NinjaTrader
   - Consider reducing the number of instruments being analyzed

### Getting Help

1. **Check the NinjaScript Output Window**
   - Look for error messages or warnings
   - Check for compilation issues

2. **Review Log Files**
   - NinjaTrader log files contain detailed error information
   - Located in `Documents\NinjaTrader 8\log\`

3. **Community Support**
   - Post questions on NinjaTrader forums
   - Include error messages and system configuration

## Version History

### v1.0.0 - Initial Release
- Complete FKS Trading Systems implementation
- AI-powered indicators and strategies
- Comprehensive AddOn utilities
- Full NinjaTrader 8 compatibility

## License and Disclaimer

This software is provided for educational and research purposes. 
- Use at your own risk
- Past performance does not guarantee future results
- Always test thoroughly in simulation before live trading
- The authors are not responsible for any trading losses

## Technical Notes

### Dependencies
- All required assemblies are included in the package
- No external NuGet packages required for basic functionality
- Python integration requires separate Python environment setup

### Performance Considerations
- Optimized for real-time data processing
- Efficient memory management with built-in caching
- Multi-threading support for improved performance
- Suitable for high-frequency data environments

### Compatibility
- Designed for NinjaTrader 8.1.2.1+
- Compatible with all NinjaTrader data providers
- Supports tick replay and historical data analysis
- Works with both live and simulation accounts
