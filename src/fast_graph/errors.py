

class ValidationError(Exception):
    """Raised when input validation fails."""
    pass


class ResourceNotFoundError(Exception):
    """Raised when a requested resource is not found."""
    pass


class ResourceExistsError(Exception):
    """Raised when a resource already exists."""
    pass


class GraphNotFoundError(Exception):
    """Raised when a graph is not found."""
    pass
