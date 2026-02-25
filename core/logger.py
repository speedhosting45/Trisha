"""
Professional logger module with ANSI colors and custom SUCCESS level
"""
import logging
import sys
from typing import Optional

# ANSI color codes
class Colors:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Custom log level
SUCCESS_LEVEL_NUM = 25
logging.addLevelName(SUCCESS_LEVEL_NUM, 'SUCCESS')

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    # Level to color mapping
    LEVEL_COLORS = {
        'INFO': Colors.CYAN,
        'SUCCESS': Colors.GREEN,
        'WARNING': Colors.YELLOW,
        'ERROR': Colors.RED,
        'CRITICAL': Colors.RED + Colors.BOLD,
    }
    
    def __init__(self, fmt: str):
        super().__init__(fmt)
        self.FORMAT = fmt
    
    def format(self, record: logging.LogRecord) -> str:
        # Save original values
        original_levelname = record.levelname
        original_msg = record.msg
        original_name = record.name
        
        # Apply color to level name
        level_color = self.LEVEL_COLORS.get(record.levelname, Colors.RESET)
        record.levelname = f"{level_color}[{record.levelname}]{Colors.RESET}"
        
        # Apply color to logger name (PURPLE)
        record.name = f"{Colors.PURPLE}{original_name}{Colors.RESET}"
        
        # Format the message
        result = super().format(record)
        
        # Restore original values
        record.levelname = original_levelname
        record.msg = original_msg
        record.name = original_name
        
        return result

class CustomLogger(logging.Logger):
    """Extended Logger with success method"""
    
    def success(self, msg: str, *args, **kwargs):
        """Log with SUCCESS level"""
        if self.isEnabledFor(SUCCESS_LEVEL_NUM):
            self._log(SUCCESS_LEVEL_NUM, msg, args, **kwargs)

def get_logger(name: str) -> CustomLogger:
    """
    Get a configured logger instance
    
    Args:
        name: Logger name (will appear in purple)
    
    Returns:
        Configured CustomLogger instance
    """
    # Register custom logger class
    logging.setLoggerClass(CustomLogger)
    
    # Get logger
    logger = logging.getLogger(name)
    
    # Only add handler if not already configured
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = ColoredFormatter(
            fmt='%(levelname)s - %(name)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(console_handler)
        
        # Prevent propagation to root logger
        logger.propagate = False
    
    return logger
