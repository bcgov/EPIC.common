"""Common cron exceptions."""


class BadRequestError(Exception):
    """Raised when queued job data or cron configuration is invalid."""
