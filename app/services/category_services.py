import re
from typing import Any, List, Optional, Tuple
from beanie import PydanticObjectId
from app.core.message_keys import Msg
from app.models.category_model import Category, CategoryTranslation
from app.models.product_model import Product
from app.schemas.category_schema import CategoryCreate, CategoryUpdate
from app.validators.category_validator import CategoryDomainValidator

class CategoryService:
    @staticmethod
    def _build_translations(
        translations: dict[str, Any] | None,
    ) -> dict[str, CategoryTranslation]:
        return {
            lang: CategoryTranslation(**translation.model_dump())
            for lang, translation in (translations or {}).items()
        }

    @staticmethod
    def _localized_name(category: Category, language: Optional[str]) -> str:
        if language and language in category.translations:
            translated_name = category.translations[language].name
            if translated_name:
                return translated_name
        return category.name

    @staticmethod
    def _serialize_category(category: Category, language: Optional[str]) -> dict[str, Any]:
        return {
            "_id": category.id,
            "name": CategoryService._localized_name(category, language),
            "parent_id": category.parent_id,
        }

    @staticmethod
    async def get_all_categories(
        language: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Category] | List[dict[str, Any]]:
        query: dict[str, Any] = {"is_deleted": False}

        if search:
            clean_search = search.strip()
            if clean_search:
                safe_regex = {"$regex": re.escape(clean_search), "$options": "i"}

                search_conditions = [{"name": safe_regex}]

                if language:
                    search_conditions.append({f"translations.{language}.name": safe_regex})

                query = {
                    "$and": [
                        query,
                        {"$or": search_conditions},
                    ]
                }

        categories = await Category.find(query).to_list()
        if language is None:
            return categories
        return [CategoryService._serialize_category(category, language) for category in categories]
    
    @staticmethod
    async def get_category_by_id(category_id: PydanticObjectId, language: Optional[str] = None) -> Category | dict[str, Any] | None:
        category = await Category.get(category_id)
        if not category or category.is_deleted:
            return None
        if language is None:
            return category
        return CategoryService._serialize_category(category, language)

    @staticmethod
    async def _validate_parent(parent_id: PydanticObjectId | None) -> Tuple[PydanticObjectId | None, str | None]:
        if parent_id is None:
            return None, None

        parent = await Category.get(parent_id)
        if not parent or parent.is_deleted:
            return None, Msg.PARENT_CATEGORY_NOT_FOUND_OR_DELETED

        return parent.id, None

    @staticmethod
    async def _creates_cycle(category_id: PydanticObjectId, new_parent_id: PydanticObjectId) -> bool:
        current_parent = await Category.get(new_parent_id)

        while current_parent is not None and not current_parent.is_deleted:
            if current_parent.id == category_id:
                return True

            if current_parent.parent_id is None:
                return False

            current_parent = await Category.get(current_parent.parent_id)

        return False
    
    @staticmethod
    async def _get_descendant_category_ids(category_id: PydanticObjectId) -> list[PydanticObjectId]:
        descendant_ids: list[PydanticObjectId] = []
        pending_ids: list[PydanticObjectId] = [category_id]

        while pending_ids:
            children = await Category.find({
                "parent_id": {"$in": pending_ids},
                "is_deleted": False,
            }).to_list()

            child_ids = [
                child.id
                for child in children
                if child.id is not None
            ]

            descendant_ids.extend(child_ids)
            pending_ids = child_ids

        return descendant_ids
    
    @staticmethod
    async def create_category(data: CategoryCreate, current_user_id: PydanticObjectId) -> Tuple[Category | None, str | None]:
        parent_id, error = await CategoryService._validate_parent(data.parent_id)
        if error:
            return None, error

        clean_name = CategoryDomainValidator.validate_name(data.name)
        if parent_id is not None:
            depth = 1
            current_parent = await Category.get(parent_id)

            while current_parent is not None and not current_parent.is_deleted:
                if current_parent.parent_id is None:
                    break
                depth += 1
                current_parent = await Category.get(current_parent.parent_id)

            CategoryDomainValidator.validate_depth_limit(depth + 1)
        new_category = Category(
            name=clean_name,
            parent_id=parent_id,
            translations=CategoryService._build_translations(data.translations),
            created_by=current_user_id,
            updated_by=current_user_id
        )
        created = await new_category.insert()
        return created, None

    @staticmethod
    async def get_category_tree(language: Optional[str] = None) -> List[dict]:
        categories = await Category.find(Category.is_deleted == False).to_list()

        category_map = {}
        tree = []

        for cat in categories:
            cat_id_str = str(cat.id)
            category_map[cat_id_str] = {
                "_id": cat.id,
                "name": CategoryService._localized_name(cat, language),
                "parent_id": cat.parent_id,
                "children": []
            }

        for cat in categories:
            cat_id_str = str(cat.id)
            if cat.parent_id:
                parent_id_str = str(cat.parent_id)
                if parent_id_str in category_map:
                    category_map[parent_id_str]["children"].append(category_map[cat_id_str])
            else:
                tree.append(category_map[cat_id_str])

        return tree

    @staticmethod
    async def update_category(category_id: PydanticObjectId, data: CategoryUpdate, current_user_id: PydanticObjectId) -> Tuple[Category | None, str | None]:
        category = await Category.get(category_id)
        if not category or category.is_deleted:
            return None, Msg.CATEGORY_NOT_FOUND
        
        if category.id is None:
            return None, Msg.CATEGORY_ID_MISSING

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return category, None

        if "name" in update_data:
            category.name = CategoryDomainValidator.validate_name(update_data["name"])

        if "translations" in update_data and update_data["translations"] is not None:
            category.translations = CategoryService._build_translations(data.translations)

        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id == category.id:
                return None, Msg.CATEGORY_CANNOT_BE_OWN_PARENT

            if new_parent_id is not None:
                new_parent = await Category.get(new_parent_id)
                if not new_parent or new_parent.is_deleted:
                    return None, Msg.NEW_PARENT_CATEGORY_NOT_FOUND
                if await CategoryService._creates_cycle(category.id, new_parent_id):
                    return None, Msg.CATEGORY_CIRCULAR_HIERARCHY

                depth = 1
                current_parent = new_parent

                while current_parent is not None and not current_parent.is_deleted:
                    if current_parent.parent_id is None:
                        break
                    depth += 1
                    current_parent = await Category.get(current_parent.parent_id)

                CategoryDomainValidator.validate_depth_limit(depth + 1)

            category.parent_id = new_parent_id
            
        category.updated_by = current_user_id
        await category.save()
        return category, None

    @staticmethod
    async def delete_category(category_id: PydanticObjectId, current_user_id: PydanticObjectId) -> str | None:
        category = await Category.get(category_id)
        if not category or category.is_deleted or category.id is None:
            return Msg.CATEGORY_NOT_FOUND

        descendant_ids = await CategoryService._get_descendant_category_ids(category.id)
        category_ids_to_delete: list[PydanticObjectId] = [category.id, *descendant_ids]

        products = await Product.find({
            "category_id": {"$in": category_ids_to_delete},
            "is_deleted": False,
        }).to_list()

        for product in products:
            await product.soft_delete(current_user_id)

        categories_to_delete = await Category.find({
            "_id": {"$in": category_ids_to_delete},
            "is_deleted": False,
        }).to_list()

        categories_by_id = {
            category_to_delete.id: category_to_delete
            for category_to_delete in categories_to_delete
            if category_to_delete.id is not None
        }

        for category_id_to_delete in reversed(category_ids_to_delete):
            category_to_delete = categories_by_id.get(category_id_to_delete)
            if category_to_delete:
                await category_to_delete.soft_delete(current_user_id)

        return None
