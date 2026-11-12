"""Custom exceptions mapped to HTTP status codes in main.py."""


class UpstreamError(Exception):
    """An external data service returned an error or an unusable payload (-> 502)."""


class UpstreamTimeout(Exception):
    """An external data service did not answer in time (-> 504)."""


class NotFoundError(Exception):
    """A requested resource does not exist (-> 404)."""


class DataQualityError(Exception):
    """The fetched data cannot support an analysis, e.g. too many gaps (-> 422)."""
