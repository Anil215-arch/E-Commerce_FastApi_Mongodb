from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId

from app.models.order_model import OrderPaymentStatus, OrderStatus
from app.services.dashboard_services import DashboardService


class _CountCursor:
    def __init__(self, value: int):
        self.value = value

    async def count(self) -> int:
        return self.value


class _AggregateCursor:
    def __init__(self, rows):
        self._rows = rows

    async def to_list(self):
        return self._rows


def test_zero_fill_daily_inserts_missing_dates():
    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 3, tzinfo=timezone.utc)
    input_rows = [SimpleNamespace(date="2026-01-02", revenue=50)]

    filled = DashboardService._zero_fill(input_rows, start_date, end_date, "daily")

    assert [row.date for row in filled] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert [row.revenue for row in filled] == [0, 50, 0]


def test_zero_fill_rejects_invalid_period():
    start_date = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 1, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError) as exc:
        DashboardService._zero_fill([], start_date, end_date, "hourly")

    assert "Invalid period" in str(exc.value)


@pytest.mark.asyncio
async def test_get_admin_summary_aggregates_all_counts():
    with patch("app.services.dashboard_services.User.find_all", return_value=_CountCursor(100)):
        with patch("app.services.dashboard_services.User.find", return_value=_CountCursor(20)):
            with patch("app.services.dashboard_services.Order.find_all", return_value=_CountCursor(300)):
                with patch("app.services.dashboard_services.Product.find_all", return_value=_CountCursor(500)):
                    with patch("app.services.dashboard_services.Category.find_all", return_value=_CountCursor(40)):
                        result = await DashboardService.get_admin_summary()

    assert result.total_users == 100
    assert result.total_sellers == 20
    assert result.total_orders == 300
    assert result.total_products == 500
    assert result.total_categories == 40


@pytest.mark.asyncio
async def test_get_seller_summary_uses_seller_scoped_counts():
    seller_id = PydanticObjectId()

    with patch("app.services.dashboard_services.Product.find", return_value=_CountCursor(7)) as mock_product_find:
        with patch("app.services.dashboard_services.Order.find", return_value=_CountCursor(11)) as mock_order_find:
            result = await DashboardService.get_seller_summary(seller_id)

    mock_product_find.assert_called_once_with({"seller_id": seller_id})
    mock_order_find.assert_called_once_with({"seller_id": seller_id})
    assert result.total_products == 7
    assert result.total_orders == 11


@pytest.mark.asyncio
async def test_get_revenue_chart_rejects_date_range_over_five_years():
    start_date = datetime.now(timezone.utc) - timedelta(days=365 * 6)
    end_date = datetime.now(timezone.utc)

    with pytest.raises(ValueError) as exc:
        await DashboardService.get_revenue_chart(start_date=start_date, end_date=end_date)

    assert "5-year limit" in str(exc.value)


@pytest.mark.asyncio
async def test_get_revenue_chart_builds_pipeline_and_returns_series():
    seller_id = PydanticObjectId()
    start_date = datetime(2026, 4, 1, tzinfo=timezone.utc)
    end_date = datetime(2026, 4, 1, tzinfo=timezone.utc)

    aggregate_rows = [{"_id": "2026-04-01", "revenue": 12300}]

    with patch(
        "app.services.dashboard_services.Order.aggregate",
        return_value=_AggregateCursor(aggregate_rows),
    ) as mock_aggregate:
        data = await DashboardService.get_revenue_chart(
            seller_id=seller_id,
            period="daily",
            start_date=start_date,
            end_date=end_date,
        )

    called_pipeline = mock_aggregate.call_args.args[0]
    match_stage = called_pipeline[0]["$match"]
    assert match_stage["seller_id"] == seller_id
    assert match_stage["payment_status"] == OrderPaymentStatus.PAID.value
    assert match_stage["status"] == {"$ne": OrderStatus.CANCELLED.value}

    assert len(data) == 1
    assert data[0].date == "2026-04-01"
    assert data[0].revenue == 123
