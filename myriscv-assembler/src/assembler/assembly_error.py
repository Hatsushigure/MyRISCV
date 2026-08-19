class AssemblyError(ValueError):
    def __init__(self, message: str, *, line: int, column: int) -> None:
        super().__init__(message)
        self.line = line
        self.column = column
