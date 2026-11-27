"""In-memory fake Supabase client for isolated FastAPI unit tests."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class FakeResponse:
    data: List[Dict[str, Any]]


class FakeQueryBuilder:
    """Mimics the fluent supabase-py table query builder."""

    def __init__(self, rows: List[Dict[str, Any]]) -> None:
        self._rows = rows
        self._op: Optional[str] = None
        self._filters: List[tuple[str, Any]] = []
        self._payload: Any = None

    def select(self, _columns: str = "*") -> "FakeQueryBuilder":
        self._op = "select"
        return self

    def insert(self, payload: Dict[str, Any]) -> "FakeQueryBuilder":
        self._op = "insert"
        self._payload = dict(payload)
        return self

    def update(self, payload: Dict[str, Any]) -> "FakeQueryBuilder":
        self._op = "update"
        self._payload = dict(payload)
        return self

    def eq(self, column: str, value: Any) -> "FakeQueryBuilder":
        self._filters.append((column, value))
        return self

    def _matches(self, row: Dict[str, Any]) -> bool:
        return all(row.get(col) == val for col, val in self._filters)

    def execute(self) -> FakeResponse:
        if self._op == "select":
            matched = [dict(r) for r in self._rows if self._matches(r)]
            return FakeResponse(data=matched)

        if self._op == "insert":
            self._rows.append(self._payload)
            return FakeResponse(data=[dict(self._payload)])

        if self._op == "update":
            updated: List[Dict[str, Any]] = []
            for row in self._rows:
                if self._matches(row):
                    row.update(self._payload)
                    updated.append(dict(row))
            return FakeResponse(data=updated)

        raise ValueError(f"Unsupported operation: {self._op}")


class FakeSupabaseClient:
    """In-memory table store mimicking supabase.Client."""

    def __init__(self, tables: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> None:
        self.tables: Dict[str, List[Dict[str, Any]]] = tables or {
            "events": [],
            "tickets": [],
            "resale_listings": [],
            "transactions": [],
            "ticket_reservations": [],
        }

    def table(self, name: str) -> FakeQueryBuilder:
        if name not in self.tables:
            self.tables[name] = []
        return FakeQueryBuilder(self.tables[name])
