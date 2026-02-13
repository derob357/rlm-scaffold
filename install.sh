#!/usr/bin/env bash
#
# install.sh — Install the RLM scaffold for Claude Code
#
# Usage:
#   ./install.sh
#   ANTHROPIC_API_KEY=sk-ant-... ./install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_DIR="$HOME/.claude/plugins/rlm"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
RLM_MARKER="# RLM (Recursive Language Model)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[rlm]${NC} $*"; }
warn()  { echo -e "${YELLOW}[rlm]${NC} $*"; }
error() { echo -e "${RED}[rlm]${NC} $*" >&2; }

# --- 1. Check Python 3 ---
if ! command -v python3 &>/dev/null; then
    error "python3 not found. Please install Python 3.9+ first."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
info "Found Python $PY_VERSION"

# --- 2. Install anthropic SDK ---
info "Installing anthropic Python SDK..."
pip install -q "anthropic>=0.79.0" 2>/dev/null || pip3 install -q "anthropic>=0.79.0"
info "anthropic SDK installed."

# --- 3. Get API key ---
if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    # Check if already in shell profile
    for f in "$HOME/.zshrc" "$HOME/.bashrc" "$HOME/.bash_profile"; do
        if [ -f "$f" ] && grep -q "ANTHROPIC_API_KEY" "$f" 2>/dev/null; then
            EXISTING_KEY=$(grep "ANTHROPIC_API_KEY" "$f" | head -1 | sed 's/.*="//' | sed 's/".*//')
            if [ -n "$EXISTING_KEY" ]; then
                info "Found existing ANTHROPIC_API_KEY in $(basename "$f")"
                ANTHROPIC_API_KEY="$EXISTING_KEY"
                break
            fi
        fi
    done
fi

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
    echo ""
    echo -e "${YELLOW}An Anthropic API key is required for RLM sub-queries.${NC}"
    echo "Get one at: https://console.anthropic.com/settings/keys"
    echo ""
    read -rp "Paste your ANTHROPIC_API_KEY (or press Enter to skip): " ANTHROPIC_API_KEY
    if [ -z "$ANTHROPIC_API_KEY" ]; then
        warn "Skipping API key setup. You'll need to set ANTHROPIC_API_KEY manually."
    fi
fi

# --- 4. Copy plugin files ---
info "Installing plugin to $PLUGIN_DIR ..."
mkdir -p "$PLUGIN_DIR"
cp "$SCRIPT_DIR"/rlm/*.py "$PLUGIN_DIR/"
cp "$SCRIPT_DIR"/rlm/requirements.txt "$PLUGIN_DIR/"
info "Plugin files copied."

# --- 5. Set up CLAUDE.md ---
mkdir -p "$HOME/.claude"
if [ -f "$CLAUDE_MD" ] && grep -q "$RLM_MARKER" "$CLAUDE_MD" 2>/dev/null; then
    info "CLAUDE.md already contains RLM instructions — skipping."
else
    info "Setting up CLAUDE.md ..."
    # Extract CLAUDE.md content from rlm_prompts.py
    python3 -c "
import sys
sys.path.insert(0, '$PLUGIN_DIR')
from rlm_prompts import CLAUDE_MD_CONTENT
print(CLAUDE_MD_CONTENT)
" > /tmp/rlm_claude_md.tmp

    if [ -f "$CLAUDE_MD" ]; then
        # Append to existing CLAUDE.md
        echo "" >> "$CLAUDE_MD"
        cat /tmp/rlm_claude_md.tmp >> "$CLAUDE_MD"
        info "Appended RLM instructions to existing CLAUDE.md."
    else
        cp /tmp/rlm_claude_md.tmp "$CLAUDE_MD"
        info "Created CLAUDE.md with RLM instructions."
    fi
    rm -f /tmp/rlm_claude_md.tmp
fi

# --- 6. Configure shell profile ---
# Detect shell
if [ -n "${ZSH_VERSION:-}" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    PROFILE="$HOME/.zshrc"
else
    PROFILE="$HOME/.bashrc"
    [ ! -f "$PROFILE" ] && PROFILE="$HOME/.bash_profile"
fi

info "Configuring $PROFILE ..."

add_line_if_missing() {
    local line="$1"
    local file="$2"
    if ! grep -qF "$line" "$file" 2>/dev/null; then
        echo "$line" >> "$file"
        return 0
    fi
    return 1
fi

# Ensure file exists
touch "$PROFILE"

# Add RLM block
CHANGED=0
if ! grep -q "RLM.*scaffold" "$PROFILE" 2>/dev/null; then
    echo "" >> "$PROFILE"
    echo "# RLM (Recursive Language Model) scaffold" >> "$PROFILE"
    CHANGED=1
fi

if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    if ! grep -q "ANTHROPIC_API_KEY" "$PROFILE" 2>/dev/null; then
        echo "export ANTHROPIC_API_KEY=\"$ANTHROPIC_API_KEY\"" >> "$PROFILE"
        CHANGED=1
    fi
fi

if add_line_if_missing 'export PYTHONPATH="$HOME/.claude/plugins/rlm:$PYTHONPATH"' "$PROFILE"; then
    CHANGED=1
fi

if add_line_if_missing 'claude-rlm() { python3 "$HOME/.claude/plugins/rlm/rlm_cli.py" "$@"; }' "$PROFILE"; then
    CHANGED=1
fi

if [ "$CHANGED" -eq 1 ]; then
    info "Shell profile updated."
else
    info "Shell profile already configured — no changes needed."
fi

# --- 7. Verify ---
echo ""
info "Installation complete!"
echo ""
echo "  Plugin location:  $PLUGIN_DIR"
echo "  CLAUDE.md:        $CLAUDE_MD"
echo "  Shell profile:    $PROFILE"
echo ""
echo "  To activate now, run:"
echo ""
echo "    source $PROFILE"
echo ""
echo "  Then test with:"
echo ""
echo "    python3 -c \"from rlm_helper import llm_query; print(llm_query('Say hi'))\""
echo "    echo 'Hello world' | claude-rlm 'What does this say?'"
echo ""
