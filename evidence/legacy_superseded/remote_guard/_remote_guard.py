"""Refuse to run a model call against localhost. Import this FIRST in any GPU harness script.

WHY. On 2026-09-06 a diagnostic script omitted OLLAMA_BASE_URL. `va._native_chat_url()` falls back to
`http://localhost:11434`, so a gemma4:26b call meant for a remote L4 went to the laptop instead and
pinned 18.6 GB of weights on a 17 GB machine with keep_alive=-1. It froze. `resume_attribution.sh`
sets the variable correctly; a standalone script written beside it did not, and nothing caught that.

The rule this enforces: a script that intends to use a REMOTE GPU must say so, and must fail loudly
rather than silently falling back to the local machine.

    from _remote_guard import require_remote   # noqa: E402
    require_remote()                           # before importing vep_assistant / evaluate
"""
import os
import sys

LOCAL = ("localhost", "127.0.0.1", "0.0.0.0", "::1")


def require_remote(allow_local=False):
    """Exit unless OLLAMA_BASE_URL points somewhere that is not this machine."""
    url = os.environ.get("OLLAMA_BASE_URL", "")
    if allow_local or os.environ.get("VEP_ALLOW_LOCAL_MODEL") == "1":
        return url
    if not url:
        sys.exit("REFUSING TO RUN: OLLAMA_BASE_URL is unset, so the model call would default to\n"
                 "  http://localhost:11434 and load the model on THIS machine. gemma4:26b is 18.6 GB.\n"
                 "  Set OLLAMA_BASE_URL to the remote endpoint, e.g.\n"
                 "    export OLLAMA_BASE_URL=https://<tunnel>.trycloudflare.com/v1\n"
                 "  Override deliberately with VEP_ALLOW_LOCAL_MODEL=1 only on a machine with headroom.")
    if any(h in url for h in LOCAL):
        sys.exit(f"REFUSING TO RUN: OLLAMA_BASE_URL={url!r} is local. See {__file__} for why.")
    return url


def safe_keep_alive():
    """keep_alive for a call that might touch a shared machine. Never -1 by default.

    -1 means resident forever, which is right on a dedicated eval box and wrong anywhere else.
    """
    return os.environ.get("VEP_KEEP_ALIVE", "5m")
