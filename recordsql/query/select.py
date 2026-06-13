from __future__ import annotations
from ..raw_querybuilders import build_select_query
from ..raw_querybuilders import JoinQuery
from ..raw_querybuilders.formatters import SQLOrderBy, column_string
from typing import List, Optional, Union, Any, Iterable, Tuple
from ..base import RecordQuery
from ..types import SQLCol
from ..dependencies import SQLCondition, no_condition, SQLExpression
from ..validators import validate_name
from .utils import normalize_args, enlist
from ..utils import ensure_bracketed


class SelectQuery(RecordQuery):
    def __init__(
        self,
        columns: Union[str, list] = "*",
        table_name: str = None,
        condition: Any = None,
        order_by: Optional[List[Any]] = None,
        criteria: List[str] = None,
        limit: Optional[Union[int, str]] = None,
        offset: Optional[Union[int, str]] = None,
        group_by: Union[Any, list, None] = None,
        having: Optional[Any] = None,
        *,
        ignore_forbidden_chars: bool = False,
        alias: Optional[str] = None,
        joins: List[Any] = None,
        withs: Optional[List[Any]] = None,
    ) -> None:
        self._initialized = False  # Block __setattr__ during init

        self.columns = columns
        self.condition = condition
        self.order_by = order_by

        # Normalize criteria
        if criteria is None:
            criteria = ["DESC"]
        elif isinstance(criteria, str) and criteria in {"ASC", "DESC"}:
            criteria = [criteria]
        elif set(criteria) - {"ASC", "DESC"}:
            raise ValueError("criteria must be 'ASC' or 'DESC'")
        self.criteria = criteria

        self.limit = limit
        self.offset = offset
        self.group_by = group_by
        self.having = having
        self.ignore_forbidden_chars = ignore_forbidden_chars
        self.alias = alias
        self._joins = joins or []
        self._withs = withs or []

        # Internal state
        self._cached_placeholder_str = None
        self._cached_placeholder_params = None
        self._up_to_date = False
        super().__init__(
            table_name=table_name,
            validate_table_name=not ignore_forbidden_chars,
            alias=alias,
            expression_value=None,
            expression_type="query",
            positive=True,
            inverted=False,
        )
        self._initialized = True

        # Call parent constructor last to avoid premature tracking

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_initialized", False):
            self._on_attribute_change(name, value)
        super().__setattr__(name, value)

    def _on_attribute_change(self, attribute: str, value: Any) -> None:
        tracked = {
            "columns",
            "table_name",
            "condition",
            "order_by",
            "criteria",
            "limit",
            "offset",
            "group_by",
            "having",
            "joins",
            "withs",
            "alias",
        }

        if attribute in tracked:
            self._up_to_date = False

    @property
    def criteria(self) -> List[str]:
        """
        Returns the sorting criteria.
        Returns:
            List[str]: The sorting criteria, either "ASC" or "DESC".
        """
        return self._criteria if self._criteria else None

    @criteria.setter
    def criteria(self, value: List[str]) -> None:
        """
        Sets the sorting criteria.
        Args:
            value (List[str]): The sorting criteria, either "ASC" or "DESC".
        """
        if value in ["ASC", "DESC"]:
            self._criteria = [value]
        elif set(value) - {"ASC", "DESC"}:
            raise ValueError("criteria must be a list of 'ASC' or 'DESC'")
        else:
            self._criteria = value

    @property
    def joins(self) -> List[JoinQuery]:
        """
        Returns the list of joins.
        Returns:
            List[JoinQuery]: The list of joins.
        """
        return self._joins

    @joins.setter
    def joins(self, value: List[JoinQuery]) -> None:
        """
        Sets the list of joins.
        Args:
            value (List[JoinQuery]): The list of joins.
        """
        value = enlist(value)
        self.validate_join_list(value)
        self._joins = value or []

    @property
    def alias(self) -> Optional[str]:
        """
        Returns the alias of the query.
        Returns:
            Optional[str]: The alias of the query.
        """
        return self._alias

    @alias.setter
    def alias(self, value: Optional[str]) -> None:
        """
        Sets the alias of the query.
        Args:
            value (Optional[str]): The alias of the query.
        """
        if value is not None:
            if isinstance(value, SQLExpression):
                value = value.expression_value
            validate_name(value, validate_chars=not self.ignore_forbidden_chars)
        self._alias = value

    @property
    def withs(self) -> List[WithQuery]:
        """
        Returns the list of withs.
        Returns:
            List[WithQuery]: The list of withs.
        """
        return self._withs

    @withs.setter
    def withs(self, value: List[WithQuery]) -> None:
        """
        Sets the list of withs.
        Args:
            value (List[WithQuery]): The list of withs.
        """
        value = enlist(value)
        self.validate_with_list(value)
        self._withs = value or []

    def _add_join(self, join: JoinQuery) -> None:
        """
        Adds a join to the list of joins.
        Args:
            join (JoinQuery): The join to add.
        """
        my_joins = self.joins
        self.joins.append(join)
        self.joins = my_joins

    @normalize_args(skip=1)
    def SELECT(self, *columns: SQLCol) -> SelectQuery:
        """
        Sets the columns to select.
        Args:
            *columns (SQLCol): The columns to select.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        self.columns = list(columns)  # enforce normalized form
        return self

    def FROM(self, table_name: str = None):
        self.table_name = table_name
        return self

    def WHERE(self, condition: SQLCondition = no_condition):
        self.condition = condition
        return self

    def ORDER_BY(self, *items: Union[SQLOrderBy, List[SQLOrderBy]]):
        if not items:
            self.order_by = None
            self.criteria = None
            return self
        collected_order_by = []
        collected_criteria = []
        for item in items:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                collected_order_by.append(item[0])
                collected_criteria.append(item[1])
            elif isinstance(item, str):
                if item.upper() in ["ASC", "DESC"]:
                    collected_criteria.append(item.upper())
                else:
                    collected_order_by.append(item)
            elif isinstance(item, (str, SQLExpression)):
                collected_order_by.append(item)
        ob_len = len(collected_order_by)
        if ob_len == 0:
            return self
        for _ in range(len(collected_criteria), ob_len):
            collected_criteria.append("DESC")
        collected_criteria = collected_criteria[:ob_len]
        self.order_by = collected_order_by
        self.criteria = collected_criteria
        return self

    def LIMIT(self, limit: Optional[Union[int, str]] = None):
        self.limit = limit
        return self

    def OFFSET(self, offset: Optional[Union[int, str]] = None):
        self.offset = offset
        return self

    def GROUP_BY(self, group_by: Union[SQLCol, List[SQLCol], None] = None):
        if not isinstance(group_by, (str, SQLExpression, list, tuple)):
            raise TypeError("group_by must be an instance of SQLCol or list")
        self.group_by = group_by
        return self

    def HAVING(self, having: Optional[SQLCondition] = None):
        self.having = having
        return self

    def SET(self, *args, **kwargs) -> None:
        raise NotImplementedError("SET clause is not applicable for SELECT queries.")

    def VALUES(self, *args, **kwargs) -> None:
        raise NotImplementedError("VALUES clause is not applicable for SELECT queries.")

    def _placeholder_pair(self) -> Tuple[str, Any]:
        """
        Returns a placeholder pair for the query.
        Returns:
            Tuple[str, Any]: A tuple containing the query string and parameters.
        """
        string, params = build_select_query(
            table_name=self.table_name,
            columns=self.columns,
            condition=self.condition,
            order_by=self.order_by,
            criteria=self.criteria,
            limit=self.limit,
            offset=self.offset,
            group_by=self.group_by,
            having=self.having,
            joins=self.joins,
            ignore_forbidden_chars=self.ignore_forbidden_chars,
        )

        if self.withs:
            first, first_params = self.withs[0].placeholder_pair(include_with=True)
            withs = [first]
            with_params = first_params
            for with_ in self.withs[1:]:
                with_string, with_param = with_.placeholder_pair(include_with=False)
                withs.append(with_string)
                with_params.extend(with_param)
            withs = ", ".join(withs)
            withs += " "
            string = f"{withs}{string}"
            params = with_params + params
        return string, params

    def placeholder_pair(self, include_alias: bool = True) -> Tuple[str, Any]:
        """
        Returns a placeholder pair for the query.
        Args:
            include_alias (bool): Whether to include the alias in the placeholder pair.
        Returns:
            Tuple[str, Any]: A tuple containing the query string and parameters.
        """
        if not self._up_to_date:
            (
                self._cached_placeholder_str,
                self._cached_placeholder_params,
            ) = self._placeholder_pair()
            self._up_to_date = True
        string = self._cached_placeholder_str
        params = self._cached_placeholder_params
        if include_alias and self.alias:
            string = ensure_bracketed(string)
            string = f"{string} AS {self.alias}"
        return string, params

    def placeholder_str(self, *args, include_alias: bool = True, **kwargs) -> str:
        """
        Returns the placeholder string for the query.
        Args:
            *args: Additional arguments.
            include_alias (bool): Whether to include the alias in the placeholder string.
            **kwargs: Additional keyword arguments.
        Returns:
            str: The placeholder string for the query.
        """
        string, _ = self.placeholder_pair(include_alias=include_alias)
        return string

    def sql_string(self, *args, include_alias: bool = True, **kwargs) -> str:
        """
        Return the SQL string for this SELECT query.
        Delegates to `placeholder_str` to include alias handling.
        """
        try:
            return self.placeholder_str(*args, include_alias=include_alias, **kwargs)
        except TypeError:
            # fallback to placeholder_pair
            pair = self.placeholder_pair(*args, **kwargs)
            if isinstance(pair, (list, tuple)) and pair:
                return pair[0]
        raise NotImplementedError("SelectQuery must provide placeholder_str or placeholder_pair returning SQL string")

    def AS(self, alias=None):
        """
        Sets the alias for the query.
        Args:
            alias (str): The alias to set.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """

        self.alias = alias
        return self

    def __str__(self) -> str:
        start = "SelectQuery("
        mid, args = self.placeholder_pair()
        end = ")"
        args = ", ".join(str(arg) for arg in args)
        return f"{start}{mid}, <{args}> {end}"

    def __repr__(self) -> str:
        start = "SelectQuery("
        mid = column_string(self.columns)
        end = ")"
        order_by = f"order_by={column_string(self.order_by) if self.order_by else None}"
        criteria = f"({self.criteria})"
        limit = f"limit={self.limit}"
        offset = f"offset={self.offset}"
        group_by = f"group_by={column_string(self.group_by) if self.group_by else None}"
        having = self.having.sql_string() if self.having else None
        having = f"having={having}"
        table_name = f"table_name={self.table_name}"
        condition = self.condition.sql_string() if self.condition else None
        condition = f"condition={condition}"
        ignore_forbidden_chars = f"ifb={self.ignore_forbidden_chars}"
        all = (
            f"{start}{mid}, {table_name}, {condition}, {order_by}, {criteria}, "
            f"{limit}, {offset}, {group_by}, {having}, {ignore_forbidden_chars}"
        )
        return f"{all}{end}"

    def copy_with(
        self,
        columns: Union[SQLCol, List[SQLCol]] = None,
        table_name: str = None,
        condition: SQLCondition = None,
        order_by: Optional[List[SQLOrderBy]] = None,
        criteria: List[str] = None,
        limit: Optional[Union[int, str]] = None,
        offset: Optional[Union[int, str]] = None,
        group_by: Union[SQLCol, List[SQLCol], None] = None,
        having: Optional[SQLCondition] = None,
        joins: Optional[List[JoinQuery]] = None,
        alias: Optional[str] = None,
        ignore_forbidden_chars: bool = False,
    ) -> SelectQuery:
        """
        Creates a copy of the current query with the specified modifications.
        Args:
            columns (Union[SQLCol, List[SQLCol]], optional): The columns to select. Defaults to None.
            table_name (str, optional): The name of the table to query. Defaults to None.
            condition (SQLCondition, optional): The condition to apply to the query. Defaults to None.
            order_by (Optional[List[SQLOrderBy]], optional): The column(s) to order the results by. Defaults to None.
            criteria (List[str], optional): Sorting criteria ("ASC" or "DESC"). Defaults to
                None.
            limit (Optional[Union[int, str]], optional): Max rows to return. Defaults to
                None.
            offset (Optional[Union[int, str]], optional): Number of rows to skip before starting to
                return rows. Defaults to None.
            group_by (Union[SQLCol, List[SQLCol], None], optional): Columns to group results by.
                Defaults to None.
            having (SQLCondition, optional): The condition to apply to the grouped results. Defaults to None.
        Returns:
            SelectQuery: A new instance of SelectQuery with the specified modifications.
        """
        return SelectQuery(
            columns=columns if columns is not None else self.columns,
            table_name=table_name if table_name is not None else self.table_name,
            condition=condition if condition is not None else self.condition,
            order_by=order_by if order_by is not None else self.order_by,
            criteria=criteria if criteria is not None else self.criteria,
            limit=limit if limit is not None else self.limit,
            offset=offset if offset is not None else self.offset,
            group_by=group_by if group_by is not None else self.group_by,
            having=having if having is not None else self.having,
            alias=alias if alias is not None else self.alias,
            ignore_forbidden_chars=ignore_forbidden_chars
            if ignore_forbidden_chars is not None
            else self.ignore_forbidden_chars,
            joins=joins if joins is not None else self.joins,
        )

    def copy(self) -> SelectQuery:
        """
        Creates a copy of the current query.
        Returns:
            SelectQuery: A new instance of SelectQuery with the same attributes as the current instance.
        """
        return self.copy_with()

    @classmethod
    def _SELECT(cls, column_list: Union[SQLCol, List[SQLCol]] = "*", *args: SQLCol, **kwargs) -> SelectQuery:
        """
        Constructs a SELECT SQL query.
        Args:
            column_list (Union[SQLCol, List[SQLCol]], optional): A single column,
                a list of columns, or "*" to select all columns. Defaults to "*".
            *args (SQLCol): Additional columns to include in the SELECT query.
        Returns:
            SelectQuery: An object representing the constructed SELECT query.
        Example:
            >>> query = SELECT(col("id"), col("name")).FROM("users").WHERE(col("id") == 1)
            >>> print(query.placeholder_pair())
            SELECT id, name FROM users WHERE id = ?, [1]
        """

        if not isinstance(column_list, list):
            column_list = [column_list]
        column_list_ = column_list + list(args)

        return cls(columns=column_list_, **kwargs)

    @normalize_args(skip=1)
    def JOINS(self, *joins: JoinQuery, join_list=None, **kwargs) -> SelectQuery:
        """
        Adds JOIN clauses to the query.
        Args:
            *joins (JoinQuery): The JOIN clauses to add.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        if join_list is not None:
            if isinstance(join_list, JoinQuery):
                join_list = [join_list]
            elif isinstance(join_list, Iterable) and not isinstance(join_list, (str, bytes)):
                join_list = list(join_list)
            else:
                raise TypeError("join_list must be a JoinQuery or an iterable of JoinQuery")
        else:
            join_list = []

        if not joins and not kwargs and not join_list:
            self.joins = None
            return self
        joins = list(joins) + list(kwargs.values()) + join_list
        self.validate_join_list(joins)
        my_joins = self.joins
        my_joins.extend(joins)
        self.joins = my_joins
        return self

    def INNER_JOIN(self, table_name: str, on: SQLCondition, alias: Optional[str] = None) -> SelectQuery:
        """
        Adds an INNER JOIN clause to the query.
        Args:
            table_name (str): The name of the table to join.
            on (SQLCondition): The condition for the join.
            alias (Optional[str]): An optional alias for the joined table.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        join = JoinQuery(table_name=table_name, on=on, join_type="INNER", alias=alias)
        self._add_join(join)
        return self

    def LEFT_JOIN(self, table_name: str, on: SQLCondition, alias: Optional[str] = None) -> SelectQuery:
        """
        Adds a LEFT JOIN clause to the query.
        Args:
            table_name (str): The name of the table to join.
            on (SQLCondition): The condition for the join.
            alias (Optional[str]): An optional alias for the joined table.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        join = JoinQuery(table_name=table_name, on=on, join_type="LEFT", alias=alias)
        self._add_join(join)
        return self

    def RIGHT_JOIN(self, table_name: str, on: SQLCondition, alias: Optional[str] = None) -> SelectQuery:
        """
        Adds a RIGHT JOIN clause to the query.
        Args:
            table_name (str): The name of the table to join.
            on (SQLCondition): The condition for the join.
            alias (Optional[str]): An optional alias for the joined table.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        join = JoinQuery(table_name=table_name, on=on, join_type="RIGHT", alias=alias)
        self._add_join(join)
        return self

    def FULL_JOIN(self, table_name: str, on: SQLCondition, alias: Optional[str] = None) -> SelectQuery:
        """
        Adds a FULL JOIN clause to the query.
        Args:
            table_name (str): The name of the table to join.
            on (SQLCondition): The condition for the join.
            alias (Optional[str]): An optional alias for the joined table.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        join = JoinQuery(table_name=table_name, on=on, join_type="FULL", alias=alias)
        self._add_join(join)
        return self

    def CROSS_JOIN(self, table_name: str, on: SQLCondition, alias: Optional[str] = None) -> SelectQuery:
        """
        Adds a CROSS JOIN clause to the query.
        Args:
            table_name (str): The name of the table to join.
            on (SQLCondition): The condition for the join.
            alias (Optional[str]): An optional alias for the joined table.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        join = JoinQuery(table_name=table_name, on=on, join_type="CROSS", alias=alias)
        self._add_join(join)
        return self

    def OUTER_JOIN(self, table_name: str, on: SQLCondition, alias: Optional[str] = None) -> SelectQuery:
        """
        Adds an OUTER JOIN clause to the query.
        Args:
            table_name (str): The name of the table to join.
            on (SQLCondition): The condition for the join.
            alias (Optional[str]): An optional alias for the joined table.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        join = JoinQuery(table_name=table_name, on=on, join_type="OUTER", alias=alias)
        self._add_join(join)
        return self

    def JOIN(self, *joins: JoinQuery, join_list=None, **kwargs) -> SelectQuery:
        """
        Adds JOIN clauses to the query.
        Args:
            *joins (JoinQuery): The JOIN clauses to add.
            join_list (Optional[List[JoinQuery]]): An optional list of JOIN clauses.
            **kwargs: Additional JOIN clauses as keyword arguments.
        Returns:
            SelectQuery: The current instance of SelectQuery.
        """
        former_joins = self.joins
        try:
            self.joins = []
            return self.JOINS(*joins, join_list=join_list, **kwargs)
        except Exception as e:
            self.joins = former_joins
            raise e
        return self

    def WITH_alias_as_self(self, alias: SQLCol = None) -> WithQuery:
        """
        Creates a WithQuery with the current SelectQuery as its query.
        Args:
            alias (SQLCol, optional): The alias for the WithQuery. Defaults to None.
        Returns:
            WithQuery: A new instance of WithQuery with the current SelectQuery as its query.
        """
        return WithQuery(self, alias=alias, ignore_forbidden_chars=self.ignore_forbidden_chars)

    def __eq__(self, other):
        return False

    def __ne__(self, other):
        return True

    @staticmethod
    def validate_join_list(joins: List[JoinQuery]) -> None:
        """
        Validates the list of joins.
        Args:
            joins (List[JoinQuery]): The list of joins to validate.
        Raises:
            TypeError: If any join is not an instance of JoinQuery.
        """
        if joins is None:
            return
        if not isinstance(joins, Iterable):
            raise TypeError("joins must be a Iterable")
        if not all(isinstance(join, JoinQuery) for join in joins):
            raise TypeError("All joins must be instances of JoinQuery")

    @staticmethod
    def validate_with_list(withs: List[WithQuery]) -> None:
        """
        Validates the list of withs.
        Args:
            withs (List[WithQuery]): The list of withs to validate.
        Raises:
            TypeError: If any with is not an instance of WithQuery.
        """
        if withs is None:
            return
        if not isinstance(withs, Iterable):
            raise TypeError("withs must be a Iterable")
        if not all(isinstance(with_, WithQuery) for with_ in withs):
            raise TypeError("All withs must be instances of WithQuery")

    def with_queries_as(self, *with_queries: WithQuery, _new_withs=True, **as_with_dict) -> SelectQuery:
        """
        Adds one or more WITH queries to the current SelectQuery instance.
        This method allows you to define Common Table Expressions (CTEs) using
        the provided `WithQuery` objects or keyword arguments. The resulting
        query will include the specified WITH queries.
        Args:
            *with_queries (WithQuery): One or more `WithQuery` objects to be
                included in the WITH clause.
            _new_withs (bool, optional): If True (default), replaces the existing
                WITH queries with the new ones. If False, appends the new WITH
                queries to the existing ones.
            **as_with_dict: Additional WITH queries specified as keyword arguments,
                where the key is the alias and the value is the query.
        Returns:
            SelectQuery: A new `SelectQuery` instance with the updated WITH queries.
        """

        withs = WITH(*with_queries, **as_with_dict).withs
        if not _new_withs:
            withs = self.withs + withs
        my_copy = self.copy()
        my_copy.withs = withs
        return my_copy


select_alias = [
    "set_select",
    "set_selection",
    "set_columns",
    "change_selection",
    "change_columns",
    "select_columns",
]

for alias in select_alias:
    setattr(SelectQuery, alias, SelectQuery.SELECT)


def SELECT(
    column_list: Union[SQLCol, List[SQLCol]] = "*",
    *args: SQLCol,
    ignore_forbidden_characters: bool = False,
    **kwargs: Any,
) -> SelectQuery:
    return SelectQuery._SELECT(column_list, *args, ignore_forbidden_chars=ignore_forbidden_characters, **kwargs)


SELECT.__doc__ = SelectQuery.SELECT.__doc__


class WithQuery:
    def __new__(
        cls,
        query: SelectQuery,
        alias: SQLCol = None,
        ignore_forbidden_chars: bool = False,
    ):
        if isinstance(query, WithQuery):
            return query
        if not isinstance(query, SelectQuery):
            raise TypeError("query must be an instance of SelectQuery")
        if not isinstance(alias, (str, SQLExpression, type(None))):
            raise TypeError("alias must be an instance of SQLCol or None")
        query = query.copy()
        return super().__new__(cls)

    def __init__(
        self,
        query: SelectQuery,
        alias: SQLCol = None,
        ignore_forbidden_chars: bool = False,
    ):
        self.ignore_forbidden_chars = ignore_forbidden_chars
        self.query = query
        self.alias = alias

    @property
    def alias(self) -> SQLCol:
        if self._alias is None:
            return self.query.alias
        return self._alias

    @alias.setter
    def alias(self, value: SQLCol) -> None:
        if value is not None:
            if isinstance(value, SQLExpression):
                value = value.expression_value
            validate_name(value, validate_chars=not self.ignore_forbidden_chars)
        self._alias = value

    def placeholder_pair(self, include_with=True) -> Tuple[str, Any]:
        alias = self.alias
        if alias is None:
            raise ValueError("Alias must be set for the WithQuery")
        string, params = self.query.placeholder_pair(include_alias=False)
        string = f"{alias} AS {ensure_bracketed(string)}"
        if include_with:
            string = f"WITH {string}"
        return string, params

    def AS(self, alias: SQLCol) -> WithQuery:
        """
        Sets the alias for the WithQuery.
        Args:
            alias (SQLCol): The alias to set.
        Returns:
            WithQuery: The current instance of WithQuery.
        """
        self.alias = alias
        return self

    def copy(self) -> WithQuery:
        """
        Creates a copy of the current WithQuery.
        Returns:
            WithQuery: A new instance of WithQuery with the same attributes as the current instance.
        """
        return WithQuery(
            self.query.copy(),
            alias=self.alias,
            ignore_forbidden_chars=self.ignore_forbidden_chars,
        )


@normalize_args()
def WITH(*with_queries: WithQuery, base: Optional[SelectQuery] = None, **as_with_dict) -> SelectQuery:
    """
    Constructs a WITH SQL query.
    Args:
        *with_queries (WithQuery): The WITH queries to include.
        **as_with_dict (dict): Additional WITH queries as keyword arguments.
    Returns:
        SelectQuery: A SelectQuery containing the WITH queries.
    Example:
        >>> query = WITH(WithQuery(SELECT("id").FROM("users")), WithQuery(SELECT("name").FROM("products")))
        >>> print(query.placeholder_pair())
        WITH id AS (SELECT id FROM users), name AS (SELECT name FROM products)
    """
    with_queries = list(with_queries)
    if not with_queries and not as_with_dict:
        raise ValueError("At least one with_query or as_with_dict must be provided")
    for key, value in as_with_dict.items():
        if not isinstance(key, SQLCol):
            raise TypeError("Key must be an instance of SQLCol")
        if not isinstance(value, SelectQuery):
            raise TypeError("Value must be an instance of SelectQuery")
        new_with = WithQuery(value, alias=key)
        with_queries.append(new_with)
    for i, with_query in enumerate(with_queries):
        if isinstance(with_query, SelectQuery):
            with_queries[i] = WithQuery(with_query)
    base: SelectQuery = base or SelectQuery()

    base.withs = with_queries
    return base
