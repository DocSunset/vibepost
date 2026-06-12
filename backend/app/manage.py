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

"""Operator CLI for vibepost.

Usage (from the backend/ directory, or inside the container):

    python -m app.manage invite new [--note "for alice"] [--days 14]
    python -m app.manage invite list
    python -m app.manage invite revoke <id>
    python -m app.manage users
    python -m app.manage promote <email>      # grant admin (the only way to get admin)
    python -m app.manage demote <email>       # remove admin
    python -m app.manage claim-orphans <email># attach pre-auth profiles to a user
"""

import argparse
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from .database import SessionLocal, engine, Base, run_migrations  # noqa: E402
from .models import InviteToken, Profile, User  # noqa: E402
from .security import hash_token  # noqa: E402


def main():
    Base.metadata.create_all(bind=engine)
    run_migrations()

    parser = argparse.ArgumentParser(prog="python -m app.manage")
    sub = parser.add_subparsers(dest="cmd", required=True)

    invite = sub.add_parser("invite", help="manage invite tokens")
    invite_sub = invite.add_subparsers(dest="invite_cmd", required=True)
    new = invite_sub.add_parser("new", help="create a new invite token")
    new.add_argument("--note", default="", help="who/what this invite is for")
    new.add_argument("--days", type=int, default=14, help="days until expiry")
    invite_sub.add_parser("list", help="list invite tokens")
    revoke = invite_sub.add_parser("revoke", help="revoke an invite token")
    revoke.add_argument("id", type=int)

    sub.add_parser("users", help="list user accounts")
    promote = sub.add_parser("promote", help="grant admin to a user")
    promote.add_argument("email")
    demote = sub.add_parser("demote", help="remove admin from a user")
    demote.add_argument("email")
    claim = sub.add_parser("claim-orphans", help="attach profiles with no owner to a user")
    claim.add_argument("email")

    args = parser.parse_args()
    db = SessionLocal()
    try:
        if args.cmd == "invite":
            if args.invite_cmd == "new":
                token = secrets.token_urlsafe(24)
                db.add(InviteToken(
                    token_hash=hash_token(token),
                    note=args.note,
                    expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=args.days),
                ))
                db.commit()
                print(f"Invite token (shown once, expires in {args.days} days):\n\n  {token}\n")
            elif args.invite_cmd == "list":
                for i in db.query(InviteToken).order_by(InviteToken.created_at).all():
                    state = "revoked" if i.revoked else ("used" if i.used_at else "open")
                    print(f"  #{i.id}  {state:8s}  expires={i.expires_at}  note={i.note!r}")
            elif args.invite_cmd == "revoke":
                i = db.query(InviteToken).filter(InviteToken.id == args.id).first()
                if not i:
                    sys.exit(f"No invite with id {args.id}")
                i.revoked = True
                db.commit()
                print(f"Invite #{args.id} revoked")
        elif args.cmd == "users":
            for u in db.query(User).order_by(User.created_at).all():
                role = "admin" if u.is_admin else "user"
                print(f"  #{u.id}  {u.email}  ({role}, since {u.created_at:%Y-%m-%d})")
        elif args.cmd == "promote":
            u = db.query(User).filter(User.email == args.email.strip().lower()).first()
            if not u:
                sys.exit(f"No user with email {args.email}")
            u.is_admin = True
            db.commit()
            print(f"{u.email} is now an admin")
        elif args.cmd == "demote":
            u = db.query(User).filter(User.email == args.email.strip().lower()).first()
            if not u:
                sys.exit(f"No user with email {args.email}")
            u.is_admin = False
            db.commit()
            print(f"{u.email} is no longer an admin")
        elif args.cmd == "claim-orphans":
            u = db.query(User).filter(User.email == args.email.strip().lower()).first()
            if not u:
                sys.exit(f"No user with email {args.email}")
            n = db.query(Profile).filter(Profile.user_id.is_(None)).update({Profile.user_id: u.id})
            db.commit()
            print(f"Attached {n} orphaned profile(s) to {u.email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
