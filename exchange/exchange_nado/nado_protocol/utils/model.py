from enum import Enum
from pydantic import BaseModel
from typing import Any, Callable, Type, TypeVar, Union


class NadoBaseModel(BaseModel):
    """
    This base model extends Pydantic's BaseModel and excludes fields with None
    values by default when serializing via .dict() or .json()
    """

    def dict(self, **kwargs):
        """
        Convert model to dictionary, excluding None fields by default.

        Args:
            kwargs: Arbitrary keyword arguments.

        Returns:
            dict: The model as a dictionary.
        """
        kwargs.setdefault("exclude_none", True)
        return super().dict(**kwargs)

    def json(self, **kwargs):
        """
        Convert model to JSON, excluding None fields by default.

        Args:
            kwargs: Arbitrary keyword arguments.

        Returns:
            str: The model as a JSON string.
        """
        kwargs.setdefault("exclude_none", True)
        return super().json(**kwargs)

    def serialize_dict(self, fields: list[str], func: Callable):
        """
        Apply a function to specified fields in the model's dictionary.

        Args:
            fields (list[str]): Fields to be modified.

            func (Callable): Function to apply to each field.
        """
        for field in fields:
            self.__dict__[field] = func(self.__dict__[field])


def parse_enum_value(value: Union[str, Enum]) -> str:
    """
    Utility function to parse an enum value.

    Args:
        value (str | Enum): Original value which may be an Enum.

    Returns:
        str: The Enum value.
    """
    if isinstance(value, Enum):
        return value.value
    else:
        return value


T = TypeVar("T")


def ensure_data_type(data, expected_type: Type[T]) -> T:
    assert isinstance(
        data, expected_type
    ), f"Expected {expected_type.__name__}, but got {type(data).__name__}"
    return data


def is_instance_of_union(obj: Any, union) -> bool:
    """Check if `obj` is an instance of any type in the `union`."""
    return any(isinstance(obj, cls) for cls in union.__args__)
