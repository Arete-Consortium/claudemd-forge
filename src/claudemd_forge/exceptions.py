"""Custom exceptions for ClaudeMD Forge."""


class ForgeError(Exception):
    """Base exception for all ClaudeMD Forge errors."""


class ScanError(ForgeError):
    """Raised when filesystem scanning encounters an unrecoverable error."""


class AnalysisError(ForgeError):
    """Raised when codebase analysis fails."""


class TemplateError(ForgeError):
    """Raised when template rendering fails."""


class LicenseError(ForgeError):
    """Raised when a feature requires a higher license tier."""
