# Development Guide

Use Python 3.11+, a virtual environment, `pip install -e '.[dev]'`, and Node.js with npm. Run `pytest`, `ruff check .`, and `cd frontend && npm run build` before acceptance. Keep imports and modules within their architectural boundaries.

Use focused branches or commits, update tests and documentation with behavior changes, and record durable decisions as ADRs. Never add credentials, real payment calls, or speculative abstractions. The preferred AI-assisted loop is: specify, generate, inspect, run, test, intentionally break where useful, fix, document, accept.
