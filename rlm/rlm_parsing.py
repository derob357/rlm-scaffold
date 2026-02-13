"""
rlm_parsing.py — Output parsing utilities for the RLM scaffold.

Handles FINAL/FINAL_VAR extraction, code block parsing, and output truncation.
"""

import re


def find_code_blocks(text):
    """Extract ```repl ... ``` code blocks from LLM output.

    Returns a list of code strings (without the fence markers).
    """
    pattern = r"```repl\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [m.strip() for m in matches]


def find_final_answer(text, repl=None):
    """Check for FINAL() or FINAL_VAR() in text and extract the answer.

    Args:
        text: The text to search (typically REPL stdout).
        repl: Optional RLMRepl instance for FINAL_VAR variable lookup.

    Returns:
        The final answer string, or None if not found.
    """
    # Check for FINAL_VAR(variable_name) first
    match = re.search(r"FINAL_VAR\(\s*['\"](\w+)['\"]\s*\)", text)
    if match and repl is not None:
        var_name = match.group(1)
        value = repl.namespace.get(var_name)
        if value is not None:
            return str(value)

    # Check for FINAL(answer) — may span multiple lines
    match = re.search(r"FINAL\((.*?)\)\s*$", text, re.DOTALL | re.MULTILINE)
    if match:
        answer = match.group(1).strip()
        # Strip surrounding quotes if present
        if len(answer) >= 2 and answer[0] == answer[-1] and answer[0] in ('"', "'"):
            answer = answer[1:-1]
        return answer

    return None


def truncate_output(text, max_length=20000):
    """Truncate output to keep context window manageable.

    If truncated, inserts a marker showing how much was cut.
    """
    if len(text) <= max_length:
        return text

    keep = max_length // 2
    omitted = len(text) - max_length
    return (
        text[:keep]
        + f"\n\n... [{omitted} characters truncated] ...\n\n"
        + text[-keep:]
    )
