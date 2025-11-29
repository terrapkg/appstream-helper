# Logging helpers that emit GitHub Actions workflow command syntax when possible.

import logging
import os
import sys
from typing import Dict


class GitHubActionsHandler(logging.Handler):
    """Logging handler that formats records using GitHub Actions workflow commands."""

    _LEVEL_PREFIXES: Dict[int, str] = {
        logging.DEBUG: "::debug::",
        logging.INFO: "::notice::",
        logging.WARNING: "::warning::",
        logging.ERROR: "::error::",
        logging.CRITICAL: "::error::",
    }

    def __init__(self) -> None:
        super().__init__()
        self.stream = sys.stdout
        self.formatter = logging.Formatter("%(message)s")

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        prefix = self._LEVEL_PREFIXES.get(record.levelno, "::notice::")
        if prefix:
            output = f"{prefix}{msg}"
        else:
            output = msg
        self.stream.write(output + "\n")
        self.flush()


def _is_running_in_github_actions() -> bool:
    return os.getenv("GITHUB_ACTIONS") == "true"


def configure_logging() -> logging.Logger:
    """Configure and return the terra-appstream-helper logger."""
    logger = logging.getLogger("terra_appstream_helper")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler: logging.Handler
    if _is_running_in_github_actions():
        handler = GitHubActionsHandler()
    else:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))

    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    """Get a configured logger for the helper."""
    return configure_logging()
