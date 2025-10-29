#!/bin/bash

# FKS Trading Systems - Package Validator
# Validates NinjaTrader package integrity and structure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[VALIDATE]${NC} $1"
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
FKS Trading Systems Package Validator

Usage: $0 <package.zip> [OPTIONS]

OPTIONS:
    --verbose       Show detailed validation information
    --json          Output results in JSON format
    --help          Show this help message

EXAMPLES:
    $0 FKS_TradingSystem_SOURCE_v1.0.0.zip
    $0 build/packages/FKS_TradingSystem_DLL_v1.0.0.zip --verbose
    $0 package.zip --json

EOF
}

# Parse arguments
PACKAGE_FILE=""
VERBOSE=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            if [[ -z "$PACKAGE_FILE" ]]; then
                PACKAGE_FILE="$1"
            else
                error "Unknown option: $1"
            fi
            shift
            ;;
    esac
done

if [[ -z "$PACKAGE_FILE" ]]; then
    error "Package file required. Use --help for usage information."
fi

if [[ ! -f "$PACKAGE_FILE" ]]; then
    error "Package file not found: $PACKAGE_FILE"
fi

# Validation results
declare -A VALIDATION

# Basic file validation
validate_basic() {
    log "Validating basic package structure..."
    
    # Check if it's a valid zip file
    if ! unzip -t "$PACKAGE_FILE" &>/dev/null; then
        error "Invalid or corrupted zip file"
    fi
    
    VALIDATION[basic]="pass"
    success "Basic validation passed"
}

# Manifest validation
validate_manifest() {
    log "Validating manifest.xml..."
    
    if ! unzip -l "$PACKAGE_FILE" | grep -q "manifest.xml"; then
        error "manifest.xml not found in package"
    fi
    
    # Extract and validate XML
    local temp_dir=$(mktemp -d)
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    if [[ ! -f "$temp_dir/manifest.xml" ]]; then
        error "manifest.xml missing from package root"
    fi
    
    # Basic XML validation
    if ! xmllint --noout "$temp_dir/manifest.xml" 2>/dev/null; then
        warn "manifest.xml has XML syntax issues"
        VALIDATION[manifest]="warn"
    else
        VALIDATION[manifest]="pass"
    fi
    
    # Check for required elements
    if grep -q "NinjaScriptManifest" "$temp_dir/manifest.xml"; then
        success "Valid NinjaScript manifest found"
    else
        error "Invalid manifest format"
    fi
    
    rm -rf "$temp_dir"
}

# Info.xml validation
validate_info() {
    log "Validating Info.xml..."
    
    if ! unzip -l "$PACKAGE_FILE" | grep -q "Info.xml"; then
        warn "Info.xml not found (optional but recommended)"
        VALIDATION[info]="warn"
        return
    fi
    
    local temp_dir=$(mktemp -d)
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    if xmllint --noout "$temp_dir/Info.xml" 2>/dev/null; then
        VALIDATION[info]="pass"
        success "Info.xml validation passed"
    else
        warn "Info.xml has XML syntax issues"
        VALIDATION[info]="warn"
    fi
    
    rm -rf "$temp_dir"
}

# Source files validation
validate_sources() {
    log "Validating source files..."
    
    local temp_dir=$(mktemp -d)
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    local required_dirs=("bin/Custom/AddOns" "bin/Custom/Indicators" "bin/Custom/Strategies")
    local found_sources=false
    
    for dir in "${required_dirs[@]}"; do
        if [[ -d "$temp_dir/$dir" ]] && [[ -n "$(ls -A "$temp_dir/$dir"/*.cs 2>/dev/null)" ]]; then
            found_sources=true
            break
        fi
    done
    
    if [[ "$found_sources" == true ]]; then
        # Count source files
        local cs_count=$(find "$temp_dir" -name "*.cs" | wc -l)
        VALIDATION[sources]="pass"
        VALIDATION[source_count]="$cs_count"
        success "Source files found ($cs_count .cs files)"
    else
        VALIDATION[sources]="none"
        log "No source files found (DLL package)"
    fi
    
    rm -rf "$temp_dir"
}

# DLL validation
validate_dll() {
    log "Validating DLL files..."
    
    local temp_dir=$(mktemp -d)
    unzip -q "$PACKAGE_FILE" -d "$temp_dir"
    
    if [[ -f "$temp_dir/FKS.dll" ]]; then
        # Check if it's a valid .NET assembly
        if file "$temp_dir/FKS.dll" | grep -q "PE32"; then
            VALIDATION[dll]="pass"
            success "Valid DLL found"
        else
            error "Invalid DLL format"
        fi
    else
        VALIDATION[dll]="none"
        log "No DLL found (source package)"
    fi
    
    rm -rf "$temp_dir"
}

# Package size and file count
validate_size() {
    log "Analyzing package size..."
    
    local size=$(du -h "$PACKAGE_FILE" | cut -f1)
    local file_count=$(unzip -l "$PACKAGE_FILE" | tail -1 | awk '{print $2}')
    
    VALIDATION[size]="$size"
    VALIDATION[file_count]="$file_count"
    
    # Size warnings
    local size_bytes=$(stat -f%z "$PACKAGE_FILE" 2>/dev/null || stat -c%s "$PACKAGE_FILE")
    if [[ $size_bytes -gt 10485760 ]]; then  # 10MB
        warn "Package is quite large ($size) - consider optimization"
    fi
    
    success "Package analysis: $size, $file_count files"
}

# Output results
output_results() {
    if [[ "$JSON_OUTPUT" == true ]]; then
        echo "{"
        echo "  \"package\": \"$(basename "$PACKAGE_FILE")\","
        echo "  \"timestamp\": \"$(date -Iseconds)\","
        echo "  \"validation\": {"
        echo "    \"basic\": \"${VALIDATION[basic]}\","
        echo "    \"manifest\": \"${VALIDATION[manifest]}\","
        echo "    \"info\": \"${VALIDATION[info]}\","
        echo "    \"sources\": \"${VALIDATION[sources]}\","
        echo "    \"dll\": \"${VALIDATION[dll]}\""
        echo "  },"
        echo "  \"size\": \"${VALIDATION[size]}\","
        echo "  \"file_count\": ${VALIDATION[file_count]},"
        echo "  \"source_count\": ${VALIDATION[source_count]:-0}"
        echo "}"
    else
        echo
        echo "=================================="
        echo "   Package Validation Results"
        echo "=================================="
        echo "Package: $(basename "$PACKAGE_FILE")"
        echo "Size: ${VALIDATION[size]}"
        echo "Files: ${VALIDATION[file_count]}"
        echo
        echo "Validation Results:"
        echo "  Basic Structure: ${VALIDATION[basic]}"
        echo "  Manifest: ${VALIDATION[manifest]}"
        echo "  Info.xml: ${VALIDATION[info]}"
        echo "  Source Files: ${VALIDATION[sources]}"
        echo "  DLL: ${VALIDATION[dll]}"
        
        if [[ -n "${VALIDATION[source_count]}" && "${VALIDATION[source_count]}" -gt 0 ]]; then
            echo "  Source Count: ${VALIDATION[source_count]} files"
        fi
        
        echo
        echo "✅ Validation completed"
    fi
    
    # Verbose output
    if [[ "$VERBOSE" == true && "$JSON_OUTPUT" == false ]]; then
        echo
        echo "Package Contents:"
        unzip -l "$PACKAGE_FILE"
    fi
}

# Main validation process
main() {
    if [[ "$JSON_OUTPUT" == false ]]; then
        echo "=================================="
        echo "   FKS Package Validator"
        echo "=================================="
        echo
    fi
    
    validate_basic
    validate_manifest
    validate_info
    validate_sources
    validate_dll
    validate_size
    
    output_results
}

# Run main function
main
