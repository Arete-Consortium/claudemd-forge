"""Custom exceptions for AnchorMD."""


class ForgeError(Exception):
    """Base exception for all AnchorMD errors."""


class ScanError(ForgeError):
    """Raised when filesystem scanning encounters an unrecoverable error."""


class AnalysisError(ForgeError):
    """Raised when codebase analysis fails."""


class TemplateError(ForgeError):
    """Raised when template rendering fails."""


class LicenseError(ForgeError):
    """Raised when a feature requires a higher license tier."""


class DriftError(ForgeError):
    """Raised when drift detection encounters an error."""


class StoreError(ForgeError):
    """Raised when a local data store operation fails."""
