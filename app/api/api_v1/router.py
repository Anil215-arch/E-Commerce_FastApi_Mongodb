from fastapi import APIRouter, Depends
from app.core.dependencies import RoleChecker
from app.core.user_role import UserRole

# Import nested modules
from app.api.api_v1.endpoints.public import auth, products as public_products, categories as public_categories, reviews as public_reviews
from app.api.api_v1.endpoints.customer import profile, cart, orders as customer_orders, notifications, device_tokens, reviews as customer_reviews
from app.api.api_v1.endpoints.seller import products as seller_products, orders as seller_orders, dashboard as seller_dashboard
from app.api.api_v1.endpoints.seller import inventory as seller_inventory
from app.api.api_v1.endpoints.admin import users as admin_users, categories as admin_categories, products as admin_products, orders as admin_orders, dashboard as admin_dashboard
# Inside router.py
from app.api.api_v1.endpoints import wishlist_api


api_router = APIRouter()

# ==========================================
# 1. PUBLIC NAMESPACE (No role lock)
# ==========================================
api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
api_router.include_router(public_products.router, prefix="/products", tags=["Products (Public)"])
api_router.include_router(public_categories.router, prefix="/categories", tags=["Categories (Public)"])
api_router.include_router(public_reviews.router, tags=["Reviews (Public)"])

# ==========================================
# 2. CUSTOMER NAMESPACE (Standard auth required)
# ==========================================
api_router.include_router(profile.router, prefix="/customer/profile", tags=["Customer Profile"])
api_router.include_router(cart.router, prefix="/customer/cart", tags=["Customer Cart"])
api_router.include_router(customer_orders.router, prefix="/customer/orders", tags=["Customer Orders"])
api_router.include_router(notifications.router, prefix="/customer/notifications", tags=["Customer Notifications"])
api_router.include_router(device_tokens.router, prefix="/customer/device-tokens", tags=["Device Tokens"])
api_router.include_router(customer_reviews.router, prefix="/customer/reviews", tags=["Customer Reviews"])
api_router.include_router(wishlist_api.router, prefix="/customers/wishlist", tags=["Wishlist"])

# ==========================================
# 3. SELLER NAMESPACE (Strict Seller/Admin Lock)
# ==========================================
api_router.include_router(
    seller_products.router, 
    prefix="/seller/products", 
    tags=["Seller Inventory"],
    dependencies=[Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)
api_router.include_router(
    seller_orders.router, 
    prefix="/seller/orders", 
    tags=["Seller Fulfillment"],
    dependencies=[Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)
api_router.include_router(
    seller_dashboard.router, 
    prefix="/seller/dashboard", 
    tags=["Seller Dashboard"],
    dependencies=[Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)
api_router.include_router(
    seller_inventory.router,
    prefix="/seller/inventory",
    tags=["Seller Inventory Management"],
    dependencies=[Depends(RoleChecker([UserRole.SELLER, UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)


# ==========================================
# 4. ADMIN NAMESPACE (Strict Admin Lock)
# ==========================================
api_router.include_router(
    admin_users.router, 
    prefix="/admin/users", 
    tags=["Admin Users"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)

api_router.include_router(
    admin_categories.router, 
    prefix="/admin/categories", 
    tags=["Admin Categories"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)

api_router.include_router(
    admin_products.router, 
    prefix="/admin/products", 
    tags=["Admin Moderation"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)

api_router.include_router(
    admin_orders.router, 
    prefix="/admin/orders", 
    tags=["Admin Intervention"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)

api_router.include_router(
    admin_dashboard.router, 
    prefix="/admin/dashboard", 
    tags=["Admin Dashboard"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.SUPER_ADMIN]))]
)
