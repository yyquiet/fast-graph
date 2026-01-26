

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class ResourceNotFoundError(Exception):
    """Raised when a requested resource is not found."""
    pass
