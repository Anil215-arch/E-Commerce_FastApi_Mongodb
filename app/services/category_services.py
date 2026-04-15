from typing import List, Tuple
from beanie import PydanticObjectId
from app.models.category_model import Category
from app.models.product_model import Product
from app.schemas.category_schema import CategoryCreate, CategoryUpdate

class CategoryService:
    @staticmethod
    async def get_all_categories() -> List[Category]:
        return await Category.find(Category.is_deleted == False).to_list()
    
    @staticmethod
    async def get_category_by_id(category_id: PydanticObjectId) -> Category | None:
        return await Category.get(category_id)

    @staticmethod
    async def _validate_parent(parent_id: PydanticObjectId | None) -> Tuple[PydanticObjectId | None, str | None]:
        if parent_id is None:
            return None, None

        parent = await Category.get(parent_id)
        if not parent or parent.is_deleted:
            return None, "Parent category not found or has been deleted."

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
    async def create_category(data: CategoryCreate, current_user_id: PydanticObjectId) -> Tuple[Category | None, str | None]:
        parent_id, error = await CategoryService._validate_parent(data.parent_id)
        if error:
            return None, error

        new_category = Category(
            name=data.name,
            parent_id=parent_id,
            created_by=current_user_id,
            updated_by=current_user_id
        )
        created = await new_category.insert()
        return created, None

    @staticmethod
    async def get_category_tree() -> List[dict]:
        categories = await Category.find(Category.is_deleted == False).to_list()

        category_map = {}
        tree = []

        for cat in categories:
            cat_id_str = str(cat.id)
            category_map[cat_id_str] = {
                "_id": cat.id,
                "name": cat.name,
                "parent_id": cat.parent_id,
                "children": []
            }

        for cat in categories:
            cat_id_str = str(cat.id)
            if cat.parent_id:
                parent_id_str = str(cat.parent_id)
                # If the parent exists in our map, inject this category into its children list
                if parent_id_str in category_map:
                    category_map[parent_id_str]["children"].append(category_map[cat_id_str])
            else:
                # If it has no parent, it is a root category
                tree.append(category_map[cat_id_str])

        return tree

    @staticmethod
    async def update_category(category_id: PydanticObjectId, data: CategoryUpdate, current_user_id: PydanticObjectId) -> Tuple[Category | None, str | None]:
        category = await Category.get(category_id)
        if not category or category.is_deleted:
            return None, "Category not found."
        
        if category.id is None:
            return None, "Category ID is missing."
        
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            return category, None

        if "name" in update_data:
            category.name = update_data["name"]

        if "parent_id" in update_data:
            new_parent_id = update_data["parent_id"]
            if new_parent_id == category.id:
                return None, "A category cannot be its own parent."

            if new_parent_id is not None:
                new_parent = await Category.get(new_parent_id)
                if not new_parent or new_parent.is_deleted:
                    return None, "New parent category not found."
                if await CategoryService._creates_cycle(category.id, new_parent_id):
                    return None, "Invalid parent category: circular hierarchy detected."
            
            category.parent_id = new_parent_id
            
        category.updated_by = current_user_id
        await category.save()
        return category, None

    @staticmethod
    async def delete_category(category_id: PydanticObjectId, current_user_id: PydanticObjectId) -> str | None:
        category = await Category.get(category_id)
        if not category or category.is_deleted:
            return "Category not found."

        child_exists = await Category.find_one({"parent_id": category.id, "is_deleted": False})
        if child_exists:
            return "Cannot delete category because it has child categories. Reassign or delete them first."

        product_exists = await Product.find_one({"category_id": category.id, "is_deleted": False})
        if product_exists:
            return "Cannot delete category because products are assigned to it. Reassign or delete those products first."

        await category.soft_delete(current_user_id)
        return None
