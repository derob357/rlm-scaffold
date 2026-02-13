"""
rlm_helper.py — LLM API bridge for RLM sub-queries.

Provides llm_query() and llm_query_batched() for recursive sub-LM calls.
Also runnable as: python3 rlm_helper.py "prompt"
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

_client = None

DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_RETRIES = 5
INITIAL_BACKOFF = 1.0
MAX_TOKENS = 4096
BATCH_WORKERS = 8


def _get_client():
    """Lazy-initialize the API client."""
    global _client
    if _client is None:
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it in your shell profile or pass it explicitly."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def llm_query(prompt, model=None, max_tokens=None, system=None):
    """Send a single prompt to the LLM API and return the text response.

    Args:
        prompt: The user message to send.
        model: Model ID (default: DEFAULT_MODEL).
        max_tokens: Max tokens in response (default: 4096).
        system: Optional system prompt.

    Returns:
        The text content of the model's response.
    """
    client = _get_client()
    model = model or DEFAULT_MODEL
    max_tokens = max_tokens or MAX_TOKENS

    messages = [{"role": "user", "content": prompt}]
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kwargs["system"] = system

    backoff = INITIAL_BACKOFF
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            error_str = str(e)
            is_rate_limit = "rate" in error_str.lower() or "429" in error_str
            is_overloaded = "overloaded" in error_str.lower() or "529" in error_str
            if (is_rate_limit or is_overloaded) and attempt < MAX_RETRIES - 1:
                time.sleep(backoff)
                backoff = min(backoff * 2, 60)
                continue
            raise


def llm_query_batched(prompts, model=None, max_tokens=None, system=None):
    """Send multiple prompts in parallel and return results in order.

    Args:
        prompts: List of prompt strings.
        model: Model ID (default: DEFAULT_MODEL).
        max_tokens: Max tokens per response.
        system: Optional system prompt (shared across all calls).

    Returns:
        List of response strings, same order as prompts.
    """
    results = [None] * len(prompts)

    def _query(index, prompt):
        return index, llm_query(prompt, model=model, max_tokens=max_tokens, system=system)

    with ThreadPoolExecutor(max_workers=min(BATCH_WORKERS, len(prompts))) as pool:
        futures = [pool.submit(_query, i, p) for i, p in enumerate(prompts)]
        for future in as_completed(futures):
            idx, result = future.result()
            results[idx] = result

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 rlm_helper.py \"prompt\"", file=sys.stderr)
        sys.exit(1)
    prompt = " ".join(sys.argv[1:])
    print(llm_query(prompt))
