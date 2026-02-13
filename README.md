# RLM Scaffold for Claude Code

An implementation of the **Recursive Language Model** pattern ([Zhang et al., MIT, 2026](https://arxiv.org/abs/2602.05568)) for [Claude Code](https://docs.anthropic.com/en/docs/claude-code). RLM dramatically improves LLM performance on long-context tasks by offloading input to a REPL and having the model write code to inspect, chunk, and recursively sub-query itself.

## What It Does

Instead of feeding a 100K-token document directly into the context window, RLM:

1. Stores the input in a Python variable (`context`)
2. The LLM writes code to inspect and chunk the input
3. Sub-LLM calls analyze each chunk independently (in parallel)
4. Results are synthesized into a final answer
5. Repeat until done (up to 15 iterations)

This outperforms vanilla LLMs by up to **2x** on long-context benchmarks.

## Two Integration Modes

### Mode 1 — Claude Code (Interactive)

When using `claude` interactively, Claude automatically knows about the RLM helper (via `~/.claude/CLAUDE.md`) and can use it through its Bash tool:

```
> Analyze all the Python files in this project and find security issues

Claude will automatically use rlm_helper to chunk files, sub-query for
each file's issues, and synthesize a report.
```

### Mode 2 — Standalone CLI

`claude-rlm` runs the full RLM loop independently:

```bash
# Pipe input
cat large_document.txt | claude-rlm "Summarize the key arguments"

# File flag
claude-rlm --file codebase.py "Find all TODO comments and categorize them"

# Verbose mode (shows iterations on stderr)
cat data.csv | claude-rlm -v "What trends do you see in this data?"
```

## Quick Install

```bash
git clone <this-repo> rlm-scaffold
cd rlm-scaffold
./install.sh
```

The install script will:
1. Check for Python 3
2. Install the `anthropic` SDK
3. Prompt for your Anthropic API key (if not already set)
4. Copy plugin files to `~/.claude/plugins/rlm/`
5. Create/update `~/.claude/CLAUDE.md` with RLM instructions
6. Add `PYTHONPATH`, `ANTHROPIC_API_KEY`, and the `claude-rlm` function to your shell profile

After installing, activate with:

```bash
source ~/.zshrc  # or ~/.bashrc
```

## Manual Install

If you prefer to install manually:

### 1. Copy Plugin Files

```bash
mkdir -p ~/.claude/plugins/rlm
cp rlm/*.py ~/.claude/plugins/rlm/
cp rlm/requirements.txt ~/.claude/plugins/rlm/
```

### 2. Install Dependencies

```bash
pip install anthropic>=0.79.0
```

### 3. Set Up Shell Profile

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
export ANTHROPIC_API_KEY="your-key-here"
export PYTHONPATH="$HOME/.claude/plugins/rlm:$PYTHONPATH"
claude-rlm() { python3 "$HOME/.claude/plugins/rlm/rlm_cli.py" "$@"; }
```

### 4. Set Up CLAUDE.md

Copy the Claude Code instructions:

```bash
cp ~/.claude/plugins/rlm/rlm_prompts.py /tmp/
python3 -c "
import sys; sys.path.insert(0, '/tmp')
from rlm_prompts import CLAUDE_MD_CONTENT; print(CLAUDE_MD_CONTENT)
" > ~/.claude/CLAUDE.md
```

Or manually create `~/.claude/CLAUDE.md` — see [CLAUDE.md content](#claudemd-content) below.

## Verify Installation

```bash
# 1. API connectivity
python3 -c "from rlm_helper import llm_query; print(llm_query('Say hi'))"

# 2. Batched queries
python3 -c "
from rlm_helper import llm_query_batched
results = llm_query_batched(['What is 2+2?', 'Capital of France?', 'Color of sky?'])
for r in results: print(r)
"

# 3. Standalone CLI
echo "The Eiffel Tower is in Paris, France." | claude-rlm "What country is mentioned?"

# 4. Claude Code integration
claude -p "Use the RLM helper to query a sub-LLM for a joke"
```

## Architecture

```
~/.claude/plugins/rlm/
├── rlm_helper.py      # llm_query() and llm_query_batched() — Anthropic API bridge
├── rlm_cli.py         # Standalone RLM CLI (full iteration loop)
├── rlm_repl.py        # Sandboxed Python REPL with injected functions
├── rlm_prompts.py     # System prompts for standalone + CLAUDE.md
├── rlm_parsing.py     # FINAL/FINAL_VAR extraction, code block parsing
└── requirements.txt   # anthropic>=0.79.0
```

### Module Details

| Module | Purpose |
|--------|---------|
| `rlm_helper.py` | Anthropic API bridge. `llm_query()` for single calls, `llm_query_batched()` for parallel calls (up to 8 workers). Lazy-initialized client with exponential backoff retry. |
| `rlm_repl.py` | `exec()`-based REPL with persistent namespace. Injects `llm_query`, `llm_query_batched`, `FINAL()`, `FINAL_VAR()`, `SHOW_VARS()` into the execution environment. |
| `rlm_cli.py` | Implements Algorithm 1 from the paper. Root model (Opus 4.6) generates code in `` ```repl``` `` blocks, REPL executes them, output is truncated and fed back, loop until `FINAL()`. |
| `rlm_prompts.py` | System prompts teaching the LLM how to use the REPL, chunking strategies, and the FINAL protocol. |
| `rlm_parsing.py` | Regex extraction of `FINAL()`, `FINAL_VAR()`, `` ```repl``` `` code blocks, and output truncation (20K char limit). |

### Models Used

| Role | Model | Purpose |
|------|-------|---------|
| Root LLM (CLI) | Claude Opus 4.6 | Orchestrates the RLM loop, generates REPL code |
| Sub-LLM calls | Claude Sonnet 4.5 | Processes individual chunks (fast, cost-effective) |

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | — | Your Anthropic API key |
| `PYTHONPATH` | Yes | — | Must include `~/.claude/plugins/rlm` |

### CLI Options

```
usage: rlm_cli.py [-h] [--file FILE] [--verbose] query

positional arguments:
  query                 The question or task to perform on the input

options:
  -h, --help            show this help message and exit
  --file FILE, -f FILE  Read input from a file instead of stdin
  --verbose, -v         Show progress on stderr
```

## CLAUDE.md Content

The install script creates `~/.claude/CLAUDE.md` with instructions that teach Claude Code:

- When to use RLM (large inputs, multi-doc analysis)
- How to call `llm_query` and `llm_query_batched` via the Bash tool
- The chunk-process-synthesize workflow pattern
- Ready-to-use code snippets

## Prerequisites

- **macOS or Linux** (tested on macOS)
- **Python 3.9+**
- **Anthropic API key** — get one at [console.anthropic.com](https://console.anthropic.com/settings/keys)
- **Claude Code** (for Mode 1 integration) — install from [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code)

## Uninstall

```bash
# Remove plugin files
rm -rf ~/.claude/plugins/rlm

# Remove RLM section from CLAUDE.md (or delete the file)
# Edit ~/.claude/CLAUDE.md and remove the RLM block

# Remove from shell profile — delete these lines from ~/.zshrc or ~/.bashrc:
#   export ANTHROPIC_API_KEY="..."
#   export PYTHONPATH="$HOME/.claude/plugins/rlm:$PYTHONPATH"
#   claude-rlm() { ... }
```

## License

MIT
