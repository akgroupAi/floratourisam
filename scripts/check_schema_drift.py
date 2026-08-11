"""Compare the SQLAlchemy models against the live database schema.

Why this exists: with DEBUG=True the app builds schema via ``Base.metadata.create_all``,
which creates *missing tables* but never adds a column to a table that already exists.
So a new column on an existing table silently never lands, and the app fails at runtime.

Read-only by default. Run before stamping Alembic, so you stamp a schema you have
actually verified rather than one you assume is current.

    python scripts/check_schema_drift.py            # report only
    python scripts/check_schema_drift.py --fix      # add missing columns, then re-check

--fix only ever ADDs missing columns. It never drops or alters anything, so it cannot
destroy data. Columns it cannot add safely (NOT NULL with no default) are reported for
you to handle by hand.
"""

import argparse
import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.schema import CreateColumn

# Importing the app package registers every model on Base.metadata.
from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401  (side effect: registers all models)


async def live_schema(conn) -> dict[str, set[str]]:
    """Every table and its columns, as the database actually has them."""
    rows = (
        await conn.execute(
            text(
                """
                SELECT table_name, column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                """
            )
        )
    ).all()
    schema: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        schema.setdefault(table_name, set()).add(column_name)
    return schema


def column_ddl(table, column) -> str | None:
    """ALTER TABLE ... ADD COLUMN for a model column, or None if unsafe to add."""
    compiled = str(CreateColumn(column).compile(dialect=engine.dialect))
    # A NOT NULL column with no default cannot be added to a table with rows.
    if not column.nullable and column.server_default is None and not column.primary_key:
        return None
    return f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {compiled}'


async def main(fix: bool) -> int:
    async with engine.begin() as conn:
        actual = await live_schema(conn)

        missing_tables: list[str] = []
        missing_columns: list[tuple[str, str]] = []

        for table_name, table in sorted(Base.metadata.tables.items()):
            if table_name not in actual:
                missing_tables.append(table_name)
                continue
            for column in table.columns:
                if column.name not in actual[table_name]:
                    missing_columns.append((table_name, column.name))

        if not missing_tables and not missing_columns:
            print("OK — every model table and column exists in the database.")
            return 0

        if missing_tables:
            print(f"\nMISSING TABLES ({len(missing_tables)}):")
            for name in missing_tables:
                print(f"  - {name}")
            print("  Restart the app with DEBUG=True once, or run the relevant migration.")

        if missing_columns:
            print(f"\nMISSING COLUMNS ({len(missing_columns)}):")
            for table_name, column_name in missing_columns:
                print(f"  - {table_name}.{column_name}")

        if not fix:
            print("\nRe-run with --fix to add the missing columns.")
            return 1

        print("\nAdding missing columns...")
        unsafe: list[str] = []
        for table_name, column_name in missing_columns:
            column = Base.metadata.tables[table_name].columns[column_name]
            ddl = column_ddl(table_name, column)
            if ddl is None:
                unsafe.append(f"{table_name}.{column_name}")
                continue
            await conn.execute(text(ddl))
            print(f"  added {table_name}.{column_name}")

        if unsafe:
            print("\nNOT added — NOT NULL with no default, needs a manual decision:")
            for name in unsafe:
                print(f"  - {name}")
            print("  Add it nullable, backfill a value, then set NOT NULL.")

        remaining = len(missing_tables) + len(unsafe)
        print(f"\nDone. {remaining} item(s) still need attention.")
        return 0 if remaining == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix", action="store_true", help="Add missing columns (never drops anything)"
    )
    sys.exit(asyncio.run(main(parser.parse_args().fix)))
