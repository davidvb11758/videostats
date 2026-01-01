"""
Logging configuration for VideoStats application.
Provides separate log files for different log levels.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from utils import get_user_data_dir


def setup_logging(level=logging.INFO, log_to_console=True):
    """
    Configure logging with separate files for different log levels.
    
    Args:
        level: Minimum log level to display (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_console: Whether to also log to console
    
    Returns:
        Logger instance
    """
    # Get log directory
    log_dir = get_user_data_dir() / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels at root
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # DEBUG log file - all debug messages
    debug_handler = RotatingFileHandler(
        log_dir / 'debug.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(detailed_formatter)
    debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)
    root_logger.addHandler(debug_handler)
    
    # INFO log file - info and above (info, warning, error, critical)
    info_handler = RotatingFileHandler(
        log_dir / 'info.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(info_handler)
    
    # WARNING log file - warnings and errors only
    warning_handler = RotatingFileHandler(
        log_dir / 'warnings.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10  # Keep more warning logs
    )
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(warning_handler)
    
    # ERROR log file - errors and critical only
    error_handler = RotatingFileHandler(
        log_dir / 'errors.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=20  # Keep many error logs
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)
    
    # Console handler - based on level parameter
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)
    
    # Create module logger
    logger = logging.getLogger('videostats')
    logger.info(f"Logging initialized. Log directory: {log_dir}")
    logger.info(f"Console log level: {logging.getLevelName(level)}")
    
    return logger


def get_logger(name=None):
    """
    Get a logger instance for a module.
    
    Args:
        name: Logger name (usually __name__). If None, returns root logger.
    
    Returns:
        Logger instance
    """
    if name is None:
        return logging.getLogger('videostats')
    return logging.getLogger(f'videostats.{name}')


# Initialize logging on import (can be overridden later)
# Default to INFO level for console, but all levels go to files
if not logging.getLogger().handlers:
    setup_logging(level=logging.INFO)

