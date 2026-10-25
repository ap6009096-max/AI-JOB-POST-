from sqlalchemy import JSON, TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB


class PortableJSONB(TypeDecorator):
    """JSONB on Postgres, JSON on SQLite test fixtures."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class PortableVector(TypeDecorator):
    """pgvector(768) on Postgres; JSON list on SQLite test fixtures."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector

            return dialect.type_descriptor(Vector(768))
        return dialect.type_descriptor(JSON())
