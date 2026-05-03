#!/bin/bash
#
# FKS Test Data Cleanup Script
# ============================
#
# Cleans up old test data, logs, and environment files
#
# Usage:
#   ./scripts/cleanup-test-data.sh [OPTIONS]
#
# Options:
#   --all                Clean everything (logs, env files, test data)
#   --logs              Clean only log directories
#   --env-files         Clean only test environment files
#   --older-than DAYS   Only clean items older than N days (default: 7)
#   --dry-run           Show what would be deleted without deleting
#   --force             Skip confirmation prompts
#   --archive           Archive data before deletion
#   --help              Show this help message
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Default options
CLEAN_LOGS=false
CLEAN_ENV_FILES=false
OLDER_THAN_DAYS=7
DRY_RUN=false
FORCE=false
ARCHIVE=false

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOGS_DIR="$PROJECT_ROOT/logs"
COMPOSE_DIR="$PROJECT_ROOT/infrastructure/compose"
ARCHIVE_DIR="$PROJECT_ROOT/.test-archives"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            CLEAN_LOGS=true
            CLEAN_ENV_FILES=true
            shift
            ;;
        --logs)
            CLEAN_LOGS=true
            shift
            ;;
        --env-files)
            CLEAN_ENV_FILES=true
            shift
            ;;
        --older-than)
            OLDER_THAN_DAYS="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --archive)
            ARCHIVE=true
            shift
            ;;
        --help|-h)
            head -n 20 "$0" | tail -n +3
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# If no options specified, show help
if [ "$CLEAN_LOGS" = false ] && [ "$CLEAN_ENV_FILES" = false ]; then
    echo -e "${YELLOW}No cleanup options specified. Use --help for usage information.${NC}"
    echo ""
    echo "Common usage:"
    echo "  $0 --all                    # Clean everything"
    echo "  $0 --logs --dry-run         # Preview log cleanup"
    echo "  $0 --logs --older-than 7    # Clean logs older than 7 days"
    exit 0
fi

echo -e "${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       FKS Test Data Cleanup                              ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${CYAN}🔍 DRY RUN MODE - No files will be deleted${NC}"
    echo ""
fi

# Function to format size
format_size() {
    local size=$1
    if [ "$size" -lt 1024 ]; then
        echo "${size}B"
    elif [ "$size" -lt 1048576 ]; then
        echo "$(($size / 1024))KB"
    elif [ "$size" -lt 1073741824 ]; then
        echo "$(($size / 1048576))MB"
    else
        echo "$(($size / 1073741824))GB"
    fi
}

# Function to get directory size
get_dir_size() {
    du -sb "$1" 2>/dev/null | cut -f1
}

# Function to archive directory
archive_directory() {
    local dir_path="$1"
    local dir_name=$(basename "$dir_path")

    if [ ! -d "$ARCHIVE_DIR" ]; then
        mkdir -p "$ARCHIVE_DIR"
    fi

    local archive_file="$ARCHIVE_DIR/${dir_name}.tar.gz"

    echo -e "${CYAN}  📦 Archiving to: $archive_file${NC}"
    tar -czf "$archive_file" -C "$(dirname "$dir_path")" "$dir_name" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}  ✓ Archived successfully${NC}"
        return 0
    else
        echo -e "${RED}  ✗ Archive failed${NC}"
        return 1
    fi
}

# Clean log directories
if [ "$CLEAN_LOGS" = true ]; then
    echo -e "${YELLOW}[1/2] Scanning test log directories...${NC}"
    echo ""

    if [ ! -d "$LOGS_DIR" ]; then
        echo -e "${BLUE}  No logs directory found at: $LOGS_DIR${NC}"
    else
        # Find test directories older than specified days
        LOG_DIRS=()
        TOTAL_SIZE=0

        while IFS= read -r -d '' dir; do
            # Check if directory is older than specified days
            DIR_AGE=$(find "$dir" -maxdepth 0 -mtime +${OLDER_THAN_DAYS} 2>/dev/null)

            if [ -n "$DIR_AGE" ]; then
                LOG_DIRS+=("$dir")
                DIR_SIZE=$(get_dir_size "$dir")
                TOTAL_SIZE=$((TOTAL_SIZE + DIR_SIZE))
            fi
        done < <(find "$LOGS_DIR" -mindepth 1 -maxdepth 1 -type d -name "*hr-test-*" -print0 2>/dev/null)

        if [ ${#LOG_DIRS[@]} -eq 0 ]; then
            echo -e "${GREEN}  ✓ No log directories older than $OLDER_THAN_DAYS days found${NC}"
        else
            echo -e "${BLUE}  Found ${#LOG_DIRS[@]} log directories older than $OLDER_THAN_DAYS days:${NC}"
            echo ""

            for dir in "${LOG_DIRS[@]}"; do
                DIR_NAME=$(basename "$dir")
                DIR_SIZE=$(get_dir_size "$dir")
                DIR_SIZE_FMT=$(format_size $DIR_SIZE)
                DIR_MODIFIED=$(stat -c %y "$dir" 2>/dev/null | cut -d' ' -f1 || stat -f %Sm -t %Y-%m-%d "$dir" 2>/dev/null)

                echo -e "  ${CYAN}$DIR_NAME${NC}"
                echo -e "    Size: $DIR_SIZE_FMT | Last modified: $DIR_MODIFIED"
            done

            echo ""
            echo -e "${BLUE}  Total size to clean: $(format_size $TOTAL_SIZE)${NC}"
            echo ""

            # Confirmation
            if [ "$FORCE" = false ] && [ "$DRY_RUN" = false ]; then
                read -p "  Delete these ${#LOG_DIRS[@]} directories? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo -e "${YELLOW}  Skipping log cleanup${NC}"
                    LOG_DIRS=()
                fi
            fi

            # Archive and/or delete
            if [ ${#LOG_DIRS[@]} -gt 0 ]; then
                for dir in "${LOG_DIRS[@]}"; do
                    DIR_NAME=$(basename "$dir")

                    if [ "$ARCHIVE" = true ] && [ "$DRY_RUN" = false ]; then
                        archive_directory "$dir"
                    fi

                    if [ "$DRY_RUN" = true ]; then
                        echo -e "  ${CYAN}[DRY RUN] Would delete: $DIR_NAME${NC}"
                    else
                        rm -rf "$dir"
                        if [ $? -eq 0 ]; then
                            echo -e "  ${GREEN}✓ Deleted: $DIR_NAME${NC}"
                        else
                            echo -e "  ${RED}✗ Failed to delete: $DIR_NAME${NC}"
                        fi
                    fi
                done

                if [ "$DRY_RUN" = false ]; then
                    echo ""
                    echo -e "${GREEN}  ✓ Log cleanup complete!${NC}"
                fi
            fi
        fi
    fi

    echo ""
fi

# Clean test environment files
if [ "$CLEAN_ENV_FILES" = true ]; then
    echo -e "${YELLOW}[2/2] Scanning test environment files...${NC}"
    echo ""

    if [ ! -d "$COMPOSE_DIR" ]; then
        echo -e "${BLUE}  No compose directory found at: $COMPOSE_DIR${NC}"
    else
        # Find test env files
        ENV_FILES=()

        while IFS= read -r -d '' file; do
            # Check if file is older than specified days
            FILE_AGE=$(find "$file" -maxdepth 0 -mtime +${OLDER_THAN_DAYS} 2>/dev/null)

            if [ -n "$FILE_AGE" ]; then
                ENV_FILES+=("$file")
            fi
        done < <(find "$COMPOSE_DIR" -maxdepth 1 -type f -name ".env.*hr-test" -print0 2>/dev/null)

        if [ ${#ENV_FILES[@]} -eq 0 ]; then
            echo -e "${GREEN}  ✓ No test environment files older than $OLDER_THAN_DAYS days found${NC}"
        else
            echo -e "${BLUE}  Found ${#ENV_FILES[@]} test env files older than $OLDER_THAN_DAYS days:${NC}"
            echo ""

            for file in "${ENV_FILES[@]}"; do
                FILE_NAME=$(basename "$file")
                FILE_SIZE=$(stat -c %s "$file" 2>/dev/null || stat -f %z "$file" 2>/dev/null)
                FILE_SIZE_FMT=$(format_size $FILE_SIZE)
                FILE_MODIFIED=$(stat -c %y "$file" 2>/dev/null | cut -d' ' -f1 || stat -f %Sm -t %Y-%m-%d "$file" 2>/dev/null)

                echo -e "  ${CYAN}$FILE_NAME${NC}"
                echo -e "    Size: $FILE_SIZE_FMT | Last modified: $FILE_MODIFIED"
            done

            echo ""

            # Confirmation
            if [ "$FORCE" = false ] && [ "$DRY_RUN" = false ]; then
                read -p "  Delete these ${#ENV_FILES[@]} files? (y/N): " -n 1 -r
                echo
                if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                    echo -e "${YELLOW}  Skipping env file cleanup${NC}"
                    ENV_FILES=()
                fi
            fi

            # Delete files
            if [ ${#ENV_FILES[@]} -gt 0 ]; then
                for file in "${ENV_FILES[@]}"; do
                    FILE_NAME=$(basename "$file")

                    if [ "$DRY_RUN" = true ]; then
                        echo -e "  ${CYAN}[DRY RUN] Would delete: $FILE_NAME${NC}"
                    else
                        rm -f "$file"
                        if [ $? -eq 0 ]; then
                            echo -e "  ${GREEN}✓ Deleted: $FILE_NAME${NC}"
                        else
                            echo -e "  ${RED}✗ Failed to delete: $FILE_NAME${NC}"
                        fi
                    fi
                done

                if [ "$DRY_RUN" = false ]; then
                    echo ""
                    echo -e "${GREEN}  ✓ Env file cleanup complete!${NC}"
                fi
            fi
        fi
    fi

    echo ""
fi

# Summary
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
if [ "$DRY_RUN" = true ]; then
    echo -e "${CYAN}Cleanup preview complete (no files deleted)${NC}"
    echo ""
    echo -e "${YELLOW}Run without --dry-run to actually delete files${NC}"
elif [ "$CLEAN_LOGS" = false ] && [ "$CLEAN_ENV_FILES" = false ]; then
    echo -e "${YELLOW}No cleanup performed${NC}"
else
    echo -e "${GREEN}Cleanup complete!${NC}"

    if [ "$ARCHIVE" = true ] && [ -d "$ARCHIVE_DIR" ]; then
        echo ""
        echo -e "${CYAN}Archives saved to: $ARCHIVE_DIR${NC}"
    fi
fi
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
