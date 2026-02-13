#!/usr/bin/env python3
"""
rlm_cli.py — Standalone RLM CLI implementing Algorithm 1 from the paper.

Usage:
    echo "input" | rlm "query"
    rlm --file input.txt "query"
    rlm "query"  # interactive, reads from stdin
"""

import argparse
import sys
import os

from rlm_helper import llm_query
from rlm_repl import RLMRepl
from rlm_prompts import STANDALONE_SYSTEM_PROMPT
from rlm_parsing import find_code_blocks, find_final_answer, truncate_output

ROOT_MODEL = "claude-opus-4-6"
MAX_ITERATIONS = 15
MAX_OUTPUT_CHARS = 20000


def log(msg, verbose=True):
    if verbose:
        print(msg, file=sys.stderr)


def build_context_message(context, query):
    """Build the initial user message with context metadata."""
    preview_len = min(2000, len(context))
    return (
        f"## Task\n{query}\n\n"
        f"## Context\n"
        f"The input has been loaded into the `context` variable.\n"
        f"- Length: {len(context):,} characters\n"
        f"- Lines: {len(context.splitlines()):,}\n"
        f"- Preview (first {preview_len} chars):\n"
        f"```\n{context[:preview_len]}\n```"
    )


def run_rlm(query, context, verbose=False):
    """Run the RLM loop: LLM generates code, REPL executes, repeat until FINAL.

    Returns the final answer string.
    """
    repl = RLMRepl()
    repl.load_context(context)

    # Message history for the root LLM
    messages = [
        {"role": "user", "content": build_context_message(context, query)},
    ]

    answer = None

    try:
        for iteration in range(1, MAX_ITERATIONS + 1):
            log(f"\n--- Iteration {iteration}/{MAX_ITERATIONS} ---", verbose)

            # Call root LLM
            log("Calling root LLM...", verbose)
            response = llm_query(
                prompt=None,  # We'll pass messages directly
                model=ROOT_MODEL,
                max_tokens=4096,
                system=STANDALONE_SYSTEM_PROMPT,
            ) if False else _call_root_llm(messages, verbose)

            messages.append({"role": "assistant", "content": response})

            # Extract code blocks
            code_blocks = find_code_blocks(response)

            if not code_blocks:
                log("No code blocks found. Checking for direct FINAL...", verbose)
                # Check if response itself contains a final answer
                fa = find_final_answer(response, repl)
                if fa:
                    answer = fa
                    break
                # Ask the LLM to produce code
                messages.append({
                    "role": "user",
                    "content": (
                        "Please write code in a ```repl``` block to make progress "
                        "on the task. Remember to call FINAL() when you have the answer."
                    ),
                })
                continue

            # Execute each code block
            all_output = []
            for i, code in enumerate(code_blocks):
                log(f"Executing code block {i+1}/{len(code_blocks)}...", verbose)
                stdout, stderr, exception = repl.execute(code)

                block_output = ""
                if stdout:
                    block_output += stdout
                if stderr:
                    block_output += f"\n[stderr]\n{stderr}"
                if exception:
                    block_output += f"\n[exception]\n{exception}"

                if block_output:
                    all_output.append(block_output)

                if verbose and block_output:
                    preview = block_output[:500]
                    log(f"Output preview: {preview}", verbose)

            # Check for FINAL answer
            if repl.final_answer is not None:
                answer = repl.final_answer
                log(f"FINAL answer received (length: {len(answer)})", verbose)
                break

            combined_output = "\n".join(all_output) if all_output else "(no output)"

            # Also check output text for FINAL patterns
            fa = find_final_answer(combined_output, repl)
            if fa:
                answer = fa
                break

            # Truncate and add to history
            truncated = truncate_output(combined_output, MAX_OUTPUT_CHARS)
            messages.append({
                "role": "user",
                "content": f"REPL output:\n```\n{truncated}\n```",
            })

        if answer is None:
            log("Max iterations reached without FINAL answer.", verbose)
            # Use the last output as a fallback
            answer = "(RLM reached max iterations without producing a final answer)"

    finally:
        repl.cleanup()

    return answer


def _call_root_llm(messages, verbose=False):
    """Call the root LLM with full message history."""
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set.")

    client = anthropic.Anthropic(api_key=api_key)

    log(f"Sending {len(messages)} messages to {ROOT_MODEL}...", verbose)

    response = client.messages.create(
        model=ROOT_MODEL,
        max_tokens=4096,
        system=STANDALONE_SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text


def main():
    parser = argparse.ArgumentParser(
        description="RLM — Recursive Language Model CLI",
        epilog="Examples:\n"
               "  echo 'hello' | rlm 'What does this say?'\n"
               "  rlm --file doc.txt 'Summarize this'\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("query", help="The question or task to perform on the input")
    parser.add_argument("--file", "-f", help="Read input from a file instead of stdin")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show progress on stderr")

    args = parser.parse_args()

    # Read input
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file) as f:
            context = f.read()
    elif not sys.stdin.isatty():
        context = sys.stdin.read()
    else:
        print("Error: No input provided. Pipe input or use --file.", file=sys.stderr)
        sys.exit(1)

    if not context.strip():
        print("Error: Input is empty.", file=sys.stderr)
        sys.exit(1)

    log(f"Input: {len(context):,} chars, {len(context.splitlines()):,} lines", args.verbose)

    answer = run_rlm(args.query, context, verbose=args.verbose)
    print(answer)


if __name__ == "__main__":
    main()
