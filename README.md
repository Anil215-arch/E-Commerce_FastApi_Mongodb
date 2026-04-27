# E-Commerce Platform API (FastAPI + MongoDB)

Production-style backend for a multi-seller e-commerce system built with FastAPI, Beanie, and MongoDB.

It includes JWT auth with refresh/revocation, email OTP flows, catalog and cart management, distributed checkout across sellers, and invoice PDF generation.

## Contents

1. Overview
2. Tech Stack
3. Architecture
4. Project Structure
5. Quick Start
6. Environment Variables
7. Running the API
8. API Modules
9. Core Workflows
10. Database Model Notes
11. Scripts (Seed, Migration, Audit)
12. Testing
13. Operational Constraints
14. Troubleshooting

## Overview

- API base path: `/api/v1`
- Interactive docs: `/docs`
- ReDoc: `/redoc`
- Static media mount: `/media`
- Response envelope:
  - success: `{ "message", "status": "success", "data" }`
  - error: `{ "message", "status": "error", "data" }`

## Tech Stack

- Python 3.11+
- FastAPI
- MongoDB
- Beanie ODM + Motor
- Pydantic v2
- JWT (`pyjwt`) + `pwdlib` password hashing
- FastAPI-Mail (SMTP)
- WeasyPrint + Jinja2 (invoice PDF)
- Pytest

## Architecture

The app uses a clear layered design:

- `api` layer: HTTP routes and dependency wiring
- `services` layer: business logic
- `models` layer: Beanie documents and indexes
- `schemas` layer: request/response validation contracts
- `core` layer: config, DB init, auth dependencies, security
- `utils` layer: response helpers, pagination, email, mappers

Runtime startup flow:

1. App bootstraps in `main.py`.
2. Lifespan event calls `init_db()` and registers all Beanie models.
3. Static folder `media/products` is created and mounted at `/media`.
4. Versioned router is mounted under `/api/v1`.
5. Global exception handlers standardize error responses.

## Project Structure

```text
.
|- main.py
|- requirements.txt
|- .env.example
|- app/
|  |- api/api_v1/endpoints/
|  |- core/
|  |- models/
|  |- schemas/
|  |- services/
|  |- templates/invoice.html
|  `- utils/
|- scripts/
`- tests/
```

## Quick Start

### 1) Clone and enter the project

```powershell
git clone <your-repo-url>
cd E-Commerce-PlateForm_fastapi
```

### 2) Create and activate a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```powershell
pip install -r requirements.txt
```

### 4) Configure environment

```powershell
Copy-Item .env.example .env
```

Update `.env` values, especially `SECRET_KEY` and mail credentials.

### 5) Start MongoDB

Ensure MongoDB is reachable at `MONGODB_URL` (default: `mongodb://localhost:27017`).

### 6) Run the API

```powershell
uvicorn main:app --reload
```

API should be available at `http://127.0.0.1:8000`.

## Environment Variables

The app reads config from `.env` via Pydantic Settings.

Minimum required:

```env
PROJECT_NAME=E-Commerce Platform
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=e_commerce

SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

MAIL_USERNAME=your-smtp-username
MAIL_PASSWORD=your-smtp-password
MAIL_FROM=noreply@yourdomain.com
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=true
MAIL_SSL_TLS=false
```

Notes:

- `SECRET_KEY` is validated at startup and must not be empty.
- OTP/email routes require valid SMTP settings.

## Running the API

```powershell
uvicorn main:app --reload
```

Important endpoints:

- `GET /` health/welcome message
- `GET /docs` Swagger UI
- `GET /redoc` ReDoc UI

## API Modules

All routes are under `/api/v1`.

### Users (`/users`)

- `POST /register`
- `POST /login`
- `POST /refresh`
- `POST /logout`
- `GET /me`
- `PATCH /me`
- `PATCH /change-password`
- `POST /me/addresses`
- `DELETE /me/addresses/{address_index}`
- Admin/Super Admin routes for user list, role updates, user deletion

### Authentication / OTP (`/auth`)

- `POST /verify-registration`
- `POST /resend-otp`
- `POST /forgot-password`
- `POST /reset-password`

### Products (`/products`)

- Create, update, soft delete products
- Upload product images
- Variant add/update/delete
- Product listing with search/filter/sort/pagination

### Categories (`/categories`)

- Create/update/delete categories (admin scopes)
- List categories
- Category tree endpoint

### Cart (`/cart`)

- Get cart
- Add item
- Update item quantity
- Remove item

### Orders (`/orders`)

- Checkout
- List my orders
- Get order details
- Update status (role-restricted)
- Cancel order
- Get invoice
- Download invoice PDF

## Core Workflows

### 1) Registration + OTP Verification

1. User registers (`/users/register`) with `is_verified=False`.
2. OTP is generated, hashed, stored, and emailed.
3. User verifies OTP (`/auth/verify-registration`).
4. Account becomes verified and can log in.

Security details:

- OTP is stored hashed (not plaintext).
- OTP expires in 10 minutes.
- OTP records use TTL cleanup.
- OTP purpose is strict (`registration` vs `password_reset`).

### 2) JWT Session Flow

1. Login returns access + refresh tokens.
2. Access token is used on protected routes.
3. Refresh endpoint rotates and revokes used refresh token.
4. Logout revokes both access and refresh token JTIs.

### 3) Catalog Query Flow

- Search mode uses text search and offset pagination (`page`, `limit`).
- Browse mode uses cursor pagination (`cursor`, `limit`).
- Relevance sort is only valid when search query is present.

### 4) Cart Flow

- One cart per user (unique index).
- Optimistic concurrency using `version` field with retry loop.
- Stock validation happens against product variants before cart updates.

### 5) Distributed Checkout (Multi-Seller)

1. Load and validate cart items.
2. Reserve inventory atomically per SKU.
3. Group items by seller and create seller-specific orders.
4. Create a transaction with seller allocations.
5. Process payment through gateway abstraction.
6. On success: mark transaction/order paid, generate invoice(s), clear cart.
7. On failure: rollback order/payment state and restore inventory.

Pricing rules currently implemented:

- Tax: 18%
- Shipping: free only when subtotal is strictly greater than 1000, else 50

### 6) Invoice + PDF

- Invoice is created as immutable snapshot per order.
- Invoice number is generated from atomic counters (`INV-<year>-<seq>`).
- PDF is rendered from HTML template via WeasyPrint.

## Database Model Notes

Beanie models registered at startup:

- User
- Product
- Category
- Cart
- Order
- Transaction
- Invoice
- EmailOTPVerification
- RevokedToken
- Counter

Key persistence patterns:

- Soft delete and audit fields via shared `AuditDocument` base model
- TTL indexes for OTP and revoked tokens
- Partial TTL for unverified users
- Product text index (`name`, `brand`, `description`)
- Unique constraints (email, username, variant SKU, invoice number, etc.)

## Scripts (Seed)

Run all scripts from the project root.

### Seeding

```powershell
python scripts/seed_super_admin.py --user-name admin --email admin@shop.com --mobile 9999999999 --password StrongPass@123
```

### Full Database Seed For Docker Dev

Export every collection from a source MongoDB database into seed files:

```powershell
python scripts/seed_database.py export --source-uri mongodb://localhost:27017 --source-db ecommerce_db --out-dir scripts/seed/ecommerce_db
```

Import every exported collection into Docker MongoDB:

```powershell
docker exec ecommerce_app python scripts/seed_database.py import --target-uri mongodb://mongodb:27017 --target-db ecommerce_db --in-dir scripts/seed/ecommerce_db --drop
```

Use MongoDB Compass with Docker MongoDB:

```text
mongodb://localhost:27017
```

## Testing

Run all tests:

```powershell
pytest
```

Run by scope:

```powershell
pytest tests/unit
pytest tests/integration
```

Run a single file:

```powershell
pytest tests/integration/test_user_and_auth_routes.py
```

Coverage (if plugin installed):

```powershell
pytest --cov=app --cov-report=term-missing
```

Test setup notes:

- Tests monkeypatch DB initialization during app lifespan.
- A fallback test `SECRET_KEY` is configured in `tests/conftest.py`.

## Operational Constraints

- Soft-deleted records should be filtered in queries (`is_deleted != True`).
- Category delete is blocked when child categories or active products exist.
- Product variant SKUs are globally unique (index on `variants.sku`).
- Cart has max item cap and optimistic locking conflict retries.
- Role checks enforce restricted writes (admin/seller/customer scopes).
- Token revocation list is consulted on protected requests.

## Troubleshooting

### App fails at startup with SECRET_KEY error

Set a non-empty `SECRET_KEY` in `.env`.

### OTP email send fails

Check `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, SMTP host/port/TLS settings.

### Checkout fails with stock conflict

Inventory changed between cart add and checkout. Re-fetch cart and retry.

### PDF generation fails

Confirm WeasyPrint dependencies are installed correctly for your OS.

---

If you want this README tailored further for deployment (Docker, CI/CD, reverse proxy, object storage for media, real payment gateway integration), add your target stack and this can be extended with production-ready runbooks.
