#!/bin/bash

# FKS Trading Systems - Build Pipeline
# Professional automated trading system for NinjaTrader 8

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BUILD_DIR="$PROJECT_ROOT/build"
TEMP_DIR="$BUILD_DIR/temp"
PACKAGES_DIR="$BUILD_DIR/packages"
SRC_DIR="$PROJECT_ROOT/src"
TEMPLATES_DIR="$PROJECT_ROOT/templates"

# Package information
PACKAGE_NAME="FKS_TradingSystem"
VERSION="1.0.0"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Help function
show_help() {
    cat << EOF
FKS Trading Systems Build Pipeline

Usage: $0 [OPTIONS]

OPTIONS:
    --source-only       Build source-only package (recommended)
    --dll              Build DLL package  
    --both             Build both package types
    --clean            Clean before build
    --json             Output results in JSON format
    --version VERSION  Set package version (default: $VERSION)
    --help             Show this help message

EXAMPLES:
    $0 --source-only                    # Build source package
    $0 --dll --clean                    # Clean build DLL package
    $0 --both --json                    # Build both with JSON output
    $0 --source-only --version 1.1.0   # Build with custom version

PACKAGE TYPES:
    Source-Only: Contains .cs files, compiled by NinjaTrader (recommended)
    DLL:         Pre-compiled assembly, faster but version-specific

EOF
}

# Parse command line arguments
BUILD_SOURCE=false
BUILD_DLL=false
CLEAN_BUILD=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --source-only)
            BUILD_SOURCE=true
            shift
            ;;
        --dll)
            BUILD_DLL=true
            shift
            ;;
        --both)
            BUILD_SOURCE=true
            BUILD_DLL=true
            shift
            ;;
        --clean)
            CLEAN_BUILD=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            error "Unknown option: $1. Use --help for usage information."
            ;;
    esac
done

# Default to source-only if no build type specified
if [[ "$BUILD_SOURCE" == false && "$BUILD_DLL" == false ]]; then
    BUILD_SOURCE=true
fi

# Initialize build results for JSON output
declare -A BUILD_RESULTS

# Function to start timer
start_timer() {
    START_TIME=$(date +%s.%N)
}

# Function to get elapsed time
get_elapsed_time() {
    END_TIME=$(date +%s.%N)
    ELAPSED=$(echo "$END_TIME - $START_TIME" | bc -l)
    printf "%.2f" $ELAPSED
}

# Clean build directories
clean_build() {
    log "Cleaning build directories..."
    rm -rf "$TEMP_DIR"
    mkdir -p "$TEMP_DIR"
    mkdir -p "$PACKAGES_DIR"
    
    if [[ "$CLEAN_BUILD" == true ]]; then
        rm -rf "$PROJECT_ROOT/bin"
        rm -rf "$SRC_DIR/obj"
    fi
}

# Validate source files
validate_sources() {
    log "Validating source files..."
    
    local required_files=(
        "AddOns/FKS_Core.cs"
        "AddOns/FKS_Calculations.cs" 
        "AddOns/FKS_Infrastructure.cs"
        "AddOns/FKS_Market.cs"
        "AddOns/FKS_Signals.cs"
        "Indicators/FKS_AI.cs"
        "Indicators/FKS_AO.cs"
        "Indicators/FKS_Dashboard.cs"
        "Indicators/FKS_PythonBridge.cs"
        "Strategies/FKS_Strategy.cs"
    )
    
    local missing_files=()
    for file in "${required_files[@]}"; do
        if [[ ! -f "$SRC_DIR/$file" ]]; then
            missing_files+=("$file")
        fi
    done
    
    if [[ ${#missing_files[@]} -gt 0 ]]; then
        error "Missing required source files: ${missing_files[*]}"
    fi
    
    success "All required source files found"
}

# Build source-only package
build_source_package() {
    log "Building source-only package..."
    start_timer
    
    local temp_package="$TEMP_DIR/source_package"
    mkdir -p "$temp_package/bin/Custom/"{AddOns,Indicators,Strategies}
    
    # Copy source files
    cp "$SRC_DIR/AddOns"/*.cs "$temp_package/bin/Custom/AddOns/"
    cp "$SRC_DIR/Indicators"/*.cs "$temp_package/bin/Custom/Indicators/"
    cp "$SRC_DIR/Strategies"/*.cs "$temp_package/bin/Custom/Strategies/"
    
    # Copy manifest and info
    cp "$TEMPLATES_DIR/manifest-source.xml" "$temp_package/manifest.xml"
    cp "$TEMPLATES_DIR/Info.xml" "$temp_package/"
    
    # Create package
    local package_name="${PACKAGE_NAME}_SOURCE_v${VERSION}.zip"
    local package_path="$PACKAGES_DIR/$package_name"
    
    cd "$temp_package"
    zip -r "$package_path" . > /dev/null
    cd - > /dev/null
    
    local elapsed=$(get_elapsed_time)
    local size=$(du -h "$package_path" | cut -f1)
    local file_count=$(unzip -l "$package_path" | tail -1 | awk '{print $2}')
    
    BUILD_RESULTS[source_status]="success"
    BUILD_RESULTS[source_package]="$package_path"
    BUILD_RESULTS[source_size]="$size"
    BUILD_RESULTS[source_files]="$file_count"
    BUILD_RESULTS[source_time]="${elapsed}s"
    
    success "Source package created: $package_name ($size, $file_count files, ${elapsed}s)"
}

# Build DLL package
build_dll_package() {
    log "Building DLL package..."
    start_timer
    
    # Build DLL if it doesn't exist or if clean build
    if [[ ! -f "$PROJECT_ROOT/bin/Release/FKS.dll" || "$CLEAN_BUILD" == true ]]; then
        log "Compiling DLL..."
        cd "$SRC_DIR"
        
        if command -v dotnet &> /dev/null; then
            dotnet build --configuration Release --verbosity quiet
        else
            error "dotnet CLI not found. Cannot build DLL."
        fi
        
        if [[ ! -f "$PROJECT_ROOT/bin/Release/FKS.dll" ]]; then
            error "DLL compilation failed"
        fi
        cd - > /dev/null
    fi
    
    local temp_package="$TEMP_DIR/dll_package"
    mkdir -p "$temp_package"
    
    # Copy DLL
    cp "$PROJECT_ROOT/bin/Release/FKS.dll" "$temp_package/"
    
    # Copy manifest and info
    cp "$TEMPLATES_DIR/manifest-dll.xml" "$temp_package/manifest.xml"
    cp "$TEMPLATES_DIR/Info.xml" "$temp_package/"
    
    # Create package
    local package_name="${PACKAGE_NAME}_DLL_v${VERSION}.zip"
    local package_path="$PACKAGES_DIR/$package_name"
    
    cd "$temp_package"
    zip -r "$package_path" . > /dev/null
    cd - > /dev/null
    
    local elapsed=$(get_elapsed_time)
    local size=$(du -h "$package_path" | cut -f1)
    local file_count=$(unzip -l "$package_path" | tail -1 | awk '{print $2}')
    
    BUILD_RESULTS[dll_status]="success"
    BUILD_RESULTS[dll_package]="$package_path"
    BUILD_RESULTS[dll_size]="$size"
    BUILD_RESULTS[dll_files]="$file_count"
    BUILD_RESULTS[dll_time]="${elapsed}s"
    
    success "DLL package created: $package_name ($size, $file_count files, ${elapsed}s)"
}

# Output results
output_results() {
    if [[ "$JSON_OUTPUT" == true ]]; then
        # JSON output for API integration
        echo "{"
        echo "  \"timestamp\": \"$(date -Iseconds)\","
        echo "  \"version\": \"$VERSION\","
        
        if [[ "$BUILD_SOURCE" == true ]]; then
            echo "  \"source\": {"
            echo "    \"status\": \"${BUILD_RESULTS[source_status]}\","
            echo "    \"package\": \"${BUILD_RESULTS[source_package]}\","
            echo "    \"size\": \"${BUILD_RESULTS[source_size]}\","
            echo "    \"files\": ${BUILD_RESULTS[source_files]},"
            echo "    \"build_time\": \"${BUILD_RESULTS[source_time]}\""
            echo "  }$([ "$BUILD_DLL" == true ] && echo ",")"
        fi
        
        if [[ "$BUILD_DLL" == true ]]; then
            echo "  \"dll\": {"
            echo "    \"status\": \"${BUILD_RESULTS[dll_status]}\","
            echo "    \"package\": \"${BUILD_RESULTS[dll_package]}\","
            echo "    \"size\": \"${BUILD_RESULTS[dll_size]}\","
            echo "    \"files\": ${BUILD_RESULTS[dll_files]},"
            echo "    \"build_time\": \"${BUILD_RESULTS[dll_time]}\""
            echo "  }"
        fi
        
        echo "}"
    else
        # Human-readable output
        echo
        echo "=================================="
        echo "   FKS Build Pipeline Complete"
        echo "=================================="
        echo "Version: $VERSION"
        echo "Timestamp: $(date)"
        echo
        
        if [[ "$BUILD_SOURCE" == true ]]; then
            echo "📦 Source Package:"
            echo "   File: $(basename "${BUILD_RESULTS[source_package]}")"
            echo "   Size: ${BUILD_RESULTS[source_size]}"
            echo "   Files: ${BUILD_RESULTS[source_files]}"
            echo "   Time: ${BUILD_RESULTS[source_time]}"
            echo
        fi
        
        if [[ "$BUILD_DLL" == true ]]; then
            echo "🔧 DLL Package:"
            echo "   File: $(basename "${BUILD_RESULTS[dll_package]}")"
            echo "   Size: ${BUILD_RESULTS[dll_size]}"
            echo "   Files: ${BUILD_RESULTS[dll_files]}"
            echo "   Time: ${BUILD_RESULTS[dll_time]}"
            echo
        fi
        
        echo "📁 Output Directory: $PACKAGES_DIR"
        echo "✅ Build completed successfully!"
    fi
}

# Main build process
main() {
    if [[ "$JSON_OUTPUT" == false ]]; then
        echo "=================================="
        echo "   FKS Trading Systems Builder"
        echo "=================================="
        echo
    fi
    
    # Validate environment
    validate_sources
    
    # Clean build directories
    clean_build
    
    # Build packages
    if [[ "$BUILD_SOURCE" == true ]]; then
        build_source_package
    fi
    
    if [[ "$BUILD_DLL" == true ]]; then
        build_dll_package
    fi
    
    # Output results
    output_results
}

# Run main function
main
