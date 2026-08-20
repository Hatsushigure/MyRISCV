class InstructionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        source_offset: int | None = None,
    ) -> None:
        super().__init__(message)
        self.source_offset = source_offset
