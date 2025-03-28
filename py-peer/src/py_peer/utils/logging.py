"""
Logging configuration for py-peer.
"""
import logging
from typing import Optional


def configure_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure logging for the application.
    
    Args:
        verbose: Whether to enable debug logging
        
    Returns:
        A configured logger instance
    """
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("py-peer")
    
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with the given name.
    
    Args:
        name: The name for the logger, defaults to 'py-peer'
        
    Returns:
        A logger instance
    """
    if name is None:
        name = "py-peer"
    return logging.getLogger(name)