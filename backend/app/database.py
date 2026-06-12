# vibepost - social media scheduling and posting tool
# Copyright (C) 2026  Travis West
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import DB_PATH

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations():
    """Additive schema migrations plus in-place encryption of legacy rows.

    create_all() only creates missing tables; it never adds columns to
    existing ones. Profiles left with user_id NULL are invisible until
    claimed with: python -m app.manage claim-orphans <email>
    """
    from sqlalchemy import text

    additions = [
        ("profiles", "user_id", "INTEGER REFERENCES users(id)"),
        ("users", "session_epoch", "INTEGER NOT NULL DEFAULT 0"),
        ("users", "email_hash", "TEXT"),
        ("invite_tokens", "failed_attempts", "INTEGER NOT NULL DEFAULT 0"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in additions:
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
            if cols and column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))

        # Passwords were removed entirely (sign-in is passkey or emailed link)
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        if "password_hash" in user_cols:
            conn.execute(text("ALTER TABLE users DROP COLUMN password_hash"))

        _encrypt_legacy_rows(conn)
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_hash ON users(email_hash)"
        ))


def _encrypt_legacy_rows(conn):
    """One-way data migration: encrypt any plaintext rows left from before
    encryption-at-rest landed. Idempotent — encrypted values are tagged and
    skipped."""
    from sqlalchemy import text
    from . import crypto

    targets = [
        ("users", "email", "user.email"),
        ("user_settings", "value", "user_setting.value"),
        ("channels", "credentials", "channel.credentials"),
        ("posts", "text", "post.text"),
    ]
    for table, column, purpose in targets:
        cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
        if column not in cols:
            continue
        rows = conn.execute(text(
            f"SELECT id, {column} FROM {table} "
            f"WHERE {column} IS NOT NULL AND {column} NOT LIKE 'enc1:%'"
        )).fetchall()
        for row_id, value in rows:
            params = {"v": crypto.encrypt(value, purpose), "id": row_id}
            if table == "users":
                params["h"] = crypto.email_index(value)
                conn.execute(text(
                    "UPDATE users SET email = :v, email_hash = :h WHERE id = :id"
                ), params)
            else:
                conn.execute(text(
                    f"UPDATE {table} SET {column} = :v WHERE id = :id"
                ), params)
