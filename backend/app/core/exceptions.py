"""Application-wide exception types."""


class BrenkPlatformError(Exception):
    """Base exception for all application-specific errors."""


class ServiceChannelError(BrenkPlatformError):
    """Base for ServiceChannel API errors."""


class ServiceChannelAuthError(ServiceChannelError):
    """Raised when ServiceChannel authentication fails."""


class ServiceChannelThrottledError(ServiceChannelError):
    """Raised when we hit ServiceChannel rate limits."""

    def __init__(self, message: str, retry_after_seconds: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class ServiceChannelNotFoundError(ServiceChannelError):
    """Raised when a ServiceChannel resource is not found (404)."""


class SyncError(BrenkPlatformError):
    """Raised when a sync operation fails."""
