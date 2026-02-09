"""
Centralized error handling utilities.

This module provides decorators and utilities for consistent error handling
across the application, particularly for UI methods that interact with users.
"""

import functools
import logging
from typing import Callable, Optional, Any
from PySide6.QtWidgets import QMessageBox, QWidget

from constants import UIConstants, ErrorMessages

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('meesho_sales.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def handle_ui_errors(
    success_message: Optional[str] = None,
    error_title: str = "Error",
    success_title: str = "Success",
    log_errors: bool = True,
    show_success_dialog: bool = True
) -> Callable:
    """
    Decorator for consistent error handling in UI methods.
    
    This decorator:
    1. Catches all exceptions from the decorated function
    2. Shows user-friendly error dialogs
    3. Logs errors for debugging
    4. Optionally shows success messages
    5. Appends messages to debug output (if available)
    
    Args:
        success_message: Message to show on successful completion
        error_title: Title for error dialog (default: "Error")
        success_title: Title for success dialog (default: "Success")
        log_errors: Whether to log errors (default: True)
        show_success_dialog: Whether to show success dialog (default: True)
    
    Returns:
        Decorated function with error handling
    
    Example:
        >>> class MyApp:
        ...     @handle_ui_errors(success_message="✅ Data imported!")
        ...     def import_data(self):
        ...         # ... import logic ...
        ...         return result
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self: Any, *args, **kwargs):
            try:
                # Execute the function
                result = func(self, *args, **kwargs)
                
                # Show success message if provided
                if success_message and show_success_dialog:
                    QMessageBox.information(
                        self if isinstance(self, QWidget) else None,
                        success_title,
                        success_message
                    )
                
                # Append to debug output if available
                if hasattr(self, 'debug_output') and success_message:
                    self.debug_output.append(success_message)
                
                # Log success
                if log_errors:
                    logger.info(f"{func.__name__} completed successfully")
                
                return result
                
            except FileNotFoundError as e:
                error_msg = f"{UIConstants.ICON_ERROR} {ErrorMessages.FILE_NOT_FOUND}\n\nDetails: {str(e)}"
                _show_error_dialog(self, error_title, error_msg)
                if log_errors:
                    logger.error(f"File not found in {func.__name__}: {e}", exc_info=True)
                return None
                
            except PermissionError as e:
                error_msg = f"{UIConstants.ICON_ERROR} {ErrorMessages.PERMISSION_DENIED}\n\nDetails: {str(e)}"
                _show_error_dialog(self, error_title, error_msg)
                if log_errors:
                    logger.error(f"Permission error in {func.__name__}: {e}", exc_info=True)
                return None
                
            except ValueError as e:
                error_msg = f"{UIConstants.ICON_ERROR} Invalid data format\n\nDetails: {str(e)}"
                _show_error_dialog(self, error_title, error_msg)
                if log_errors:
                    logger.error(f"Value error in {func.__name__}: {e}", exc_info=True)
                return None
                
            except Exception as e:
                # Generic error handling
                error_msg = f"{UIConstants.ICON_ERROR} An error occurred\n\nDetails: {str(e)}"
                _show_error_dialog(self, error_title, error_msg)
                if log_errors:
                    logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
                return None
        
        return wrapper
    return decorator


def handle_export_errors(file_type: str = "File") -> Callable:
    """
    Specialized decorator for export operations.
    
    Args:
        file_type: Type of file being exported (e.g., "B2B CSV", "HSN Report")
    
    Returns:
        Decorated function with export-specific error handling
    
    Example:
        >>> @handle_export_errors(file_type="B2B CSV")
        ... def export_b2b(self):
        ...     # ... export logic ...
        ...     return "b2b.csv"
    """
    success_msg = f"{UIConstants.ICON_SUCCESS} {file_type} exported successfully"
    return handle_ui_errors(
        success_message=success_msg,
        error_title=f"{file_type} Export Error",
        show_success_dialog=True
    )


def handle_import_errors(source: str = "Data") -> Callable:
    """
    Specialized decorator for import operations.
    
    Args:
        source: Data source being imported (e.g., "Amazon B2B", "Meesho ZIP")
    
    Returns:
        Decorated function with import-specific error handling
    
    Example:
        >>> @handle_import_errors(source="Amazon B2B")
        ... def import_amazon_b2b(self):
        ...     # ... import logic ...
        ...     return records_count
    """
    success_msg = f"{UIConstants.ICON_SUCCESS} {source} imported successfully"
    return handle_ui_errors(
        success_message=success_msg,
        error_title=f"{source} Import Error",
        show_success_dialog=True
    )


def _show_error_dialog(parent: Any, title: str, message: str) -> None:
    """
    Show error dialog and append to debug output if available.
    
    Args:
        parent: Parent widget (self from calling method)
        title: Dialog title
        message: Error message to display
    """
    # Show error dialog
    QMessageBox.critical(
        parent if isinstance(parent, QWidget) else None,
        title,
        message
    )
    
    # Append to debug output if available
    if hasattr(parent, 'debug_output'):
        parent.debug_output.append(message)


def safe_division(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default on division by zero.
    
    Args:
        numerator: Number to divide
        denominator: Number to divide by
        default: Value to return if denominator is zero (default: 0.0)
    
    Returns:
        Result of division or default value
    
    Example:
        >>> safe_division(10, 2)
        5.0
        >>> safe_division(10, 0)
        0.0
        >>> safe_division(10, 0, default=100)
        100.0
    """
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default


def safe_float_conversion(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float, returning default on failure.
    
    Args:
        value: Value to convert
        default: Value to return on conversion failure (default: 0.0)
    
    Returns:
        Float value or default
    
    Example:
        >>> safe_float_conversion("123.45")
        123.45
        >>> safe_float_conversion("invalid")
        0.0
        >>> safe_float_conversion(None, default=100.0)
        100.0
    """
    try:
        if value is None or value == '' or str(value).lower() == 'nan':
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """
    Safely convert value to integer, returning default on failure.
    
    Args:
        value: Value to convert
        default: Value to return on conversion failure (default: 0)
    
    Returns:
        Integer value or default
    
    Example:
        >>> safe_int_conversion("123")
        123
        >>> safe_int_conversion("12.8")
        12
        >>> safe_int_conversion("invalid")
        0
    """
    try:
        if value is None or value == '' or str(value).lower() == 'nan':
            return default
        return int(float(value))  # Convert to float first to handle "12.0"
    except (TypeError, ValueError):
        return default


def validate_date_range(start_date, end_date) -> bool:
    """
    Validate that date range is logical (start before end).
    
    Args:
        start_date: Start date
        end_date: End date
    
    Returns:
        True if valid, False otherwise
    
    Example:
        >>> from datetime import datetime
        >>> validate_date_range(datetime(2025, 1, 1), datetime(2025, 12, 31))
        True
        >>> validate_date_range(datetime(2025, 12, 31), datetime(2025, 1, 1))
        False
    """
    try:
        return start_date < end_date
    except (TypeError, AttributeError):
        return False


def log_operation(operation_name: str, details: str = "") -> None:
    """
    Log an operation for debugging/audit purposes.
    
    Args:
        operation_name: Name of the operation
        details: Additional details about the operation
    
    Example:
        >>> log_operation("Data Import", "Imported 1000 records from Amazon B2B")
    """
    message = f"{operation_name}"
    if details:
        message += f" - {details}"
    logger.info(message)


# =============================================================================
# CONTEXT MANAGER FOR OPERATIONS
# =============================================================================

class OperationContext:
    """
    Context manager for operations with automatic logging and error handling.
    
    Example:
        >>> with OperationContext("Importing Data", debug_output=self.debug_output):
        ...     # ... import operation ...
        ...     pass
    """
    
    def __init__(self, operation_name: str, debug_output=None):
        """
        Initialize operation context.
        
        Args:
            operation_name: Name of the operation
            debug_output: QTextEdit widget for debug output (optional)
        """
        self.operation_name = operation_name
        self.debug_output = debug_output
        self.start_time = None
    
    def __enter__(self):
        """Start operation."""
        from datetime import datetime
        self.start_time = datetime.now()
        
        msg = f"{UIConstants.ICON_LOADING} Starting: {self.operation_name}"
        logger.info(msg)
        if self.debug_output:
            self.debug_output.append(msg)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        End operation with logging.
        
        Returns:
            False to propagate exceptions (don't suppress)
        """
        from datetime import datetime
        duration = datetime.now() - self.start_time if self.start_time else None
        
        if exc_type is None:
            # Success
            msg = f"{UIConstants.ICON_SUCCESS} Completed: {self.operation_name}"
            if duration:
                msg += f" (took {duration.total_seconds():.2f}s)"
            logger.info(msg)
            if self.debug_output:
                self.debug_output.append(msg)
        else:
            # Error
            msg = f"{UIConstants.ICON_ERROR} Failed: {self.operation_name} - {exc_val}"
            logger.error(msg, exc_info=True)
            if self.debug_output:
                self.debug_output.append(msg)
        
        return False  # Don't suppress exceptions
