"""Structured logging configuration."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import structlog
from logging.handlers import RotatingFileHandler


def configure_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None,
    log_file_max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    log_file_backup_count: int = 5,
) -> None:
    """Configure structured logging with optional file output.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (relative to project root). None or empty string disables file logging.
        log_file_max_bytes: Maximum size of log file before rotation (in bytes)
        log_file_backup_count: Number of backup log files to keep
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_formatter = logging.Formatter("%(message)s")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log_file is specified)
    log_path: Optional[Path] = None
    if log_file:
        try:
            # Convert to Path and resolve relative to project root
            log_path = Path(log_file)
            if not log_path.is_absolute():
                # Assume project root is parent of src/
                project_root = Path(__file__).parent.parent.parent
                log_path = project_root / log_file
            
            # Create log directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create rotating file handler
            file_handler = RotatingFileHandler(
                filename=str(log_path),
                maxBytes=log_file_max_bytes,
                backupCount=log_file_backup_count,
                encoding="utf-8",
            )
            file_handler.setLevel(getattr(logging, log_level.upper()))
            # Use JSON format for file logs (more structured)
            file_formatter = logging.Formatter(
                '{"time": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            # If file logging fails, log warning but continue with console logging
            root_logger.warning(f"Failed to setup file logging: {e}. Continuing with console logging only.")
            log_path = None

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Log that file logging is enabled (after structlog is configured)
    if log_file:
        logger = structlog.get_logger(__name__)
        logger.info("File logging enabled", log_file=str(log_path))


def get_logger(name: str) -> Any:
    """Get logger instance."""
    return structlog.get_logger(name)

