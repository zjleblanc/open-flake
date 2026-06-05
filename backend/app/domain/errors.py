import re

SNAKE_CASE_PATTERN = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


class InvalidFieldNameError(Exception):
    def __init__(self, name: str):
        self.name = name
        super().__init__(
            f'Invalid field name "{name}": must be snake_case '
            "(lowercase letters, digits, and underscores)."
        )


def validate_snake_case_field_name(name: str) -> None:
    if not SNAKE_CASE_PATTERN.match(name):
        raise InvalidFieldNameError(name)


def validate_other_field_keys(other: dict) -> None:
    for key in other:
        validate_snake_case_field_name(key)
