from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    SELLER = "seller"
    CUSTOMER = "customer"
    SUPPORT = "support"
