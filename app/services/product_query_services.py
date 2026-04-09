from typing import Dict, Any, Tuple, List, Optional
from bson import ObjectId
from bson.errors import InvalidId
from beanie import PydanticObjectId
from app.models.product_model import Product
from app.models.category_model import Category
from app.schemas.product_query_schema import ProductQueryParams, SortOrder, SortField
from app.schemas.product_schema import ProductResponse
from app.utils.pagination import CursorUtils
from app.utils.product_mapper import ProductMapper
from app.services.product_services import ProductService  

class ProductQueryService:

    @staticmethod
    async def list_products(params: ProductQueryParams) -> Tuple[List[ProductResponse], Optional[str]]:
        sort_field_map = {
            SortField.PRICE: "price",
            SortField.RATING: "rating",
            SortField.CREATED_AT: "_id" 
        }
        db_sort_field = sort_field_map[params.sort_by]
        
        is_desc = params.sort_order == SortOrder.DESC
        cmp_op = "$lt" if is_desc else "$gt"
        sort_dir = -1 if is_desc else 1
        
        query: Dict[str, Any] = {}
        
        if params.category_id: query["category_id"] = params.category_id
        if params.brand: query["brand"] = params.brand
        if params.min_price is not None or params.max_price is not None:
            query["price"] = {}
            if params.min_price is not None: query["price"]["$gte"] = params.min_price
            if params.max_price is not None: query["price"]["$lte"] = params.max_price

        cursor_data = CursorUtils.decode_cursor(params.cursor)
        if cursor_data:
            try:
                # FIX 3: Catch malicious or broken ObjectIds
                last_id = ObjectId(cursor_data.get("id"))
                
                # FIX 4: Explicit BSON casting for the sort value
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
                # If cursor is unparseable, silently ignore it and return Page 1
                pass

        products = await Product.find(query).sort(
            [(db_sort_field, sort_dir), ("_id", sort_dir)]
        ).limit(params.limit + 1).to_list()

        next_cursor = None
        if len(products) > params.limit:
            products.pop() 
            last_item = products[-1]
            last_item_val = getattr(last_item, db_sort_field) if db_sort_field != "_id" else str(last_item.id)
            next_cursor = CursorUtils.encode_cursor({"v": last_item_val, "id": str(last_item.id)})

        if not products:
            return [], next_cursor

        category_ids = list(set([product.category_id for product in products]))
        categories = await Category.find({"_id": {"$in": category_ids}}).to_list()
        category_map = {str(cat.id): cat for cat in categories}

        serialized_products = []
        for product in products:
            # FIX 2: Safe dictionary .get() prevents KeyError
            category = category_map.get(str(product.category_id))
            serialized_products.append(ProductMapper.serialize_product(product, category))

        return serialized_products, next_cursor
    
    
    @staticmethod
    async def get_product(product_id: PydanticObjectId) -> Optional[ProductResponse]:
        # 1. Fetch raw product
        product = await Product.get(product_id)
        if not product:
            return None

        # 2. Fetch category safely
        category = await Category.get(product.category_id)
        
        # 3. Map to schema
        return ProductMapper.serialize_product(product, category)