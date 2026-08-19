class InstructionError(ValueError):
    def __init__(self, message: str, *, argument_index: int | None = None) -> None:
        super().__init__(message)
        self.argument_index = argument_index
