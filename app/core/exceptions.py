class DomainValidationError(Exception):
    """Raised when a payload fails semantic or business rule validation."""
    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(self.detail)