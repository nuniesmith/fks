# NinjaTrader Reference DLLs

This directory contains the static reference DLLs required for compiling NinjaTrader 8 projects in external development environments (outside of NinjaTrader).

## Files Included

### NinjaTrader Core DLLs
- **NinjaTrader.Core.dll** - Core NinjaTrader functionality, data structures, and trading APIs
- **NinjaTrader.Custom.dll** - Custom indicators, strategies, and add-ons framework
- **NinjaTrader.Gui.dll** - User interface components and GUI framework

### WPF/Windows Dependencies
- **PresentationCore.dll** - WPF core presentation services
- **PresentationFramework.dll** - WPF application framework
- **System.Xaml.dll** - XAML services and markup extensions

## Usage

These DLLs are referenced in the `FKS.csproj` file using relative paths:

```xml
<Reference Include="NinjaTrader.Core">
  <HintPath>../references/NinjaTrader.Core.dll</HintPath>
  <Private>false</Private>
</Reference>
```

## Version Information

- **NinjaTrader Version**: 8.x
- **Target Framework**: .NET Framework 4.8
- **Last Updated**: 2025-01-11

## Important Notes

1. **Static References**: These are static DLLs that allow compilation outside NinjaTrader
2. **Version Compatibility**: These DLLs must match the NinjaTrader version you're targeting
3. **Distribution**: These DLLs are included in the repository for development convenience
4. **License**: These DLLs are proprietary to NinjaTrader and subject to their license terms

## Git Configuration

The repository is configured to include these DLLs despite the global `*.dll` exclusion:

```gitignore
# Exclude all DLLs
*.dll

# But include reference DLLs
!references/*.dll
```

## External Development

With these references in place, you can:
- Compile NinjaTrader projects in Visual Studio/VS Code
- Use IntelliSense and code completion
- Perform static analysis and debugging
- Build automated CI/CD pipelines
- Develop on Linux/Mac with compatible tools

## Updating References

To update these references:
1. Copy the latest DLLs from your NinjaTrader installation
2. Replace the files in this directory
3. Test compilation to ensure compatibility
4. Commit the updated DLLs to the repository
