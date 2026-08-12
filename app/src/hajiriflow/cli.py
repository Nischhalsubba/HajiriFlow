import argparse
import getpass

from sqlalchemy import select

from hajiriflow.core.config import get_settings
from hajiriflow.db.models.identity import UserAccount
from hajiriflow.db.session import session_scope
from hajiriflow.identity.bootstrap import seed_identity_catalog
from hajiriflow.identity.permissions import ScopeType
from hajiriflow.identity.service import IdentityService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hajiriflow")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("seed-identity", help="Seed system roles and permissions.")
    create_admin = commands.add_parser(
        "create-admin",
        help="Create or promote the first system administrator.",
    )
    create_admin.add_argument("--username", required=True)
    create_admin.add_argument("--display-name", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    with session_scope() as session:
        seed_identity_catalog(session)
        if args.command == "seed-identity":
            print("Identity catalog is ready.")
            return

        service = IdentityService(session, settings)
        username = service.normalize_username(args.username)
        user = session.scalar(
            select(UserAccount).where(UserAccount.username == username)
        )
        if user is None:
            password = getpass.getpass("Initial password: ")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                raise SystemExit("Passwords do not match.")
            user = service.create_user(
                username=username,
                display_name=args.display_name,
                password=password,
                must_change_password=True,
            )
        service.assign_role(
            user_id=user.id,
            role_code="system_administrator",
            actor_user_id=user.id,
            scope_type=ScopeType.GLOBAL,
        )
        print(f"System administrator ready: {user.username}")


if __name__ == "__main__":
    main()
