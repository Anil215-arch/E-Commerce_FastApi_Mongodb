from typing import Dict, Any, Tuple, List, Optional
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status
from beanie import PydanticObjectId, SortDirection
from pymongo.errors import DuplicateKeyError

from app.models.order_model import Order
from app.models.product_model import Product
from app.models.review_rating_model import ReviewAndRating
from app.schemas.review_rating_schema import ReviewCreate, ReviewUpdate
from app.utils.pagination import CursorUtils
from app.validators.review_validator import ReviewDomainValidator
from app.core.exceptions import DomainValidationError
from app.core.message_keys import Msg

class ReviewService:
    
    @staticmethod
    async def _check_verified_purchase(user_id: PydanticObjectId, product_id: PydanticObjectId) -> Optional[PydanticObjectId]:
        order = await Order.find_one({
            "user_id": user_id,
            "status": {"$in": ["DELIVERED", "COMPLETED"]}, 
            "items.product_id": product_id
        })
        return order.id if order else None

    @staticmethod
    async def create_review(user_id: PydanticObjectId, product_id: PydanticObjectId, review_data: ReviewCreate) -> ReviewAndRating:
        product = await Product.find_one({
            "_id": product_id, 
            "is_deleted": {"$ne": True},
            "is_available": True
        })
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Msg.PRODUCT_NOT_FOUND_OR_UNAVAILABLE)

        order_id = await ReviewService._check_verified_purchase(user_id, product_id)
        
        if not order_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail=Msg.REVIEW_OWN_PRODUCTS_ONLY
            )
        clean_review_text = ReviewDomainValidator.validate_review_text(review_data.review)
        clean_images = ReviewDomainValidator.validate_images(review_data.images)
        new_review = ReviewAndRating(
            product_id=product_id,
            user_id=user_id,
            rating=review_data.rating,
            review=clean_review_text,
            images=clean_images,
            is_verified=bool(order_id),
            order_id=order_id,
            created_by=user_id,
            updated_by=user_id
        )
        
        try:
            # 1. Insert the review (Standalone write)
            await new_review.insert()
        except DuplicateKeyError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=Msg.REVIEW_ALREADY_EXISTS)

        # 2. Update the product aggregates natively (Standalone write)
        await Product.get_pymongo_collection().update_one(
            {"_id": product_id},
            [
                {
                    "$set": {
                        "num_reviews": {"$add": [{"$ifNull": ["$num_reviews", 0]}, 1]},
                        "rating_sum": {"$add": [{"$ifNull": ["$rating_sum", 0]}, review_data.rating]},
                        f"rating_breakdown.{review_data.rating}": {
                            "$add": [{"$ifNull": [f"$rating_breakdown.{review_data.rating}", 0]}, 1]
                        }
                    }
                },
                {
                    "$set": {
                        "average_rating": {
                            "$round": [{"$divide": ["$rating_sum", "$num_reviews"]}, 2]
                        }
                    }
                }
            ]
        )

        return new_review

    @staticmethod
    async def update_review(
        review_id: PydanticObjectId, 
        user_id: PydanticObjectId, 
        review_data: ReviewUpdate
    ) -> ReviewAndRating:
        
        if review_data.review is not None:
            review_data.review = ReviewDomainValidator.validate_review_text(review_data.review)
        if review_data.images is not None:
            review_data.images = ReviewDomainValidator.validate_images(review_data.images)
            
        review_doc = await ReviewAndRating.get(review_id)
        if not review_doc or review_doc.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Msg.REVIEW_NOT_FOUND)
            
        if review_doc.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Msg.EDIT_OWN_REVIEWS_ONLY)

        update_data = review_data.model_dump(exclude_unset=True)
        if not update_data:
            return review_doc

        old_rating = review_doc.rating
        new_rating = update_data.get("rating")

        for key, value in update_data.items():
            setattr(review_doc, key, value)
            
        review_doc.updated_by = user_id

        # 1. Save the updated review (Standalone write)
        await review_doc.save()

        if new_rating is not None and old_rating != new_rating:
            product = await Product.get(review_doc.product_id)
            if not product:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Msg.TARGET_PRODUCT_NO_LONGER_EXISTS)
            
            # 2. Shift the aggregates (Standalone write)
            await Product.get_pymongo_collection().update_one(
                {"_id": review_doc.product_id},
                [
                    {
                        "$set": {
                            "rating_sum": {
                                "$max": [0, {"$add": [{"$subtract": [{"$ifNull": ["$rating_sum", 0]}, old_rating]}, new_rating]}]
                            },
                            f"rating_breakdown.{old_rating}": {
                                "$max": [0, {"$subtract": [{"$ifNull": [f"$rating_breakdown.{old_rating}", 0]}, 1]}]
                            },
                            f"rating_breakdown.{new_rating}": {
                                "$add": [{"$ifNull": [f"$rating_breakdown.{new_rating}", 0]}, 1]
                            }
                        }
                    },
                    {
                        "$set": {
                            "average_rating": {
                                "$cond": [
                                    {"$gt": ["$num_reviews", 0]},
                                    {"$round": [{"$divide": ["$rating_sum", "$num_reviews"]}, 2]},
                                    0.0
                                ]
                            }
                        }
                    }
                ]
            )
            
        return review_doc

    @staticmethod
    async def delete_review(review_id: PydanticObjectId, user_id: PydanticObjectId) -> None:
        review_doc = await ReviewAndRating.get(review_id)
        if not review_doc or review_doc.is_deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Msg.REVIEW_NOT_FOUND)
            
        if review_doc.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=Msg.DELETE_OWN_REVIEWS_ONLY)

        rating_to_remove = review_doc.rating
        product_id = review_doc.product_id

        review_doc.is_deleted = True
        review_doc.deleted_at = datetime.now(timezone.utc)
        review_doc.deleted_by = user_id
        
        # 1. Soft delete the review (Standalone write)
        await review_doc.save()

        product = await Product.get(product_id)
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=Msg.TARGET_PRODUCT_NO_LONGER_EXISTS)
        
        # 2. Decrement the aggregates (Standalone write)
        await Product.get_pymongo_collection().update_one(
            {"_id": product_id},
            [
                {
                    "$set": {
                        "num_reviews": {"$max": [0, {"$subtract": [{"$ifNull": ["$num_reviews", 0]}, 1]}]},
                        "rating_sum": {"$max": [0, {"$subtract": [{"$ifNull": ["$rating_sum", 0]}, rating_to_remove]}]},
                        f"rating_breakdown.{rating_to_remove}": {
                            "$max": [0, {"$subtract": [{"$ifNull": [f"$rating_breakdown.{rating_to_remove}", 0]}, 1]}]
                        }
                    }
                },
                {
                    "$set": {
                        "average_rating": {
                            "$cond": [
                                {"$gt": ["$num_reviews", 0]},
                                {"$round": [{"$divide": ["$rating_sum", "$num_reviews"]}, 2]},
                                0.0
                            ]
                        }
                    }
                }
            ]
        )
            
    @staticmethod
    async def list_product_reviews(
        product_id: PydanticObjectId, 
        limit: int, 
        cursor: Optional[str] = None
    ) -> Tuple[List[ReviewAndRating], Optional[str], bool]:
        
        query: Dict[str, Any] = {
            "product_id": product_id,
            "is_deleted": {"$ne": True}
        }
        
        has_next_page = False
        next_cursor = None

        if cursor:
            cursor_data = CursorUtils.decode_cursor(cursor)
            if cursor_data:
                try:
                    last_id = ObjectId(cursor_data.get("id"))
                    last_val_str = cursor_data.get("v")
                    last_val = datetime.fromisoformat(last_val_str) if last_val_str else None
                    
                    if last_val:
                        cursor_query = {
                            "$or": [
                                {"created_at": {"$lt": last_val}},
                                {"created_at": last_val, "_id": {"$lt": last_id}}
                            ]
                        }
                        query = {"$and": [query, cursor_query]}
                except (InvalidId, TypeError, ValueError):
                    pass

        reviews = await ReviewAndRating.find(query).sort(
            [("created_at", SortDirection.DESCENDING), ("_id", SortDirection.DESCENDING)]
        ).limit(limit + 1).to_list()

        if len(reviews) > limit:
            has_next_page = True
            reviews.pop()
            last_item = reviews[-1]
            last_item_val = last_item.created_at.isoformat() 
            next_cursor = CursorUtils.encode_cursor({"v": last_item_val, "id": str(last_item.id)})

        return reviews, next_cursor, has_next_page
