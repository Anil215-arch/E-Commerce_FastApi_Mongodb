import argparse
import asyncio
import os
import sys
from getpass import getpass
from pathlib import Path

from beanie import init_beanie
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.user_role import UserRole
from app.models.user_model import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a single super admin user into MongoDB.")
    parser.add_argument("--user-name", dest="user_name", default=os.getenv("SUPER_ADMIN_USER_NAME"))
    parser.add_argument("--email", default=os.getenv("SUPER_ADMIN_EMAIL"))
    parser.add_argument("--mobile", default=os.getenv("SUPER_ADMIN_MOBILE"))
    parser.add_argument("--password", default=os.getenv("SUPER_ADMIN_PASSWORD"))
    return parser.parse_args()


def resolve_inputs(args: argparse.Namespace) -> tuple[str, str, str, str]:
    user_name = (args.user_name or "").strip()
    email = (args.email or "").strip().lower()
    mobile = (args.mobile or "").strip()
    password = args.password or getpass("Super admin password: ")

    missing_fields = [
        field_name
        for field_name, value in {
            "user_name": user_name,
            "email": email,
            "mobile": mobile,
            "password": password,
        }.items()
        if not value
    ]
    if missing_fields:
        raise SystemExit(f"Missing required values: {', '.join(missing_fields)}")

    return user_name, email, mobile, password


async def seed_super_admin(user_name: str, email: str, mobile: str, password: str) -> None:
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    database = client[settings.DATABASE_NAME]

    try:
        await init_beanie(database=database, document_models=[User])

        existing_super_admin = await User.find_one(User.role == UserRole.SUPER_ADMIN)
        if existing_super_admin:
            print(f"Skipped: super admin already exists with email '{existing_super_admin.email}'.")
            return

        existing_user_by_email = await User.find_one(User.email == email)
        if existing_user_by_email:
            print(f"Skipped: user with email '{email}' already exists.")
            return

        existing_user_by_name = await User.find_one(User.user_name == user_name)
        if existing_user_by_name:
            print(f"Skipped: username '{user_name}' is already taken.")
            return

        super_admin = User(
            user_name=user_name,
            email=email,
            hashed_password=get_password_hash(password),
            mobile=mobile,
            role=UserRole.SUPER_ADMIN,
        )
        await super_admin.insert()
        print(f"Created super admin '{super_admin.user_name}' with email '{super_admin.email}'.")
    finally:
        client.close()


if __name__ == "__main__":
    arguments = parse_args()
    input_user_name, input_email, input_mobile, input_password = resolve_inputs(arguments)
    asyncio.run(seed_super_admin(input_user_name, input_email, input_mobile, input_password))
