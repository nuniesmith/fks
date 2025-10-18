"""
Core exceptions for FKS project.

Consolidates exceptions from across the application into a centralized module.
All application-specific exceptions should inherit from FKSException.
"""

from typing import Any, Dict, Optional


class FKSException(Exception):
    """Base exception for all FKS application errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """
        Initialize exception.

        Args:
            message: Human-readable error message
            code: Error code for programmatic handling
            details: Additional error details
        """
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary format."""
        return {
            "error": self.__class__.__name__,
            "message": self.message,
            "code": self.code,
            "details": self.details,
        }


# Data-related exceptions


class DataError(FKSException):
    """Base class for data-related errors."""

    pass


class DataFetchError(DataError):
    """Error fetching data from external source."""

    pass


class DataValidationError(DataError):
    """Error validating data."""

    pass


class DataStorageError(DataError):
    """Error storing or retrieving data."""

    pass


# Trading-related exceptions


class TradingError(FKSException):
    """Base class for trading-related errors."""

    pass


class SignalError(TradingError):
    """Error generating or processing trading signal."""

    pass


class StrategyError(TradingError):
    """Error in strategy execution."""

    pass


class BacktestError(TradingError):
    """Error during backtesting."""

    pass


class OrderError(TradingError):
    """Error placing or managing order."""

    pass


# Model/ML-related exceptions


class ModelError(FKSException):
    """Base class for machine learning model errors."""

    pass


class ModelTrainingError(ModelError):
    """Error during model training."""

    pass


class ModelPredictionError(ModelError):
    """Error during model prediction."""

    pass


class ModelNotFoundError(ModelError):
    """Model not found in registry."""

    pass


# Configuration exceptions


class ConfigError(FKSException):
    """Base class for configuration errors."""

    pass


class ConfigValidationError(ConfigError):
    """Configuration validation failed."""

    pass


class ConfigNotFoundError(ConfigError):
    """Configuration key not found."""

    pass


# API/HTTP exceptions


class ApplicationError(FKSException):
    """Base class for application-specific HTTP errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize with HTTP status code."""
        super().__init__(message, code, details)
        self.status_code = status_code


class BadRequestError(ApplicationError):
    """HTTP 400 Bad Request."""

    def __init__(self, message: str = "Bad request", **kwargs):
        """Initialize with default 400 status."""
        super().__init__(message, status_code=400, **kwargs)


class NotFoundError(ApplicationError):
    """HTTP 404 Not Found."""

    def __init__(self, message: str = "Resource not found", **kwargs):
        """Initialize with default 404 status."""
        super().__init__(message, status_code=404, **kwargs)


class ForbiddenError(ApplicationError):
    """HTTP 403 Forbidden."""

    def __init__(self, message: str = "Forbidden", **kwargs):
        """Initialize with default 403 status."""
        super().__init__(message, status_code=403, **kwargs)


class UnauthorizedError(ApplicationError):
    """HTTP 401 Unauthorized."""

    def __init__(self, message: str = "Unauthorized", **kwargs):
        """Initialize with default 401 status."""
        super().__init__(message, status_code=401, **kwargs)


class ConflictError(ApplicationError):
    """HTTP 409 Conflict."""

    def __init__(self, message: str = "Conflict", **kwargs):
        """Initialize with default 409 status."""
        super().__init__(message, status_code=409, **kwargs)


# Circuit breaker exceptions


class CircuitBreakerError(FKSException):
    """Base class for circuit breaker errors."""

    pass


class CircuitOpenError(CircuitBreakerError):
    """Circuit is open and not accepting requests."""

    def __init__(
        self,
        message: str = "Circuit breaker is open",
        circuit_name: str | None = None,
        **kwargs
    ):
        """Initialize with circuit information."""
        super().__init__(message, **kwargs)
        if circuit_name:
            self.details["circuit_name"] = circuit_name


class StateTransitionError(CircuitBreakerError):
    """Error during circuit breaker state transition."""

    pass


# Worker/Task exceptions


class TaskError(FKSException):
    """Base class for asynchronous task errors."""

    pass


class EnsembleError(TaskError):
    """Error in ensemble model execution."""

    pass


# Rate limiting exceptions


class RateLimitError(FKSException):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        **kwargs
    ):
        """Initialize with retry information."""
        super().__init__(message, **kwargs)
        if retry_after:
            self.details["retry_after"] = retry_after


# Database exceptions


class DatabaseError(FKSException):
    """Base class for database errors."""

    pass


class ConnectionError(DatabaseError):
    """Database connection error."""

    pass


class QueryError(DatabaseError):
    """Database query error."""

    pass


# Authentication/Authorization exceptions


class AuthenticationError(FKSException):
    """Authentication failed."""

    pass


class AuthorizationError(FKSException):
    """Authorization/permission denied."""

    pass


__all__ = [
    # Base
    "FKSException",
    # Data
    "DataError",
    "DataFetchError",
    "DataValidationError",
    "DataStorageError",
    # Trading
    "TradingError",
    "SignalError",
    "StrategyError",
    "BacktestError",
    "OrderError",
    # Models
    "ModelError",
    "ModelTrainingError",
    "ModelPredictionError",
    "ModelNotFoundError",
    # Config
    "ConfigError",
    "ConfigValidationError",
    "ConfigNotFoundError",
    # HTTP/API
    "ApplicationError",
    "BadRequestError",
    "NotFoundError",
    "ForbiddenError",
    "UnauthorizedError",
    "ConflictError",
    # Circuit Breaker
    "CircuitBreakerError",
    "CircuitOpenError",
    "StateTransitionError",
    # Tasks
    "TaskError",
    "EnsembleError",
    # Rate Limiting
    "RateLimitError",
    # Database
    "DatabaseError",
    "ConnectionError",
    "QueryError",
    # Auth
    "AuthenticationError",
    "AuthorizationError",
]
