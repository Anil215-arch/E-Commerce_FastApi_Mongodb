import re
from typing import Dict, Any, Tuple, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from beanie import PydanticObjectId, SortDirection
from app.models.product_model import Product
from app.models.category_model import Category
from app.schemas.product_query_schema import ProductQueryParams, SortOrder, SortField
from app.schemas.product_schema import ProductResponse
from app.utils.pagination import CursorUtils
from app.utils.product_mapper import ProductMapper

class ProductQueryService:

    @staticmethod
    async def list_products(params: ProductQueryParams, language: Optional[str] = None) -> Tuple[List[ProductResponse], Optional[str], bool]:
        query: Dict[str, Any] = {"is_deleted": {"$ne": True}}
        
        if params.category_id: query["category_id"] = params.category_id
        if params.brand: query["brand"] = params.brand
        if params.min_price is not None or params.max_price is not None:
            query["price"] = {}
            if params.min_price is not None: query["price"]["$gte"] = params.min_price
            if params.max_price is not None: query["price"]["$lte"] = params.max_price

        has_next_page = False
        next_cursor = None
        products = []

        # ==========================================
        # PATH A: REGEX SEARCH (Offset Pagination)
        # ==========================================
        if params.search:
            safe_search = re.escape(params.search)
            search_regex = {"$regex": safe_search, "$options": "i"}
            variant_attribute_exprs: List[Dict[str, Any]] = [
                {
                    "$anyElementTrue": {
                        "$map": {
                            "input": {"$ifNull": ["$variants", []]},
                            "as": "variant",
                            "in": {
                                "$anyElementTrue": {
                                    "$map": {
                                        "input": {"$objectToArray": {"$ifNull": ["$$variant.attributes", {}]}},
                                        "as": "attr",
                                        "in": {
                                            "$regexMatch": {
                                                "input": {"$toString": "$$attr.v"},
                                                "regex": safe_search,
                                                "options": "i",
                                            }
                                        },
                                    }
                                }
                            },
                        }
                    }
                }
            ]

            search_conditions = [
                {"name": search_regex},
                {"description": search_regex},
                {"brand": search_regex},
                {"variants.sku": search_regex},
            ]

            if language:
                search_conditions.extend([
                    {f"translations.{language}.name": search_regex},
                    {f"translations.{language}.description": search_regex},
                ])
                variant_attribute_exprs.append(
                    {
                        "$anyElementTrue": {
                            "$map": {
                                "input": {"$ifNull": ["$variants", []]},
                                "as": "variant",
                                "in": {
                                    "$anyElementTrue": {
                                        "$map": {
                                            "input": {
                                                "$objectToArray": {
                                                    "$ifNull": [
                                                        f"$$variant.translations.{language}.attributes",
                                                        {},
                                                    ]
                                                }
                                            },
                                            "as": "attr",
                                            "in": {
                                                "$regexMatch": {
                                                    "input": {"$toString": "$$attr.v"},
                                                    "regex": safe_search,
                                                    "options": "i",
                                                }
                                            },
                                        }
                                    }
                                },
                            }
                        }
                    }
                )

            search_conditions.append({"$expr": {"$or": variant_attribute_exprs}})

            query = {
                "$and": [
                    query,
                    {"$or": search_conditions},
                ]
            }
            if params.sort_by == SortField.RELEVANCE:
                sort_params = [("_id", SortDirection.DESCENDING)]
            else:
                sort_field_map = {
                    SortField.PRICE: "price",
                    SortField.RATING: "average_rating",
                }
                db_sort_field = sort_field_map.get(params.sort_by, "price")
                sort_dir = (
                    SortDirection.DESCENDING
                    if params.sort_order == SortOrder.DESC
                    else SortDirection.ASCENDING
                )
                sort_params = [(db_sort_field, sort_dir), ("_id", sort_dir)]

            skip_amount = (params.page - 1) * params.limit

            collection = Product.get_pymongo_collection()
            cursor = collection.find(query)

            for field, direction in sort_params:
                cursor = cursor.sort(field, direction)

            raw_products = await cursor.skip(skip_amount).limit(params.limit + 1).to_list(
                length=params.limit + 1
            )

            products = [Product.model_validate(product) for product in raw_products]
            
            if len(products) > params.limit:
                has_next_page = True
                products.pop()
                
        # ==========================================
        # PATH B: STANDARD BROWSE (Cursor Pagination)
        # ==========================================
        else:
            sort_field_map = {
                SortField.PRICE: "price",
                SortField.RATING: "average_rating",
                SortField.CREATED_AT: "_id" 
            }
            db_sort_field = sort_field_map[params.sort_by]
            is_desc = params.sort_order == SortOrder.DESC
            cmp_op = "$lt" if is_desc else "$gt"
            sort_dir = SortDirection.DESCENDING if is_desc else SortDirection.ASCENDING
            
            cursor_data = CursorUtils.decode_cursor(params.cursor)
            if cursor_data:
                try:
                    last_id = ObjectId(cursor_data.get("id"))
                    raw_val = cursor_data.get("v")
                    last_val = ObjectId(raw_val) if db_sort_field == "_id" else raw_val
                    
                    cursor_query = {
                        "$or": [
                            {db_sort_field: {cmp_op: last_val}},
                            {db_sort_field: last_val, "_id": {cmp_op: last_id}}
                        ]
                    }
                    query = {"$and": [query, cursor_query]} if query else cursor_query
                except (InvalidId, TypeError):
                    pass

            products = await Product.find(query).sort(
                [(db_sort_field, sort_dir), ("_id", sort_dir)]
            ).limit(params.limit + 1).to_list()

            if len(products) > params.limit:
                has_next_page = True
                products.pop()
                last_item = products[-1]
                last_item_val = getattr(last_item, db_sort_field) if db_sort_field != "_id" else str(last_item.id)
                next_cursor = CursorUtils.encode_cursor({"v": last_item_val, "id": str(last_item.id)})

        # ==========================================
        # HYDRATION & SERIALIZATION
        # ==========================================
        if not products:
            return [], None, False

        category_ids = list(set([product.category_id for product in products]))
        categories = await Category.find({"_id": {"$in": category_ids}}).to_list()
        category_map = {str(cat.id): cat for cat in categories}

        serialized_products = []
        for product in products:
            category = category_map.get(str(product.category_id))
            serialized_products.append(ProductMapper.serialize_product(product, category, language=language))

        return serialized_products, next_cursor, has_next_page

    @staticmethod
    async def get_product(product_id: PydanticObjectId, language: Optional[str] = None) -> Optional[ProductResponse]:
        product = await Product.get(product_id)
        if not product or getattr(product, "is_deleted", False):
            return None
        
        category = await Category.get(product.category_id)
        return ProductMapper.serialize_product(product, category, language=language)
