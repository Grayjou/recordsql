from ..base import RecordQuery
from ..types import SQLCol
from ..dependencies import SQLCondition, no_condition
from ..raw_querybuilders import build_count_query
from typing import Union, List, Tuple, Any, Optional


class CountQuery(RecordQuery):
    name = "COUNT"

    def __init__(
        self,
        table_name: str = None,
        condition: Optional[SQLCondition] = no_condition,
        group_by: Union[SQLCol, List[SQLCol], None] = None,
        having: Optional[SQLCondition] = None,
        ignore_forbidden_characters: bool = False,
    ):
        super().__init__(table_name=table_name, validate_table_name=not ignore_forbidden_characters)
        self.condition = condition
        self.group_by = group_by
        self.having = having
        self.ignore_forbidden_characters = ignore_forbidden_characters

    def FROM(self, table_name: str) -> "CountQuery":
        self.table_name = table_name
        return self

    def WHERE(self, condition: SQLCondition) -> "CountQuery":
        self.condition = condition
        return self

    def GROUP_BY(self, group_by: Union[SQLCol, List[SQLCol], None]) -> "CountQuery":
        self.group_by = group_by
        return self

    def HAVING(self, having: Optional[SQLCondition]) -> "CountQuery":
        self.having = having
        return self

    def placeholder_pair(self) -> Tuple[str, List[Any]]:
        return build_count_query(
            table_name=self.table_name,
            condition=self.condition,
            group_by=self.group_by,
            having=self.having,
            ignore_forbidden_chars=self.ignore_forbidden_characters,
        )

    def sql_string(self, *args, **kwargs) -> str:
        """
        Return the SQL string for this COUNT query.
        Delegates to `placeholder_pair` and returns the SQL text portion.
        """
        pair = self.placeholder_pair(*args, **kwargs)
        if isinstance(pair, (list, tuple)) and pair:
            return pair[0]
        raise NotImplementedError("CountQuery must provide a placeholder_pair returning (sql, params)")

    def SET(self, *args, **kwargs) -> None:
        raise NotImplementedError("SET clause is not supported in COUNT queries.")

    def ORDER_BY(self, *args, **kwargs) -> None:
        raise NotImplementedError("ORDER BY clause is not supported in COUNT queries.")

    def LIMIT(self, *args, **kwargs) -> None:
        raise NotImplementedError("LIMIT clause is not supported in COUNT queries.")

    def OFFSET(self, *args, **kwargs) -> None:
        raise NotImplementedError("OFFSET clause is not supported in COUNT queries.")

    def __repr__(self):
        return (
            f"CountQuery(table={self.table_name}, where={self.condition}, "
            f"group_by={self.group_by}, having={self.having})"
        )


def COUNT(table_name: str = None, ignore_forbidden_characters: bool = False) -> CountQuery:
    return CountQuery(table_name=table_name, ignore_forbidden_characters=ignore_forbidden_characters)
