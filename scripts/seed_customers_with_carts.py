import argparse
import asyncio
import sys
from pathlib import Path

from beanie import init_beanie
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

from app.core.config import settings
from app.core.security import get_password_hash
from app.core.user_role import UserRole
from app.models.cart_model import Cart, CartItem
from app.models.product_model import Product
from app.models.user_model import User


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed customer users with cart items using existing products."
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of customer users to seed. Default: 10",
    )
    parser.add_argument(
        "--password",
        default="Customer@123",
        help="Plain text password used for seeded customers. Default: Customer@123",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to the database.",
    )
    return parser.parse_args()


def build_customer_payload(index: int) -> dict[str, str]:
    return {
        "user_name": f"customer{index:02d}",
        "email": f"customer{index:02d}@seedusers.com",
        "mobile": f"900000{index:04d}",
    }


def pick_cart_items(products: list[Product], user_index: int) -> list[CartItem]:
    if not products:
        return []

    # Deterministic spread: each user gets 3-5 unique products.
    target_items = 3 + (user_index % 3)
    start = (user_index * 7) % len(products)

    selected: list[CartItem] = []
    visited_product_ids = set()
    offset = 0

    while len(selected) < target_items and offset < len(products) * 2:
        product = products[(start + offset) % len(products)]
        offset += 1

        if product.id is None:
            continue

        if not product.variants:
            continue

        if str(product.id) in visited_product_ids:
            continue

        variant_index = (user_index + len(selected)) % len(product.variants)
        variant = product.variants[variant_index]
        qty = min(2 + (user_index % 2), max(1, variant.available_stock))

        if variant.available_stock < 1:
            continue

        product_id = product.id
        visited_product_ids.add(str(product_id))
        selected.append(CartItem(product_id=product_id, sku=variant.sku, quantity=qty))

    return selected


async def seed_customers_with_carts(count: int, password: str, dry_run: bool = False) -> None:
    if count < 10:
        raise SystemExit("Please provide --count >= 10 for this task.")

    await init_beanie(
        connection_string=f"{settings.MONGODB_URL}/{settings.DATABASE_NAME}",
        document_models=[User, Product, Cart],
    )

    products = await Product.find(Product.is_available == True).to_list()  # noqa: E712
    if len(products) < 3:
        raise SystemExit("Need at least 3 available products before creating carts.")

    created_users = 0
    existing_users = 0
    created_carts = 0
    updated_carts = 0
    skipped_carts = 0

    hashed_password = get_password_hash(password)

    for index in range(1, count + 1):
        payload = build_customer_payload(index)

        user = await User.find_one(User.email == payload["email"])
        if user is None:
            if dry_run:
                created_users += 1
                continue

            user = User(
                user_name=payload["user_name"],
                email=payload["email"],
                mobile=payload["mobile"],
                hashed_password=hashed_password,
                role=UserRole.CUSTOMER,
            )
            await user.insert()
            created_users += 1
        else:
            existing_users += 1

        if dry_run:
            created_carts += 1
            continue

        target_items = pick_cart_items(products, index)
        if not target_items:
            skipped_carts += 1
            continue

        if user.id is None:
            skipped_carts += 1
            continue

        user_id = user.id

        cart = await Cart.find_one(Cart.user_id == user_id)
        if cart is None:
            cart = Cart(user_id=user_id, items=target_items)
            await cart.insert()
            created_carts += 1
        else:
            # Replace with deterministic items so reruns keep seed data consistent.
            cart.items = target_items
            await cart.save()
            updated_carts += 1

    mode = "Dry run" if dry_run else "Completed"
    print(f"{mode}: target customer users={count}")
    print(f"Created users: {created_users}")
    print(f"Existing users: {existing_users}")
    print(f"Created carts: {created_carts}")
    print(f"Updated carts: {updated_carts}")
    print(f"Skipped carts: {skipped_carts}")


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_customers_with_carts(count=args.count, password=args.password, dry_run=args.dry_run))
