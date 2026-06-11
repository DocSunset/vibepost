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
    """Additive schema migrations for pre-auth databases.

    create_all() only creates missing tables; it never adds columns to
    existing ones. The only column added since the single-tenant version is
    profiles.user_id. Profiles left with user_id NULL are invisible until
    claimed with: python -m app.manage claim-orphans <email>
    """
    from sqlalchemy import text

    additions = [
        ("profiles", "user_id", "INTEGER REFERENCES users(id)"),
        ("users", "session_epoch", "INTEGER NOT NULL DEFAULT 0"),
        ("invite_tokens", "failed_attempts", "INTEGER NOT NULL DEFAULT 0"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in additions:
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
            if cols and column not in cols:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
