from ..base import RecordQuery
from ..dependencies import SQLCondition, no_condition
from ..types import SQLCol
from ..raw_querybuilders import build_delete_query
from typing import Optional, List, Tuple, Any
from .utils import normalize_args


class DeleteQuery(RecordQuery):
    name = "DELETE"

    def __init__(
        self,
        table_name: str = None,
        condition: Optional[SQLCondition] = no_condition,
        returning: Optional[List[SQLCol]] = None,
        ignore_forbidden_characters: bool = False,
    ):
        super().__init__(table_name=table_name, validate_table_name=not ignore_forbidden_characters)
        self.condition = condition if isinstance(condition, SQLCondition) else no_condition
        self.returning = returning if isinstance(returning, list) else [returning] if returning else None
        self.ignore_forbidden_characters = ignore_forbidden_characters

    def WHERE(self, condition: SQLCondition) -> "DeleteQuery":
        if not isinstance(condition, SQLCondition):
            raise TypeError("Condition must be an SQLCondition.")
        self.condition = condition
        return self

    def FROM(self, table_name: str) -> "DeleteQuery":
        self.table_name = table_name
        return self

    @normalize_args(skip=1)
    def RETURNING(self, *args: SQLCol) -> "DeleteQuery":
        self.returning = list(args) if args else None
        return self

    def HAVING(self, *args, **kwargs) -> "DeleteQuery":
        raise NotImplementedError("HAVING clause is not supported in DELETE queries.")

    def ORDER_BY(self, *args, **kwargs) -> "DeleteQuery":
        raise NotImplementedError("ORDER BY clause is not supported in DELETE queries.")

    def LIMIT(self, *args, **kwargs) -> "DeleteQuery":
        raise NotImplementedError("LIMIT clause is not supported in DELETE queries.")

    def OFFSET(self, *args, **kwargs) -> "DeleteQuery":
        raise NotImplementedError("OFFSET clause is not supported in DELETE queries.")

    def placeholder_pair(self, *args, **kwarfs) -> Tuple[str, List[Any]]:
        return build_delete_query(
            table_name=self.table_name,
            condition=self.condition,
            returning=self.returning,
            ignore_forbidden_chars=self.ignore_forbidden_characters,
        )

    def sql_string(self, *args, **kwargs) -> str:
        """
        Return the SQL string for this DELETE query.
        """
        pair = self.placeholder_pair(*args, **kwargs)
        if isinstance(pair, (list, tuple)) and pair:
            return pair[0]
        raise NotImplementedError("DeleteQuery must provide a placeholder_pair returning (sql, params)")

    def __repr__(self):
        return f"DeleteQuery(table={self.table_name}, where={self.condition}, returning={self.returning})"


def DELETE(table_name: str = None, ignore_forbidden_characters: bool = False) -> DeleteQuery:
    return DeleteQuery(table_name=table_name, ignore_forbidden_characters=ignore_forbidden_characters)
