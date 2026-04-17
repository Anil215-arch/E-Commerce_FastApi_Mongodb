from unittest.mock import AsyncMock

from app.services.product_query_services import ProductQueryService


def test_list_products_returns_single_paginated_payload(client, monkeypatch):
    monkeypatch.setattr(
        ProductQueryService,
        "list_products",
        AsyncMock(return_value=([], None, False)),
    )

    response = client.get("/api/v1/products/?limit=10&sort_by=created_at&sort_order=desc")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Products fetched successfully",
        "status": "success",
        "data": {
            "items": [],
            "meta": {
                "has_next_page": False,
                "next_cursor": None,
            },
        },
    }
