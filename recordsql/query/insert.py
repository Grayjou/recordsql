from __future__ import annotations
from ..base import RecordQuery
from ..dependencies import SQLCondition, SQLExpression
from ..types import SQLInput

# from expressql import SQLCondition, SQLExpression, no_condition
from ..raw_querybuilders import build_insert_query, OnConflictQuery
from typing import List, Union, Iterable
from ..types import SQLCol
from .utils import validate_monolist, normalize_args, is_pair, get_col_value
from ..validators import validate_name


class InsertQuery(RecordQuery):
    name = "INSERT"

    def __init__(
        self,
        into: str = None,
        columns: List[str] = None,
        values: List[SQLInput] = None,
        or_action: str = None,
        on_conflict=None,
        ignore_forbidden_chars=False,
        returning: List[SQLCol] = None,
    ):
        self.into = into
        table_name = into
        self.columns = columns
        self.values = values
        self.or_action = or_action
        self.on_conflict = on_conflict
        self.returning = returning
        super().__init__(table_name=table_name, validate_table_name=not ignore_forbidden_chars)
        self.ignore_forbidden_characters = ignore_forbidden_chars

    @property
    def bulk(self) -> bool:
        if self.values is None:
            return False
        if not isinstance(self.values, Iterable) or isinstance(self.values, str):
            raise TypeError("Values must be an iterable of SQLInput.")
        if not self.values:
            return False
        if not isinstance(self.values[0], Iterable) or isinstance(self.values[0], str):
            return False
        return True

    def __len__(self) -> int:
        if self.values is None:
            value_len = 0
        elif self.bulk:
            value_len = len(self.values[0])
        else:
            value_len = len(self.values)
        col_len = len(self.columns) if self.columns else 0
        if value_len != col_len:
            raise ValueError(f"Expected {col_len} values, got {value_len}.")
        return value_len

    def col_value_dict(self):
        if self.values is None or not self.values:
            raise ValueError("Values must be set before calling col_value_dict.")
        if self.columns is None or not self.columns:
            raise ValueError("Columns must be set before calling col_value_dict.")
        column_names = [
            column.expression_value if isinstance(column, SQLExpression) else column for column in self.columns
        ]
        if self.bulk:
            pack = []
            expected_len = len(self)
            for value in self.values:
                if len(value) != expected_len:
                    raise ValueError(f"Expected {expected_len} values, got {len(value)}.")
                pack.append(dict(zip(column_names, value)))
            return pack
        else:
            if len(self.values) != len(self.columns):
                raise ValueError(f"Expected {len(self.columns)} values, got {len(self.values)}.")
            return dict(zip(column_names, self.values))

    def INTO(self, table_name) -> InsertQuery:
        self.into = table_name
        self.table_name = table_name
        return self

    @normalize_args(skip=1)
    def VALUES(self, *values: Union[List[SQLInput], SQLInput]) -> InsertQuery:
        self.values = values
        return self

    def WHERE(self, condition):
        raise NotImplementedError("WHERE clause is not applicable for INSERT queries.")

    @normalize_args(skip=1)
    def RETURNING(self, *columns: SQLCol) -> InsertQuery:
        validate_monolist(*columns, monotype=SQLCol)
        self.returning = list(columns)
        return self

    @normalize_args(skip=1)
    def SET(self, *args, **kwargs) -> None:
        collected_cols = []
        collected_values = []
        for arg in args:
            if isinstance(arg, dict):
                collected_cols.extend(arg.keys())
                collected_values.extend(arg.values())
            elif is_pair(arg):
                k, v = arg
                collected_cols.append(k)
                collected_values.append(v)
            else:
                raise ValueError("SET accepts dicts or (col_name, value) pairs.")
        if not self.ignore_forbidden_characters:
            for col_key in collected_cols:
                col_key = get_col_value(col_key)
                validate_name(col_key, validate_chars=True)
        self.columns = list(collected_cols)
        self.values = list(collected_values)
        return self

    def placeholder_pair(self):
        placeholder_query, injections = build_insert_query(
            table_name=self.table_name,
            values=self.col_value_dict(),
            or_action=self.or_action,
            on_conflict=self.on_conflict,
            returning=self.returning,
        )

        return placeholder_query, injections

    def sql_string(self, *args, **kwargs) -> str:
        """
        Return the SQL string for this INSERT query.
        """
        pair = self.placeholder_pair(*args, **kwargs)
        if isinstance(pair, (list, tuple)) and pair:
            return pair[0]
        raise NotImplementedError("InsertQuery must provide a placeholder_pair returning (sql, params)")

    @normalize_args(skip=1)
    def COLS(self, *args: SQLCol) -> InsertQuery:
        validate_monolist(*args, monotype=SQLCol)
        self.columns = list(args)
        return self

    def OR_REPLACE(self) -> InsertQuery:
        self.or_action = "REPLACE"
        return self

    def OR_IGNORE(self) -> InsertQuery:
        self.or_action = "IGNORE"
        return self

    def ON_CONFLICT(
        self,
        do="NOTHING",
        conflict_cols: List[SQLCol] = None,
        set=None,
        where: SQLCondition = None,
    ) -> InsertQuery:
        if not conflict_cols:
            raise ValueError("Conflict columns must be provided.")
        if not isinstance(conflict_cols, list):
            raise TypeError("Conflict columns must be a list of SQLCol objects.")
        validate_monolist(*conflict_cols, monotype=SQLCol)
        self.on_conflict = OnConflictQuery(do_what=do, conflict_cols=conflict_cols, set_clauses=set, condition=where)
        return self


@normalize_args()
def INSERT(*column_names: SQLCol, or_action: str = None) -> InsertQuery:
    """
    Constructs an InsertQuery object with the specified column names and optional conflict resolution action.
    Args:
        *column_names (SQLCol): Variable-length argument list of SQL column objects to be included in the insert query.
        or_action (str, optional): Specifies the conflict resolution action to take (e.g., "OR REPLACE", "OR IGNORE").
                                    Defaults to None.
    Returns:
        InsertQuery: An object representing the constructed insert query.
    """

    if not column_names:
        column_names = []

    return InsertQuery(or_action=or_action, columns=column_names)
