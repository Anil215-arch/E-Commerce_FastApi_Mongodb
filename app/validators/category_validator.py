from app.core.exceptions import DomainValidationError

class CategoryDomainValidator:
    MAX_CATEGORY_DEPTH = 4  # Example: Root -> Sub -> SubSub -> SubSubSub

    @staticmethod
    def validate_name(name: str) -> str:
        """Sanitizes the name to prevent whitespace bypasses."""
        clean_name = name.strip()
        if len(clean_name) < 2 or len(clean_name) > 100:
            raise DomainValidationError("Category name must be strictly between 2 and 100 characters.")
        return clean_name
        
    @staticmethod
    def validate_depth_limit(new_depth: int) -> None:
        """Prevents infinite nesting that causes OOM crashes during tree generation."""
        if new_depth > CategoryDomainValidator.MAX_CATEGORY_DEPTH:
            raise DomainValidationError(
                f"Category hierarchy cannot exceed a depth of {CategoryDomainValidator.MAX_CATEGORY_DEPTH} levels."
            )