"""Logging setup for predictable, secret-conscious application logs.

Author: Karthikeya
Architectural layer: core observability.

Phase 1 establishes a stable baseline. Future phases may add structured fields
such as correlation_id and recovery_case_id without changing call sites.
"""

import logging

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging once using the requested severity level.

    The formatter intentionally excludes configuration values and request bodies;
    callers must never log credentials, payment data, or full customer payloads.
    """

    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=_LOG_FORMAT)
