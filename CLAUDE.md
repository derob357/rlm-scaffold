# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this project.

## Project Overview

RLM Scaffold implements the Recursive Language Model pattern (Zhang et al., MIT, 2026) for improved long-context LLM performance. It works in two modes: as a Claude Code plugin (interactive, via `rlm_helper`) and as a standalone CLI (`rlm`/`claude-rlm`). ~850 LOC across 6 Python modules.

## Tech Stack

- **Language**: Python 3.9+
- **Dependency**: `anthropic>=0.79.0` (only external dep)
- **Root LLM**: `claude-opus-4-6` (orchestration)
- **Sub-LLM**: `claude-sonnet-4-5-20250929` (chunk analysis)
- **License**: MIT

## Installation

```bash
cd rlm-scaffold
./install.sh
```

The installer:
1. Installs `anthropic` SDK
2. Copies plugin files to `~/.claude/plugins/rlm/`
3. Adds `ANTHROPIC_API_KEY`, `PYTHONPATH`, and `rlm()` shell function to shell profile
4. Updates `~/.claude/CLAUDE.md` with RLM usage instructions

## Usage

### Mode 1 — Claude Code Plugin (interactive)

```python
# Available in any Claude Code session after install
from rlm_helper import llm_query, llm_query_batched

result = llm_query("Analyze this code for bugs")
results = llm_query_batched(["prompt1", "prompt2", "prompt3"])  # up to 8 parallel
```

### Mode 2 — Standalone CLI

```bash
cat large_doc.txt | rlm "Summarize the key arguments"
rlm --file codebase.py "Find all security issues"
rlm -v "What trends do you see?" < data.csv   # verbose (shows iterations)
```

## Architecture

### Module Map

| Module | Lines | Purpose |
|--------|-------|---------|
| `rlm/rlm_helper.py` | 106 | LLM API bridge — `llm_query()` and `llm_query_batched()` (8 parallel workers, exponential backoff) |
| `rlm/rlm_cli.py` | 207 | Algorithm 1 implementation — root model generates code, REPL executes, iterates until `FINAL()` (max 15 turns) |
| `rlm/rlm_repl.py` | 118 | Sandboxed `exec()`-based Python REPL — injects `llm_query`, `FINAL()`, `FINAL_VAR()`, `SHOW_VARS()`. Blocks unsafe builtins. |
| `rlm/rlm_prompts.py` | 170 | System prompts for the root LLM + CLAUDE.md content for plugin mode |
| `rlm/rlm_parsing.py` | 64 | Regex utilities — extract ` ```repl``` ` code blocks, detect `FINAL()` calls, truncate output (20K char limit) |
| `rlm/requirements.txt` | 1 | `anthropic>=0.79.0` |

### Core Pattern: Chunk-Process-Synthesize

```python
# 1. Chunk input
chunks = [context[i:i+chunk_size] for i in range(0, len(context), chunk_size)]

# 2. Process in parallel via sub-LLM
prompts = [f"Analyze:\n\n{chunk}" for chunk in chunks]
results = llm_query_batched(prompts)

# 3. Synthesize via sub-LLM
final = llm_query(f"Synthesize:\n\n{'\n---\n'.join(results)}")
FINAL(final)
```

### CLI Constants

- `ROOT_MODEL`: `claude-opus-4-6`
- `MAX_ITERATIONS`: 15
- `MAX_OUTPUT_CHARS`: 20,000 (REPL output truncation)
- `DEFAULT_MODEL` (helper): `claude-sonnet-4-5-20250929`
- `MAX_RETRIES`: 5 (exponential backoff)
- `BATCH_WORKERS`: 8 (max parallel sub-queries)

## Environment Variables

- `ANTHROPIC_API_KEY` — Required. Anthropic API credentials.
- `PYTHONPATH` — Must include `~/.claude/plugins/rlm` (set by installer).

## Security Notes

- REPL blocks `eval`, `exec`, `compile` builtins to prevent code injection
- Sub-LLM calls use the Anthropic SDK (HTTPS, API key auth)
- Output truncated at 20K chars to prevent context window overflow

## Testing

No formal test suite. Manual verification:

```bash
# Test API connectivity
python3 -c "from rlm_helper import llm_query; print(llm_query('Say hello'))"

# Test batched queries
python3 -c "from rlm_helper import llm_query_batched; print(llm_query_batched(['Say hi', 'Say bye']))"

# Test CLI
echo "The Eiffel Tower is in Paris, France." | rlm "What country is mentioned?"
```
