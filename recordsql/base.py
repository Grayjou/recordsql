"""
Base classes for recordsql query builders.

This module provides the foundational RecordQuery class that all query
builders inherit from. It defines the common interface and functionality
shared by SELECT, INSERT, UPDATE, DELETE, and other query types.

Key Classes:
    - RecordQuery: Base class for all query builders

The RecordQuery class provides:
    - Table name validation
    - Query building interface
    - Placeholder parameter generation
    - Query copying and modification
"""
from .dependencies import SQLExpression
from typing import List, Any, Tuple, Optional
from .validators import validate_name


class RecordQuery(SQLExpression):
    """
    Base class for all query builders.
    """

    def __init__(
        self,
        table_name=None,
        *args,
        validate_table_name=True,
        alias: Optional[str] = None,
        **kwargs,
    ):
        """
        Initialize the query builder with the given arguments.
        """
        self.validate_table_name = validate_table_name
        if validate_table_name and table_name is not None:
            validate_name(table_name)

        self._table_name = table_name
        self.args = args
        self.kwargs = kwargs

        super().__init__(
            expression_value=None,
            expression_type="query",
            positive=True,
            inverted=False,
            alias=None,
        )

    @property
    def table_name(self) -> str:
        """
        Returns the name of the table.
        Returns:
            str: The name of the table.
        """
        return self._table_name if self._table_name else None

    @table_name.setter
    def table_name(self, value: str) -> None:
        """
        Sets the name of the table.
        Args:
            value (str): The name of the table.
        """
        if self.validate_table_name:
            validate_name(value)
        self._table_name = value

    def build(self):
        """
        Build the query.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def placeholder_pair(self) -> Tuple[str, List[Any]]:
        """
        Returns a tuple of the SQL query and its parameters.
        Returns:
            Tuple[str, List[Any]]: The SQL query and its parameters.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def copy(self):
        raise NotImplementedError("Subclasses must implement this method.")

    def copy_with(self, **kwargs):
        raise NotImplementedError("Subclasses must implement this method.")

    def __getattr__(self, name):
        """
        Get an attribute of the query builder.
        Args:
            name (str): The name of the attribute.
        Returns:
            Any: The value of the attribute.
        """
        # Override the __getattr__ method to handle dynamic attribute access in SQLExpression
        raise AttributeError(f"{name} not found in {self.__class__.__name__}")

    def sql_string(self, *args, **kwargs) -> str:
        """
        Return the SQL string representation of this query.

        This method delegates to the query subclass implementation of
        `placeholder_pair` / `placeholder_str` so that external callers
        (for example code in the expressql package that expects
        `SQLExpression.sql_string`) can obtain a SQL string without
        raising NotImplementedError.

        Any positional/keyword arguments are forwarded to
        `placeholder_pair`/`placeholder_str` when possible.
        """
        # Prefer a simple string-returning helper if available
        if hasattr(self, "placeholder_str"):
            try:
                return self.placeholder_str(*args, **kwargs)
            except TypeError:
                # fallback if signature differs
                pass

        # Fall back to placeholder_pair which should return (sql, params)
        if hasattr(self, "placeholder_pair"):
            pair = self.placeholder_pair(*args, **kwargs)
            if isinstance(pair, (list, tuple)) and len(pair) >= 1:
                return pair[0]

        # As a last resort, raise a clear error indicating the subclass must
        # implement placeholder_pair/placeholder_str.
        raise NotImplementedError(
            "Subclasses of RecordQuery must implement placeholder_pair "
            "or placeholder_str to produce SQL strings."
        )
