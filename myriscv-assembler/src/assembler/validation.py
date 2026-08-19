from typing import Any, cast

from assembler.validation_error import ValidationError


class Validation:
    @staticmethod
    def field_path(path: str, field: str | int) -> str:
        if isinstance(field, int):
            return f"{path}[{field}]" if path else f"[{field}]"
        return f"{path}.{field}" if path else field

    @staticmethod
    def require_field(data: dict[str, Any], field: str, *, path: str) -> Any:
        result_path = Validation.field_path(path, field)
        if field not in data:
            raise ValidationError(result_path, "is required")
        return data[field]

    @staticmethod
    def require_mapping_value(value: Any, *, path: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValidationError(path, "must be a map")
        return cast(dict[str, Any], value)

    @staticmethod
    def require_mapping(
        data: dict[str, Any], field: str, *, path: str
    ) -> dict[str, Any]:
        result_path = Validation.field_path(path, field)
        value = Validation.require_field(data, field, path=path)
        return Validation.require_mapping_value(value, path=result_path)

    @staticmethod
    def require_list(data: dict[str, Any], field: str, *, path: str) -> list[Any]:
        result_path = Validation.field_path(path, field)
        value = Validation.require_field(data, field, path=path)
        if not isinstance(value, list):
            raise ValidationError(result_path, "must be a list")
        return cast(list[Any], value)

    @staticmethod
    def require_string_value(value: Any, *, path: str) -> str:
        if not isinstance(value, str):
            raise ValidationError(path, "must be a string")
        return value

    @staticmethod
    def require_string(data: dict[str, Any], field: str, *, path: str) -> str:
        result_path = Validation.field_path(path, field)
        value = Validation.require_field(data, field, path=path)
        return Validation.require_string_value(value, path=result_path)

    @staticmethod
    def require_integer(data: dict[str, Any], field: str, *, path: str) -> int:
        result_path = Validation.field_path(path, field)
        value = Validation.require_field(data, field, path=path)
        if not isinstance(value, int):
            raise ValidationError(result_path, "must be an integer")
        return value

    @staticmethod
    def require_positive_integer_value(value: Any, *, path: str) -> int:
        if not isinstance(value, int) or value <= 0:
            raise ValidationError(path, "must be a positive integer")
        return value

    @staticmethod
    def require_positive_integer(
        data: dict[str, Any], field: str, *, path: str
    ) -> int:
        result_path = Validation.field_path(path, field)
        value = Validation.require_field(data, field, path=path)
        return Validation.require_positive_integer_value(value, path=result_path)
