from ..base import RecordQuery
from ..types import SQLCol, SQLInput
from ..dependencies import SQLCondition, no_condition, SQLExpression
from typing import List, Tuple, Any, Union, Dict
from ..validators import validate_name, validate_column_names
from .utils import is_pair, get_col_value, normalize_args
from ..raw_querybuilders import build_update_query


class UpdateQuery(RecordQuery):
    name = "UPDATE"

    def __init__(
        self,
        table_name: str = None,
        set_clauses: dict = None,
        condition: SQLCondition = no_condition,
        returning: List[SQLCol] = None,
        ignore_forbidden_characters: bool = False,
    ) -> None:
        self._set_clauses = self.normalize_set_clauses(set_clauses) if set_clauses else None
        super().__init__(table_name=table_name, validate_table_name=not ignore_forbidden_characters)
        self.ignore_forbidden_characters = ignore_forbidden_characters
        self.condition = condition if isinstance(condition, SQLCondition) else no_condition
        if not ignore_forbidden_characters:
            validate_column_names(returning, allow_dot=True)
        if isinstance(returning, (str, SQLExpression)):
            returning = [returning]
        self.returning = returning

    @property
    def set_clauses(self):
        return self._set_clauses

    @set_clauses.setter
    def set_clauses(self, clauses):
        """
        clauses: list of (col_name, value) pairs or dict.
        Validates column names here.
        """
        validated = {}

        if clauses:
            validated = self.normalize_set_clauses(clauses)
        self._set_clauses = validated

    def normalize_set_clauses(
        self, clauses: Union[Dict[str, SQLInput], List[Tuple[str, SQLInput]]]
    ) -> Dict[str, SQLInput]:
        set_clauses = {}

        if not clauses:
            return set_clauses

        if isinstance(clauses, dict):
            for k, v in clauses.items():
                col_key = get_col_value(k)
                if not self.ignore_forbidden_characters:
                    validate_name(col_key, allow_dot=True)
                set_clauses[col_key] = v

        elif isinstance(clauses, (list, tuple)):
            if is_pair(clauses):  # A single pair like ("age", 30)
                k, v = clauses
                col_key = get_col_value(k)
                if not self.ignore_forbidden_characters:
                    validate_name(col_key, allow_dot=True)
                set_clauses[col_key] = v
            else:
                for item in clauses:
                    if isinstance(item, dict):
                        for k, v in item.items():
                            col_key = get_col_value(k)
                            if not self.ignore_forbidden_characters:
                                validate_name(col_key, allow_dot=True)
                            set_clauses[col_key] = v
                    elif is_pair(item):
                        k, v = item
                        col_key = get_col_value(k)
                        if not self.ignore_forbidden_characters:
                            validate_name(col_key, allow_dot=True)
                        set_clauses[col_key] = v
                    else:
                        raise ValueError("SET clause must be a dict or a (col_name, value) pair.")
        else:
            raise ValueError("SET clause must be a dict or a list of pairs.")

        return set_clauses

    def SET(self, *args, **kwargs) -> "UpdateQuery":
        new_clauses = {}

        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    col_key = get_col_value(k)
                    if not self.ignore_forbidden_characters:
                        validate_name(col_key, allow_dot=True)
                    new_clauses[col_key] = v
            elif is_pair(arg):
                k, v = arg
                col_key = get_col_value(k)
                if not self.ignore_forbidden_characters:
                    validate_name(col_key, allow_dot=True)
                new_clauses[col_key] = v
            else:
                raise ValueError("SET accepts dicts or (col_name, value) pairs.")
        if not self.ignore_forbidden_characters:
            validate_column_names(kwargs.keys(), allow_dot=False)
        new_clauses.update(kwargs)
        self.set_clauses = new_clauses
        return self

    def WHERE(self, condition: SQLCondition) -> "UpdateQuery":
        if not isinstance(condition, SQLCondition):
            raise TypeError("Condition must be an SQLCondition.")
        self.condition = condition
        return self

    @normalize_args(skip=1)
    def RETURNING(self, *args: SQLCol) -> "UpdateQuery":
        """
        Adds a RETURNING clause to the query.
        """
        if not args:
            args = None
            self.returning = args
        self.returning = list(args)
        return self

    def HAVING(self, *args, **kwargs) -> None:
        raise NotImplementedError("HAVING clause is not supported in DELETE queries.")

    def ORDER_BY(self, *args, **kwargs) -> None:
        raise NotImplementedError("ORDER BY clause is not supported in DELETE queries.")

    def LIMIT(self, *args, **kwargs) -> None:
        raise NotImplementedError("LIMIT clause is not supported in DELETE queries.")

    def OFFSET(self, *args, **kwargs) -> None:
        raise NotImplementedError("OFFSET clause is not supported in DELETE queries.")

    def UPDATE(self, table_name: str) -> "UpdateQuery":
        """
        Sets the table name for the UPDATE query.
        """
        self.table_name = table_name
        return self

    FROM = UPDATE  # Alias for FROM method
    UPDATE_TABLE = UPDATE  # Alias for UPDATE_TABLE method
    TABLE = UPDATE  # Alias for TABLE method

    def placeholder_pair(self) -> Tuple[str, List[Any]]:
        """
        Builds the UPDATE SQL query and placeholder values.
        """
        # So you know it's a pair of query and injections
        query, injections = build_update_query(
            table_name=self.table_name,
            values=self.set_clauses,
            condition=self.condition,
            returning=self.returning,
            ignore_forbidden_chars=self.ignore_forbidden_characters,
        )

        return query, injections

    def sql_string(self, *args, **kwargs) -> str:
        """
        Return the SQL string for this UPDATE query.
        """
        pair = self.placeholder_pair(*args, **kwargs)
        if isinstance(pair, (list, tuple)) and pair:
            return pair[0]
        raise NotImplementedError("UpdateQuery must provide a placeholder_pair returning (sql, params)")

    def __repr__(self):
        return f"UpdateQuery(table={self.table_name}, set={self.set_clauses}, where={self.condition})"


def UPDATE(
    table_name: str,
    *set_clauses: Union[Dict[str, SQLInput], List[Tuple[str, SQLInput]]],
    ignore_forbidden_characters: bool = False,
) -> UpdateQuery:
    """
    Constructs an SQL UPDATE query.
    Args:
        table_name (str): The name of the table to update.
        *set_clauses (Union[Dict[str, SQLInput], List[Tuple[str, SQLInput]]]):
            One or more clauses specifying the columns to update and their new values.
            Each clause can be a dictionary mapping column names to values or a list of
            tuples where each tuple contains a column name and its corresponding value.
        ignore_forbidden_characters (bool, optional):
            If True, ignores forbidden characters in the input. Defaults to False.
    Returns:
        UpdateQuery: An object representing the constructed SQL UPDATE query.
    """

    return UpdateQuery(
        table_name=table_name,
        set_clauses=set_clauses,
        ignore_forbidden_characters=ignore_forbidden_characters,
    )
