# FKS NinjaTrader Project Makefile

# Variables
PROJECT_NAME = FKS
BUILD_DIR = build
OUTPUT_DIR = $(BUILD_DIR)/output
DOCKER_IMAGE = fks_ninjatrader
PYTHON_SCRIPT = fks_master-script.py

# Colors
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m

.PHONY: all clean build test docker-build docker-run fix lint package help

all: clean fix build

help:
	@echo "$(GREEN)FKS NinjaTrader Project Makefile$(NC)"
	@echo "Available targets:"
	@echo "  make all         - Clean, fix, and build the project"
	@echo "  make build       - Build the C# project"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make fix         - Fix compilation issues"
	@echo "  make lint        - Run code analysis"
	@echo "  make test        - Run tests"
	@echo "  make package     - Create deployment package"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run  - Run in Docker container"
	@echo "  make monitor     - Run Python monitoring script"

clean:
	@echo "$(YELLOW)Cleaning build artifacts...$(NC)"
	@rm -rf $(BUILD_DIR)/output
	@rm -rf bin obj
	@find . -name "*.tmp" -delete

fix:
	@echo "$(GREEN)Running fix script...$(NC)"

build:
	@echo "$(GREEN)Building FKS project...$(NC)"
	@mkdir -p $(OUTPUT_DIR)
	@if command -v msbuild >/dev/null 2>&1; then \
		msbuild $(PROJECT_NAME).csproj /p:Configuration=Release /p:OutputPath=$(OUTPUT_DIR); \
	else \
		echo "$(YELLOW)MSBuild not found, trying dotnet build...$(NC)"; \
		dotnet build $(PROJECT_NAME).csproj -c Release -o $(OUTPUT_DIR); \
	fi

lint:
	@echo "$(GREEN)Running code analysis...$(NC)"
	@find fks/src -name "*.cs" -exec echo "Checking {}" \; -exec grep -n "TODO\|FIXME\|HACK" {} + || true

test:
	@echo "$(GREEN)Running tests...$(NC)"
	@if [ -d "tests" ]; then \
		dotnet test tests/*.csproj; \
	else \
		echo "$(YELLOW)No tests found!$(NC)"; \
	fi
