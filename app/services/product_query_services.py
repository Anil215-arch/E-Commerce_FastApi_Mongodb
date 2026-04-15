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
    async def list_products(params: ProductQueryParams) -> Tuple[List[ProductResponse], Optional[str], bool]:
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
        # PATH A: TEXT SEARCH (Offset Pagination)
        # ==========================================
        if params.search:
            query["$text"] = {"$search": params.search}
            pipeline: List[Dict[str, Any]] = [{"$match": query}]
            # Sort Logic
            if params.sort_by == SortField.RELEVANCE:
                pipeline.append({"$sort": {"score": {"$meta": "textScore"}, "_id": 1}})
            else:
                sort_field_map = {SortField.PRICE: "price", SortField.RATING: "rating"}
                db_sort_field = sort_field_map.get(params.sort_by, "price")
                sort_dir = -1 if params.sort_order == SortOrder.DESC else 1
                pipeline.append({"$sort": {db_sort_field: sort_dir, "_id": sort_dir}})
            
            # Pagination Logic
            skip_amount = (params.page - 1) * params.limit
            pipeline.append({"$skip": skip_amount})
            pipeline.append({"$limit": params.limit + 1})
            
            products = await Product.aggregate(pipeline, projection_model=Product).to_list()
            
            if len(products) > params.limit:
                has_next_page = True
                products.pop()
                
        # ==========================================
        # PATH B: STANDARD BROWSE (Cursor Pagination)
        # ==========================================
        else:
            sort_field_map = {
                SortField.PRICE: "price",
                SortField.RATING: "rating",
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
            serialized_products.append(ProductMapper.serialize_product(product, category))

        return serialized_products, next_cursor, has_next_page

    @staticmethod
    async def get_product(product_id: PydanticObjectId) -> Optional[ProductResponse]:
        product = await Product.get(product_id)
        if not product or getattr(product, "is_deleted", False):
            return None
        
        category = await Category.get(product.category_id)
        return ProductMapper.serialize_product(product, category)