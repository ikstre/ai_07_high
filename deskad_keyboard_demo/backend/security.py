"""Centralized secret-handling helpers.

Goals:
- One single source of truth for which env vars hold secrets.
- Never print or log secret values; only their presence and (optionally) a
  short masked tail for debugging.
- A logging filter that scrubs values seen in environment variables out of any
  log record, even if a third-party library tries to print them.

Importing this module has no side effects. Call install_secret_log_filter()
once during app startup to attach the filter to the root logger.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from typing import Iterable


# Names of environment variables whose value must never appear in logs or
# responses. Keep this list as the single source of truth.
SENSITIVE_ENV_KEYS: tuple[str, ...] = (
    "GITHUB_TOKEN",
    "OPENAI_API_KEY",
    "HYPERCLOVA_API_KEY",
    "HYPERCLOVA_APIGW_KEY",
    "KANANA_API_KEY",
    "MIDM_API_KEY",
    "HF_TOKEN",
    "HUGGINGFACEHUB_API_TOKEN",
    "ANTHROPIC_API_KEY",
)

# Substrings that indicate a sensitive value even when not in SENSITIVE_ENV_KEYS.
_SENSITIVE_NAME_HINTS: tuple[str, ...] = ("TOKEN", "API_KEY", "SECRET", "PASSWORD")

# Token-shaped patterns we still want to mask even if their literal didn't come
# through env vars (e.g. a hard-coded token someone pasted into a log line).
_TOKEN_SHAPED_PATTERNS: tuple[re.Pattern, ...] = (
    # GitHub PATs
    re.compile(r"\bghp_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"\bgho_[A-Za-z0-9]{30,}\b"),
    # OpenAI-style
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
    # Anthropic
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    # HuggingFace
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    # Generic Bearer headers
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.=]{16,}"),
)


def is_sensitive_key(key: str) -> bool:
    if not key:
        return False
    upper = key.upper()
    if upper in SENSITIVE_ENV_KEYS:
        return True
    return any(hint in upper for hint in _SENSITIVE_NAME_HINTS)


def mask_value(value: object, *, keep_tail: int = 0) -> str:
    """Return a non-reversible status string for a secret value.

    keep_tail > 0 only used for debugging in non-production paths. By default
    we return one of three constants so logs never carry length or shape.
    """
    if value is None:
        return "missing"
    text = str(value)
    if not text:
        return "missing"
    if keep_tail > 0 and len(text) > keep_tail + 4:
        return f"set(...{text[-keep_tail:]})"
    return "set"


def redact_mapping(mapping: dict, *, extra_sensitive: Iterable[str] = ()) -> dict:
    """Return a copy of the mapping with sensitive values replaced by mask_value()."""
    sensitive = set(SENSITIVE_ENV_KEYS) | {key.upper() for key in extra_sensitive}
    redacted: dict = {}
    for key, value in mapping.items():
        upper = str(key).upper()
        if upper in sensitive or is_sensitive_key(upper):
            redacted[key] = mask_value(value)
        else:
            redacted[key] = value
    return redacted


def _collect_secret_values() -> list[str]:
    """Snapshot current env values for every sensitive key.

    The list contains only the *values* themselves so the logging filter can
    replace any literal occurrence inside a log message. Empty values are
    discarded so we never replace empty strings.
    """
    values: list[str] = []
    for key, value in os.environ.items():
        if not value:
            continue
        if is_sensitive_key(key):
            values.append(value)
    # Longest-first reduces the risk of partially-overlapping replacements.
    values.sort(key=len, reverse=True)
    return values


class SecretLogFilter(logging.Filter):
    """Replace any sensitive env value or token-shaped substring with [REDACTED]."""

    def __init__(self) -> None:
        super().__init__(name="deskad.security.redact")
        self._lock = threading.Lock()
        self._values: list[str] = _collect_secret_values()

    def refresh(self) -> None:
        with self._lock:
            self._values = _collect_secret_values()

    def _scrub(self, text: str) -> str:
        with self._lock:
            values = list(self._values)
        for raw in values:
            if raw and raw in text:
                text = text.replace(raw, "[REDACTED]")
        for pattern in _TOKEN_SHAPED_PATTERNS:
            text = pattern.sub("[REDACTED]", text)
        return text

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if isinstance(record.msg, str):
                record.msg = self._scrub(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {key: self._scrub(str(value)) for key, value in record.args.items()}
                else:
                    record.args = tuple(self._scrub(str(arg)) for arg in record.args)
        except Exception:
            return True
        return True


_FILTER_SINGLETON: SecretLogFilter | None = None


def install_secret_log_filter() -> SecretLogFilter:
    """Attach the redaction filter to the root logger plus common server loggers.

    Idempotent: repeated calls return the same instance and do not duplicate the
    filter on the loggers we have already touched.
    """
    global _FILTER_SINGLETON
    if _FILTER_SINGLETON is None:
        _FILTER_SINGLETON = SecretLogFilter()
    log_filter = _FILTER_SINGLETON

    targets = (
        logging.getLogger(),
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.access"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("fastapi"),
        logging.getLogger("httpx"),
        logging.getLogger("urllib3"),
        logging.getLogger("requests"),
        logging.getLogger("streamlit"),
    )
    for logger in targets:
        if log_filter not in logger.filters:
            logger.addFilter(log_filter)
        for handler in logger.handlers:
            if log_filter not in handler.filters:
                handler.addFilter(log_filter)
    return log_filter
