"""Shared helpers for Submit database repositories."""

from sqlalchemy import MetaData, Table


class SubmitTableRepository:
    """Base class for small Submit repositories."""

    def __init__(self, session):
        self.session = session
        self.metadata = MetaData()
        self._tables = {}

    def _table(self, table_name: str) -> Table:
        if table_name not in self._tables:
            self._tables[table_name] = Table(
                table_name,
                self.metadata,
                autoload_with=self.session.get_bind(),
            )
        return self._tables[table_name]
