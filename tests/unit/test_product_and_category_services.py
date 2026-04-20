from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from app.schemas.category_schema import CategoryUpdate
from app.schemas.product_schema import ProductUpdate
from app.schemas.product_variant_schema import ProductVariantUpdate
from app.services.category_services import CategoryService
from app.services.product_services import ProductService


@pytest.mark.asyncio
async def test_product_update_variant_rejects_path_body_sku_mismatch():
    product = SimpleNamespace(category_id=PydanticObjectId(), variants=[SimpleNamespace(sku="SKU-1")])

    with patch("app.services.product_services.ProductService._get_product_or_raise", new=AsyncMock(return_value=product)):
        with patch("app.services.product_services.ProductService._get_category_or_raise", new=AsyncMock(return_value=object())):
            with pytest.raises(HTTPException) as exc:
                await ProductService.update_variant(
                    PydanticObjectId(),
                    "SKU-PATH",
                    ProductVariantUpdate(sku="SKU-BODY", price=100, stock=3),
                    PydanticObjectId(),
                )

    assert exc.value.status_code == 400
    assert "path and body must match" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_delete_variant_rejects_when_product_would_have_no_variants_left():
    product = SimpleNamespace(
        category_id=PydanticObjectId(),
        variants=[SimpleNamespace(sku="ONLY")],
        save=AsyncMock(),
    )

    with patch("app.services.product_services.ProductService._get_product_or_raise", new=AsyncMock(return_value=product)):
        with patch("app.services.product_services.ProductService._get_category_or_raise", new=AsyncMock(return_value=object())):
            with pytest.raises(HTTPException) as exc:
                await ProductService.delete_variant(PydanticObjectId(), "ONLY", PydanticObjectId())

    assert exc.value.status_code == 400
    assert "at least one variant" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_delete_variant_triggers_wishlist_cleanup_for_removed_sku():
    product_id = PydanticObjectId()
    product = SimpleNamespace(
        category_id=PydanticObjectId(),
        variants=[SimpleNamespace(sku="SKU-1"), SimpleNamespace(sku="SKU-2")],
        updated_by=None,
        save=AsyncMock(),
    )
    cleanup_mock = AsyncMock()

    with patch("app.services.product_services.ProductService._get_product_or_raise", new=AsyncMock(return_value=product)):
        with patch("app.services.product_services.ProductService._get_category_or_raise", new=AsyncMock(return_value=object())):
            with patch("app.services.product_services.ProductMapper.serialize_product", return_value={"ok": True}):
                with patch("app.services.product_services.WishlistService.remove_ghost_product_references", new=cleanup_mock):
                    await ProductService.delete_variant(product_id, "SKU-1", PydanticObjectId())

    assert len(product.variants) == 1
    assert product.variants[0].sku == "SKU-2"
    product.save.assert_awaited_once()
    cleanup_mock.assert_awaited_once_with(product_id, "SKU-1")


@pytest.mark.asyncio
async def test_upload_product_images_rejects_file_above_size_limit():
    product = SimpleNamespace(images=[], category_id=PydanticObjectId(), save=AsyncMock())
    image = SimpleNamespace(
        filename="big.jpg",
        content_type="image/jpeg",
        file=BytesIO(b"x"),
    )

    def _fake_seek(offset, whence=0):
        if whence == 2:
            return 0
        return 0

    image.file.seek = _fake_seek
    image.file.tell = lambda: (5 * 1024 * 1024) + 1

    with patch("app.services.product_services.Product.get", new=AsyncMock(return_value=product)):
        with pytest.raises(HTTPException) as exc:
            await ProductService.upload_product_images(PydanticObjectId(), [image], PydanticObjectId())

    assert exc.value.status_code == 400
    assert "file too large" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_update_product_rejects_variants_payload_in_general_update():
    product = SimpleNamespace(category_id=PydanticObjectId())

    with patch("app.services.product_services.Product.get", new=AsyncMock(return_value=product)):
        with patch("app.services.product_services.ProductService._get_category_or_raise", new=AsyncMock(return_value=object())):
            with pytest.raises(HTTPException) as exc:
                await ProductService.update_product(
                    PydanticObjectId(),
                    ProductUpdate(
                        variants=[
                            ProductVariantUpdate(sku="SKU-1", price=100, stock=1),
                        ]
                    ),
                    PydanticObjectId(),
                )

    assert exc.value.status_code == 400
    assert "dedicated variant endpoints" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_update_product_unavailable_triggers_wishlist_cleanup():
    product_id = PydanticObjectId()
    current_user_id = PydanticObjectId()
    product = SimpleNamespace(
        category_id=PydanticObjectId(),
        set=AsyncMock(),
    )
    updated_product = SimpleNamespace(id=product_id)
    cleanup_mock = AsyncMock()

    with patch("app.services.product_services.Product.get", new=AsyncMock(side_effect=[product, updated_product])):
        with patch("app.services.product_services.ProductService._get_category_or_raise", new=AsyncMock(return_value=object())):
            with patch("app.services.product_services.ProductMapper.serialize_product", return_value={"ok": True}):
                with patch("app.services.product_services.WishlistService.remove_ghost_product_references", new=cleanup_mock):
                    await ProductService.update_product(
                        product_id,
                        ProductUpdate(is_available=False),
                        current_user_id,
                    )

    product.set.assert_awaited_once()
    cleanup_mock.assert_awaited_once_with(product_id)


@pytest.mark.asyncio
async def test_update_product_without_unavailable_flag_does_not_trigger_cleanup():
    product_id = PydanticObjectId()
    current_user_id = PydanticObjectId()
    product = SimpleNamespace(
        category_id=PydanticObjectId(),
        set=AsyncMock(),
    )
    updated_product = SimpleNamespace(id=product_id)
    cleanup_mock = AsyncMock()

    with patch("app.services.product_services.Product.get", new=AsyncMock(side_effect=[product, updated_product])):
        with patch("app.services.product_services.ProductService._get_category_or_raise", new=AsyncMock(return_value=object())):
            with patch("app.services.product_services.ProductMapper.serialize_product", return_value={"ok": True}):
                with patch("app.services.product_services.WishlistService.remove_ghost_product_references", new=cleanup_mock):
                    await ProductService.update_product(
                        product_id,
                        ProductUpdate(name="Updated Product Name"),
                        current_user_id,
                    )

    cleanup_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_product_triggers_wishlist_cleanup_after_soft_delete():
    product_id = PydanticObjectId()
    current_user_id = PydanticObjectId()
    product = SimpleNamespace(
        is_deleted=False,
        images=[],
        soft_delete=AsyncMock(),
    )
    cleanup_mock = AsyncMock()

    with patch("app.services.product_services.Product.get", new=AsyncMock(return_value=product)):
        with patch("app.services.product_services.WishlistService.remove_ghost_product_references", new=cleanup_mock):
            result = await ProductService.delete_product(product_id, current_user_id)

    assert result is True
    product.soft_delete.assert_awaited_once_with(current_user_id)
    cleanup_mock.assert_awaited_once_with(product_id)


@pytest.mark.asyncio
async def test_category_update_rejects_self_parent_assignment():
    category_id = PydanticObjectId()
    category = SimpleNamespace(id=category_id, parent_id=None, is_deleted=False, save=AsyncMock())

    with patch("app.services.category_services.Category.get", new=AsyncMock(return_value=category)):
        updated, error = await CategoryService.update_category(
            category_id,
            CategoryUpdate(parent_id=category_id),
            PydanticObjectId(),
        )

    assert updated is None
    assert error == "A category cannot be its own parent."


@pytest.mark.asyncio
async def test_category_update_rejects_cycle_in_hierarchy():
    category_id = PydanticObjectId()
    new_parent_id = PydanticObjectId()
    category = SimpleNamespace(id=category_id, parent_id=None, is_deleted=False, save=AsyncMock())

    async def _category_get_side_effect(requested_id):
        if requested_id == category_id:
            return category
        if requested_id == new_parent_id:
            return SimpleNamespace(id=new_parent_id, parent_id=None, is_deleted=False)
        return None

    with patch("app.services.category_services.Category.get", new=AsyncMock(side_effect=_category_get_side_effect)):
        with patch("app.services.category_services.CategoryService._creates_cycle", new=AsyncMock(return_value=True)):
            updated, error = await CategoryService.update_category(
                category_id,
                CategoryUpdate(parent_id=new_parent_id),
                PydanticObjectId(),
            )

    assert updated is None
    assert "circular hierarchy" in error.lower()


@pytest.mark.asyncio
async def test_delete_category_rejects_when_products_are_assigned():
    category = SimpleNamespace(id=PydanticObjectId(), is_deleted=False, delete=AsyncMock())

    with patch("app.services.category_services.Category.get", new=AsyncMock(return_value=category)):
        with patch("app.services.category_services.Category.find_one", new=AsyncMock(return_value=None)):
            with patch("app.services.category_services.Product.find_one", new=AsyncMock(return_value=object())):
                error = await CategoryService.delete_category(category.id, PydanticObjectId())

    assert "products are assigned" in error.lower()


@pytest.mark.asyncio
async def test_get_category_tree_builds_nested_children():
    root_id = PydanticObjectId()
    child_id = PydanticObjectId()
    categories = [
        SimpleNamespace(id=root_id, name="Root", parent_id=None),
        SimpleNamespace(id=child_id, name="Child", parent_id=root_id),
    ]

    class _Expr:
        def __eq__(self, _other):
            return True

    find_cursor = SimpleNamespace(to_list=AsyncMock(return_value=categories))
    with patch("app.services.category_services.Category.is_deleted", new=_Expr(), create=True):
        with patch("app.services.category_services.Category.find", return_value=find_cursor):
            tree = await CategoryService.get_category_tree()

    assert len(tree) == 1
    assert tree[0]["name"] == "Root"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["name"] == "Child"
