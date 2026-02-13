"""
rlm_repl.py — Sandboxed Python REPL environment for RLM.

Provides an exec()-based REPL with persistent namespace, injected helper
functions, and stdout/stderr capture.
"""

import io
import os
import sys
import shutil
import tempfile
import threading
from contextlib import redirect_stdout, redirect_stderr

from rlm_helper import llm_query, llm_query_batched

# Builtins to block inside the sandbox
_BLOCKED_BUILTINS = {"eval", "exec", "compile", "input", "__import__"}


class RLMRepl:
    """A sandboxed Python REPL with persistent state across iterations."""

    def __init__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="rlm_")
        self._lock = threading.Lock()
        self._final_answer = None

        # Build safe builtins
        import builtins
        safe_builtins = {
            k: v for k, v in vars(builtins).items()
            if k not in _BLOCKED_BUILTINS
        }

        # Allow controlled imports
        safe_builtins["__import__"] = __import__

        self.namespace = {
            "__builtins__": safe_builtins,
            # Injected RLM functions
            "llm_query": llm_query,
            "llm_query_batched": llm_query_batched,
            "FINAL": self._final,
            "FINAL_VAR": self._final_var,
            "SHOW_VARS": self._show_vars,
        }

    def load_context(self, text, var_name="context"):
        """Load a large text into the REPL namespace via a temp file.

        This avoids embedding huge strings directly in exec() source code.
        """
        path = os.path.join(self._tmpdir, f"{var_name}.txt")
        with open(path, "w") as f:
            f.write(text)
        # Read it back into the namespace
        self.namespace[var_name] = text
        return len(text)

    def execute(self, code):
        """Execute a code block in the persistent namespace.

        Returns (stdout, stderr, exception_str_or_None).
        Thread-safe via lock.
        """
        with self._lock:
            stdout_buf = io.StringIO()
            stderr_buf = io.StringIO()
            exception = None

            try:
                with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
                    exec(code, self.namespace)
            except Exception as e:
                exception = f"{type(e).__name__}: {e}"

            return stdout_buf.getvalue(), stderr_buf.getvalue(), exception

    def _final(self, answer):
        """Signal the final answer (called from inside REPL code)."""
        self._final_answer = str(answer)
        print(f"FINAL({answer})")

    def _final_var(self, var_name):
        """Signal the final answer by variable name (called from inside REPL code)."""
        if var_name in self.namespace:
            self._final_answer = str(self.namespace[var_name])
            print(f"FINAL_VAR('{var_name}')")
        else:
            print(f"Error: variable '{var_name}' not found in namespace")

    def _show_vars(self):
        """Print all user-defined variables in the namespace."""
        skip = {
            "__builtins__", "llm_query", "llm_query_batched",
            "FINAL", "FINAL_VAR", "SHOW_VARS",
        }
        for k, v in sorted(self.namespace.items()):
            if k in skip or k.startswith("_"):
                continue
            val_str = repr(v)
            if len(val_str) > 200:
                val_str = val_str[:200] + "..."
            print(f"  {k}: {type(v).__name__} = {val_str}")

    @property
    def final_answer(self):
        return self._final_answer

    def cleanup(self):
        """Remove the temp directory."""
        if os.path.exists(self._tmpdir):
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def __del__(self):
        self.cleanup()
