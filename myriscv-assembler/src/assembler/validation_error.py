class ValidationError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        self.path = path or "<root>"
        super().__init__(f"{self.path}: {message}")
