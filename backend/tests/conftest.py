"""Local test environment guards.

Set before anything imports protobuf, which is why this lives in conftest.py
rather than in a fixture — pytest loads this module before it collects tests,
and protobuf reads the variable once at import.

**Why:** the container runs `python:3.12-slim` (see the Dockerfile), but a local
machine may be on something newer. On Python 3.14, protobuf 7.x's `upb` C
extension segfaults while materialising messages out of a generator — the exact
shape of consuming a Firestore `.stream()` into a list. It took down a local
Python process mid-session:

    EXC_BAD_ACCESS (SIGSEGV) at 0x10
      _message.abi3.so  PyUpb_Message_New
      Python            gen_iternext
      Python            _list_extend

The deployed service is unaffected — it is pinned to 3.12 — but a local crash
still costs a debugging session, so we force the pure-Python implementation
here. It is slower and completely stable, which is the right trade for a test
suite that runs in a second.

Delete this the day the local interpreter matches the container.
"""
from __future__ import annotations

import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")

# Tests must never reach a real Google API even by accident. An empty key makes
# gemini.client() raise ModelError immediately rather than authenticating with
# whatever happens to be in the developer's shell.
os.environ.setdefault("GEMINI_API_KEY", "")
