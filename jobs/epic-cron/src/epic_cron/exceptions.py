"""Application exceptions owned by epic-cron."""

from werkzeug.exceptions import BadRequest
from werkzeug.wrappers.response import Response


class BadRequestError(BadRequest):
    """Raised when a queued job cannot be processed because its data is invalid."""

    def __init__(self, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.description = message
        self.response = Response(message, status=BadRequest.code)
