"""One command to bring the database up to date, whatever state Alembic is in.

Alembic on this deployment has been unreliable: `alembic_version` gets emptied, and
`create_all` (DEBUG=True) builds schema behind Alembic's back. Running `alembic upgrade`
blindly then fails on columns that already exist. This script looks first and picks the
right approach.

    python scripts/migrate.py           # report what it would do - changes nothing
    python scripts/migrate.py --run     # do it

It decides between three cases:

  REPAIR   alembic_version is empty but tables exist.
           -> create anything missing, then stamp. Running migrations would fail.

  UPGRADE  Alembic is tracking correctly and is behind.
           -> hand over to `alembic upgrade`, the normal path.

  SYNC     Alembic is current but the models moved ahead (create_all drift).
           -> add the missing pieces and re-stamp.

Only ever CREATEs and ADDs - never drops a table, drops a column, alters a type, or
deletes a row. It cannot lose data, and re-running it is harmless.
"""

import argparse
import asyncio
import os
import pathlib
import subprocess
import sys

# Add to path to allow importing app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.schema import CreateColumn

from app.db.base import Base
from app.db.session import engine
import app.models  # noqa: F401  (side effect: registers every model)

# Head of the live migration chain. Bump when a migration is added.
TARGET_REVISION = "6d7a99e3eb2d"

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Inspection ────────────────────────────────────────────────


async def current_revision(conn) -> str | None:
    """What Alembic thinks the database is at, or None if it has no idea."""
    exists = (
        await conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'alembic_version'"
            )
        )
    ).scalar()
    if not exists:
        return None
    return (await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))).scalar()


async def live_schema(conn) -> dict[str, set[str]]:
    rows = (
        await conn.execute(
            text(
                "SELECT table_name, column_name FROM information_schema.columns "
                "WHERE table_schema = 'public'"
            )
        )
    ).all()
    schema: dict[str, set[str]] = {}
    for table_name, column_name in rows:
        schema.setdefault(table_name, set()).add(column_name)
    return schema


def find_drift(actual: dict[str, set[str]]):
    """Tables and columns the models define but the database lacks."""
    missing_tables, missing_columns = [], []
    for table_name, table in sorted(Base.metadata.tables.items()):
        if table_name not in actual:
            missing_tables.append(table_name)
            continue
        for column in table.columns:
            if column.name not in actual[table_name]:
                missing_columns.append((table_name, column.name))
    return missing_tables, missing_columns


# ── Actions ───────────────────────────────────────────────────


def column_ddl(table: str, column) -> str | None:
    """ADD COLUMN statement, or None when it cannot be added safely.

    A NOT NULL column with no default cannot be added to a table that already has rows.
    """
    if not column.nullable and column.server_default is None and not column.primary_key:
        return None
    return (
        f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS '
        f"{str(CreateColumn(column).compile(dialect=engine.dialect))}"
    )


async def apply_drift(conn, missing_tables, missing_columns) -> list[str]:
    """Create the missing schema. Returns anything that needs a human."""
    unsafe = []

    if missing_tables:
        # create_all resolves foreign-key order itself; creating one at a time in name
        # order fails when a table references another that sorts later.
        targets = [Base.metadata.tables[name] for name in missing_tables]
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(
                sync_conn, tables=targets, checkfirst=True
            )
        )
        for name in missing_tables:
            print(f"    created table  {name}")

    for table_name, column_name in missing_columns:
        column = Base.metadata.tables[table_name].columns[column_name]
        ddl = column_ddl(table_name, column)
        if ddl is None:
            unsafe.append(f"{table_name}.{column_name}")
            continue
        await conn.execute(text(ddl))
        print(f"    added column   {table_name}.{column_name}")

    return unsafe


async def stamp(conn, revision: str) -> None:
    """Write the revision into alembic_version - what `alembic stamp` does.

    Done with SQL rather than the Alembic API so it does not depend on env.py loading,
    which is part of what breaks on this deployment.
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
        text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": revision}
    )


def check_revision_files() -> list[str]:
    """Look for duplicate revision ids before handing anything to Alembic.

    A duplicate makes Alembic report "Cycle is detected in revisions" and list every
    revision, which points nowhere useful. Catching it here names the actual files.

    Also flags migration files not tracked by git, since those are usually the cause -
    a file created directly on a server will not exist anywhere else.
    """
    import collections
    import re

    versions = pathlib.Path(REPO_ROOT) / "alembic" / "versions"
    revs = collections.defaultdict(list)
    for f in sorted(versions.glob("*.py")):
        text_content = f.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"""^revision\s*=\s*["']([^"']+)""", text_content, re.M)
        if m:
            revs[m.group(1)].append(f.name)

    problems = []
    for rev, files in revs.items():
        if len(files) > 1:
            problems.append(f"revision {rev} is defined in {len(files)} files: " + ", ".join(files))

    # Untracked files are only a warning: a migration you just wrote is untracked until
    # you commit it. On a server, though, an untracked migration means someone created
    # it there by hand, which is the usual source of a duplicate.
    warnings = []
    tracked = set()
    try:
        result = subprocess.run(
            ["git", "ls-files", "alembic/versions"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if result.returncode == 0:
            tracked = {pathlib.Path(line).name for line in result.stdout.split() if line}
    except Exception:
        pass

    if tracked:
        untracked = sorted({f.name for f in versions.glob("*.py")} - tracked)
        if untracked:
            warnings.append(
                "migration files not tracked by git: " + ", ".join(untracked)
                + "\n    (expected for one you just wrote; on a server it means someone "
                "created it there by hand)"
            )

    return problems, warnings


def run_alembic_upgrade(revision: str) -> bool:
    """Hand over to Alembic for the normal path. Returns True on success."""
    print(f"    running: alembic upgrade {revision}")
    result = subprocess.run(
        ["alembic", "upgrade", revision],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print("   ", result.stdout.strip().replace("\n", "\n    "))
    if result.returncode != 0:
        print("   ", (result.stderr or "").strip()[-1500:])
        return False
    return True


# ── Main ──────────────────────────────────────────────────────


async def main(run: bool, revision: str) -> int:
    # Checked before connecting: broken migration files are a local problem and the
    # message is clearer without a database error on top of it.
    problems, warnings = check_revision_files()

    if warnings:
        print("Note")
        for warning in warnings:
            print(f"  - {warning}")
        print()

    if problems:
        print("MIGRATION FILES ARE BROKEN\n")
        for problem in problems:
            print(f"  - {problem}")
        print(
            "\nAlembic cannot build a valid history from these. A duplicate revision id"
            "\nsurfaces as a misleading 'Cycle is detected' error listing every revision,"
            "\nwhich is why the real cause is hard to spot."
            "\n\nDelete or renumber the offending file, then re-run."
        )
        return 1

    async with engine.begin() as conn:
        current = await current_revision(conn)
        actual = await live_schema(conn)
        missing_tables, missing_columns = find_drift(actual)
        table_count = len(actual)

    has_drift = bool(missing_tables or missing_columns)

    print("Database state")
    print(f"  tables present     {table_count}")
    print(f"  alembic revision   {current or '(none - Alembic is not tracking this database)'}")
    print(f"  target revision    {revision}")
    print(f"  missing tables     {len(missing_tables)}")
    print(f"  missing columns    {len(missing_columns)}")

    # Decide the strategy.
    if current is None and table_count > 0:
        plan = "REPAIR"
        why = (
            "Tables exist but Alembic has no revision recorded. `alembic upgrade` would "
            "replay every migration from the start and fail on existing columns."
        )
    elif current is None:
        plan = "UPGRADE"
        why = "Empty database - run the migrations normally."
    elif current == revision and not has_drift:
        plan = "NOTHING"
        why = "Alembic is at the target revision and the schema matches the models."
    elif current == revision and has_drift:
        plan = "SYNC"
        why = (
            "Alembic is at the target revision but the models have moved ahead - "
            "schema was likely created outside Alembic (DEBUG create_all)."
        )
    else:
        plan = "UPGRADE"
        why = f"Alembic is tracking and behind ({current} -> {revision})."

    print(f"\nPlan: {plan}")
    print(f"  {why}")

    if missing_tables:
        print("\n  tables to create:")
        for name in missing_tables:
            print(f"    - {name}")
    if missing_columns:
        print("\n  columns to add:")
        for table_name, column_name in missing_columns:
            print(f"    - {table_name}.{column_name}")

    if plan == "NOTHING":
        print("\nNothing to do.")
        return 0

    if not run:
        print("\nNothing was changed. Re-run with --run to apply.")
        return 0

    print("\nApplying...")

    if plan == "UPGRADE":
        if not run_alembic_upgrade(revision):
            print(
                "\nAlembic failed. If it complains a column already exists, the database "
                "is ahead of the version table - re-run this script, which will now "
                "detect REPAIR."
            )
            return 1
        print("\nDone.")
        return 0

    # REPAIR and SYNC both create the missing schema, then stamp.
    async with engine.begin() as conn:
        unsafe = await apply_drift(conn, missing_tables, missing_columns)

        if unsafe:
            print("\n  NOT added - NOT NULL with no default, needs a decision:")
            for name in unsafe:
                print(f"    - {name}")
            print("    Add it nullable, backfill, then set NOT NULL.")
            print("\nStamp skipped - resolve these so you stamp a schema you have verified.")
            return 1

        await stamp(conn, revision)
        print(f"    stamped        {revision}")

    print("\nDone. `alembic current` will report the revision, and `alembic upgrade` works again.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run", action="store_true", help="Apply the plan (default: report only)")
    parser.add_argument(
        "--revision", default=TARGET_REVISION, help=f"Target revision (default: {TARGET_REVISION})"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.run, args.revision)))
