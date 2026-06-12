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
    python -m app.manage revoke-sessions <email> # force-sign-out a user everywhere
    python -m app.manage claim-orphans <email># attach pre-auth profiles to a user
    python -m app.manage reencrypt            # rotate CREDENTIALS_KEY (see incident runbook)
"""

import argparse
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from . import crypto  # noqa: E402
from .database import SessionLocal, engine, Base, run_migrations  # noqa: E402
from .models import Channel, InviteToken, Post, Profile, User, UserSetting  # noqa: E402
from .security import hash_token  # noqa: E402


def _user_by_email(db, email: str) -> User | None:
    return (
        db.query(User)
        .filter(User.email_hash.in_(crypto.email_index_candidates(email)))
        .first()
    )


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
    revoke_sessions = sub.add_parser(
        "revoke-sessions", help="force-sign-out a user everywhere (hijack response)"
    )
    revoke_sessions.add_argument("email")
    claim = sub.add_parser("claim-orphans", help="attach profiles with no owner to a user")
    claim.add_argument("email")
    sub.add_parser(
        "reencrypt",
        help="re-encrypt all data with the current CREDENTIALS_KEY "
             "(set CREDENTIALS_KEY_OLD to the previous key first)",
    )

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
            u = _user_by_email(db, args.email)
            if not u:
                sys.exit(f"No user with email {args.email}")
            u.is_admin = True
            db.commit()
            print(f"{u.email} is now an admin")
        elif args.cmd == "demote":
            u = _user_by_email(db, args.email)
            if not u:
                sys.exit(f"No user with email {args.email}")
            u.is_admin = False
            db.commit()
            print(f"{u.email} is no longer an admin")
        elif args.cmd == "revoke-sessions":
            u = _user_by_email(db, args.email)
            if not u:
                sys.exit(f"No user with email {args.email}")
            u.session_epoch = (u.session_epoch or 0) + 1
            db.commit()
            print(f"All sessions for {u.email} are now invalid")
        elif args.cmd == "claim-orphans":
            u = _user_by_email(db, args.email)
            if not u:
                sys.exit(f"No user with email {args.email}")
            n = db.query(Profile).filter(Profile.user_id.is_(None)).update({Profile.user_id: u.id})
            db.commit()
            print(f"Attached {n} orphaned profile(s) to {u.email}")
        elif args.cmd == "reencrypt":
            # The ORM decrypts on load (old key via CREDENTIALS_KEY_OLD) and
            # encrypts on write (current key); flag_modified forces the write
            # even though the plaintext value is unchanged.
            from sqlalchemy.orm.attributes import flag_modified
            count = 0
            for u in db.query(User).all():
                u.email_hash = crypto.email_index(u.email)
                flag_modified(u, "email")
                count += 1
            for s in db.query(UserSetting).all():
                if s.value is not None:
                    flag_modified(s, "value")
                    count += 1
            for c in db.query(Channel).all():
                if c.credentials is not None:
                    flag_modified(c, "credentials")
                    count += 1
            for p in db.query(Post).all():
                if p.text is not None:
                    flag_modified(p, "text")
                    count += 1
            db.commit()
            print(f"Re-encrypted {count} values with the current CREDENTIALS_KEY.")
            print("You can now unset CREDENTIALS_KEY_OLD.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
