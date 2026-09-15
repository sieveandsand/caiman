"""Shared deterministic serialization and fail-closed document labels."""

from dataclasses import dataclass
import json
import re


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
        super().__init__('; '.join(f'{field}: {reason}' for field, reason in errors.items()))


def canonical_json(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False).encode('utf-8')


def valid_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value))


@dataclass(frozen=True)
class AccessLabel:
    is_public: bool = False
    compartments: frozenset[str] = frozenset()

    def __post_init__(self):
        if type(self.is_public) is not bool or not isinstance(self.compartments, frozenset):
            raise ValueError('Labels require a boolean public flag and frozen compartment set')
        if any(not valid_identifier(item) or item == 'public' for item in self.compartments):
            raise ValueError('Compartments must be safe identifiers other than public')
        if self.is_public and self.compartments:
            raise ValueError('Choose public access or compartments, not both')

    def prefixed_labels(self) -> frozenset[str]:
        if self.is_public:
            return frozenset({'public'})
        return frozenset(f'compartment:{item}' for item in self.compartments)

    def permits(self, session_compartments) -> bool:
        required = self.prefixed_labels()
        if not required or isinstance(session_compartments, (str, bytes)):
            return False
        try:
            available = AccessLabel(False, frozenset(session_compartments)).prefixed_labels()
        except (ValueError, TypeError):
            return False
        return required <= (available | AccessLabel(True).prefixed_labels())
