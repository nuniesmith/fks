#!/bin/bash
# Helper script to organize existing issues and decide what to import

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== FKS Issue Analysis & Organization ===${NC}"
echo ""

echo -e "${YELLOW}Current Issues Summary:${NC}"
echo ""

# Count issues
TOTAL_OPEN=$(gh issue list --state open --limit 100 | wc -l)
RAG_ISSUES=$(gh issue list --label "rag" --state open | wc -l)

echo "Total Open Issues: $TOTAL_OPEN"
echo "RAG-related Issues: $RAG_ISSUES"
echo ""

echo -e "${BLUE}Existing Issue Breakdown:${NC}"
gh issue list --limit 20

echo ""
echo -e "${BLUE}==================== Analysis ====================${NC}"
echo ""

echo -e "${GREEN}Your Current Issues (#62-73):${NC}"
echo "  • Focus: RAG system implementation (12 phases)"
echo "  • Status: All recently opened"
echo "  • Labels: rag, phase-1 through phase-12"
echo ""

echo -e "${GREEN}Proposed Platform Issues (from import script):${NC}"
echo "  • Focus: Core platform (security, testing, deployment)"
echo "  • Count: 19 issues across 7 phases"
echo "  • Labels: platform, impact/urgency/effort, phase:1-7"
echo ""

echo -e "${BLUE}==================== Options ====================${NC}"
echo ""

echo -e "${YELLOW}Option 1: Import All Platform Issues${NC}"
echo "  Pros: Comprehensive task tracking for platform + RAG"
echo "  Cons: 32 total open issues (might be overwhelming)"
echo "  Command: ./scripts/import_github_issues.sh"
echo ""

echo -e "${YELLOW}Option 2: Import Only Critical Platform Issues${NC}"
echo "  Import: Security, Import Fixes, Testing (Phase 1 only)"
echo "  Pros: Focus on immediate needs, manageable count"
echo "  Cons: Missing long-term roadmap visibility"
echo "  Command: ./scripts/import_phase1_only.sh"
echo ""

echo -e "${YELLOW}Option 3: Organize Existing Issues First${NC}"
echo "  Steps:"
echo "    1. Review existing RAG issues"
echo "    2. Add milestones and priorities"
echo "    3. Close any duplicates or unnecessary issues"
echo "    4. Then import platform issues as needed"
echo "  Command: (Manual - see below)"
echo ""

echo -e "${YELLOW}Option 4: Create GitHub Project Board${NC}"
echo "  Create board with columns:"
echo "    - RAG Development"
echo "    - Platform Development  "
echo "    - Testing & QA"
echo "    - Documentation"
echo "  Pros: Visual organization, drag-and-drop prioritization"
echo "  Command: gh project create --title 'FKS Development'"
echo ""

echo -e "${BLUE}==================== Recommendation ====================${NC}"
echo ""

echo -e "${GREEN}Recommended Approach:${NC}"
echo ""
echo "1. ${YELLOW}Import Phase 1 platform issues now${NC} (3 critical issues):"
echo "   - Security Hardening (blocks everything)"
echo "   - Fix Import/Test Failures (blocks development)"
echo "   - Code Cleanup (improves productivity)"
echo ""
echo "2. ${YELLOW}Create GitHub Project board${NC} to organize:"
echo "   - RAG track (your existing #62-73)"
echo "   - Platform track (new Phase 1 issues)"
echo ""
echo "3. ${YELLOW}Import remaining platform phases${NC} after Phase 1 complete"
echo ""

echo -e "${BLUE}==================== Quick Actions ====================${NC}"
echo ""

read -p "Would you like to import Phase 1 platform issues now? [y/N]: " import_phase1

if [[ "$import_phase1" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${GREEN}Importing Phase 1 issues...${NC}"
    
    # Create Platform Phase 1 milestone
    gh api repos/:owner/:repo/milestones -X POST \
      -f title="Platform Phase 1: Immediate Fixes" \
      -f description="Security, imports, cleanup (20-30 hours)" \
      -f state="open" 2>/dev/null || echo "Milestone exists"
    
    # Import 3 critical issues (abbreviated for safety)
    echo "Creating Issue: Security Hardening..."
    gh issue create \
      --title "[PLATFORM] Security Hardening" \
      --label "platform,security,impact:high,urgency:high,effort:medium" \
      --milestone "Platform Phase 1: Immediate Fixes" \
      --body "See docs/GITHUB_ISSUES_IMPORT.md for details"
    
    echo "Creating Issue: Fix Import/Test Failures..."
    gh issue create \
      --title "[PLATFORM] Fix Import/Test Failures" \
      --label "platform,testing,impact:high,urgency:high,effort:high" \
      --milestone "Platform Phase 1: Immediate Fixes" \
      --body "See docs/GITHUB_ISSUES_IMPORT.md for details"
    
    echo "Creating Issue: Code Cleanup..."
    gh issue create \
      --title "[PLATFORM] Code Cleanup" \
      --label "platform,refactor,impact:medium,urgency:medium,effort:medium" \
      --milestone "Platform Phase 1: Immediate Fixes" \
      --body "See docs/GITHUB_ISSUES_IMPORT.md for details"
    
    echo ""
    echo -e "${GREEN}✓ Created 3 Phase 1 platform issues${NC}"
    echo ""
    gh issue list --milestone "Platform Phase 1: Immediate Fixes"
else
    echo ""
    echo -e "${YELLOW}Skipped import. Review your options above.${NC}"
fi

echo ""
read -p "Would you like to create a GitHub Project board? [y/N]: " create_project

if [[ "$create_project" =~ ^[Yy]$ ]]; then
    echo ""
    echo -e "${GREEN}Creating GitHub Project...${NC}"
    gh project create --owner @me --title "FKS Development Roadmap"
    echo ""
    echo -e "${GREEN}✓ Project created! Add issues with:${NC}"
    echo "   gh issue edit <number> --add-project 'FKS Development Roadmap'"
fi

echo ""
echo -e "${BLUE}==================== Next Steps ====================${NC}"
echo ""
echo "1. Review issues: ${YELLOW}gh issue list${NC}"
echo "2. View specific issue: ${YELLOW}gh issue view <number>${NC}"
echo "3. Start work: ${YELLOW}gh issue develop <number> --checkout${NC}"
echo "4. See full platform roadmap: ${YELLOW}cat docs/GITHUB_ISSUES_IMPORT.md${NC}"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"
