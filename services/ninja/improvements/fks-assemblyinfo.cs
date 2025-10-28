using System.Reflection;
using System.Runtime.CompilerServices;
using System.Runtime.InteropServices;

// General Information about an assembly is controlled through the following 
// set of attributes. Change these attribute values to modify the information
// associated with an assembly.
[assembly: AssemblyTitle("FKS Trading Systems")]
[assembly: AssemblyDescription("Professional automated trading system with AI-enhanced signals for futures markets")]
[assembly: AssemblyConfiguration("")]
[assembly: AssemblyCompany("FKS Trading")]
[assembly: AssemblyProduct("FKS Trading Systems for NinjaTrader 8")]
[assembly: AssemblyCopyright("Copyright © FKS Trading 2025")]
[assembly: AssemblyTrademark("FKS")]
[assembly: AssemblyCulture("")]

// Setting ComVisible to false makes the types in this assembly not visible 
// to COM components.  If you need to access a type in this assembly from 
// COM, set the ComVisible attribute to true on that type.
[assembly: ComVisible(false)]

// The following GUID is for the ID of the typelib if this project is exposed to COM
[assembly: Guid("a4d0c3e1-8f2a-4b5c-9d7e-1a3b5c8d9f0e")]

// Version information for an assembly consists of the following four values:
//
//      Major Version
//      Minor Version 
//      Build Number
//      Revision
//
// You can specify all the values or you can default the Build and Revision Numbers 
// by using the '*' as shown below:
// [assembly: AssemblyVersion("1.0.*")]
[assembly: AssemblyVersion("1.0.0.20250707")]
[assembly: AssemblyFileVersion("1.0.0.20250707")]

// NinjaTrader specific attributes
[assembly: AssemblyMetadata("NinjaTrader.PackageVersion", "1.0.0.0")]
[assembly: AssemblyMetadata("NinjaTrader.MinimumVersion", "8.0.27.1")]
[assembly: AssemblyMetadata("NinjaTrader.Platform", "Futures")]

// Strong name signing (optional - for production use)
// [assembly: AssemblyKeyFile("FKS.snk")]
// [assembly: AssemblyDelaySign(false)]

// Allow internal access between FKS components
[assembly: InternalsVisibleTo("FKS.Tests")]

// Custom attributes for FKS system
[assembly: AssemblyMetadata("FKS.SystemType", "Automated")]
[assembly: AssemblyMetadata("FKS.SupportedMarkets", "GC,ES,NQ,CL,BTC")]
[assembly: AssemblyMetadata("FKS.RequiresDataFeed", "true")]
[assembly: AssemblyMetadata("FKS.RequiresRealtimeData", "true")]