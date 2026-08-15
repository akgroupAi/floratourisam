"""Bring the database in line with the models, then tell Alembic where it stands.

Use this when `alembic upgrade` cannot run — which is the case on this deployment,
because `alembic_version` is empty and `upgrade` therefore replays every migration from
the beginning and fails on columns that already exist.

What it does, in order:

  1. Reports every table and column the models define but the database lacks
  2. Creates them  (--apply)
  3. Writes the current revision into alembic_version  (--stamp)

Safe by design: it only ever CREATEs and ADDs. It never drops a table, drops a column,
alters a type, or deletes a row, so it cannot lose data. Re-running it is harmless.

    python scripts/sync_schema.py                    # report only, changes nothing
    python scripts/sync_schema.py --apply            # create what is missing
    python scripts/sync_schema.py --apply --stamp    # ...and mark Alembic up to date

After a successful --apply --stamp, normal `alembic upgrade <revision>` works again.
"""

import argparse
import asyncio
import os
import sys

# Add to path to allow importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.schema import CreateColumn

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401  (side effect: registers every model)

# The newest revision in the live migration chain. Bump this when a migration is added.
CURRENT_REVISION = "a1b2c3d4e5f6"


async def live_schema(conn) -> dict[str, set[str]]:
    """Every table and column the database actually has."""
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


def column_ddl(table: str, column) -> str | None:
    """ALTER TABLE ... ADD COLUMN for a model column, or None if unsafe to add.

    A NOT NULL column with no default cannot be added to a table that already has rows,
    so those are reported for a human to decide rather than guessed at.
    """
    if not column.nullable and column.server_default is None and not column.primary_key:
        return None
    compiled = str(CreateColumn(column).compile(dialect=engine.dialect))
    return f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS {compiled}'


async def stamp(conn, revision: str) -> None:
    """Write the revision into alembic_version — the same thing `alembic stamp` does.

    Done directly rather than through the Alembic API so it does not depend on env.py
    loading correctly, which is part of what is broken here.
    """
    await conn.execute(
        text(
            "CREATE TABLE IF NOT EXISTS alembic_version ("
            "version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        )
    )
    await conn.execute(text("DELETE FROM alembic_version"))
    await conn.execute(
        text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
        {"rev": revision},
    )


async def main(apply: bool, do_stamp: bool, revision: str) -> int:
    # Checked before connecting so the mistake is caught immediately.
    if do_stamp and not apply:
        print("Refusing to stamp without --apply — stamp only a schema you have verified.")
        return 1

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

        if missing_tables:
            print(f"\nMISSING TABLES ({len(missing_tables)}):")
            for name in missing_tables:
                print(f"  - {name}")

        if missing_columns:
            print(f"\nMISSING COLUMNS ({len(missing_columns)}):")
            for table_name, column_name in missing_columns:
                print(f"  - {table_name}.{column_name}")

        if not missing_tables and not missing_columns:
            print("Schema is already in line with the models — nothing to create.")

        if not apply:
            if missing_tables or missing_columns:
                print("\nNothing was changed. Re-run with --apply to create these.")
                return 1
        else:
            unsafe: list[str] = []

            if missing_tables:
                print("\nCreating tables...")
                # create_all resolves foreign-key dependencies itself. Creating them one
                # at a time in name order fails as soon as one table references another
                # that sorts later — booking_documents → booking_guests, for instance.
                targets = [Base.metadata.tables[name] for name in missing_tables]
                await conn.run_sync(
                    lambda sync_conn: Base.metadata.create_all(
                        sync_conn, tables=targets, checkfirst=True
                    )
                )
                for name in missing_tables:
                    print(f"  created {name}")

            if missing_columns:
                print("\nAdding columns...")
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
                print("\nStamp skipped — resolve these first so you stamp a verified schema.")
                return 1

        if do_stamp:
            await stamp(conn, revision)
            print(f"\nAlembic stamped at {revision}.")
            print("`alembic current` will now report this, and `alembic upgrade` works again.")

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply", action="store_true", help="Create missing tables and columns"
    )
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="Write the revision into alembic_version (requires --apply)",
    )
    parser.add_argument(
        "--revision",
        default=CURRENT_REVISION,
        help=f"Revision to stamp (default: {CURRENT_REVISION})",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.apply, args.stamp, args.revision)))
