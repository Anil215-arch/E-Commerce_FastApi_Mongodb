from app.schemas.user_schema import UserRegister, UserUpdateProfile
from app.core.exceptions import DomainValidationError

class UserValidator:
    RESERVED_USERNAMES = {"admin", "support", "system", "root", "superuser"}
    BANNED_EMAIL_DOMAINS = {"tempmail.com", "10minutemail.com", "mailinator.com"}

    @staticmethod
    def validate_registration(data: UserRegister) -> None:
        username = data.user_name.strip().lower()
        domain = data.email.split("@")[-1].strip().lower()

        if any(reserved in username for reserved in UserValidator.RESERVED_USERNAMES):
            raise DomainValidationError("Username contains restricted keyword.")

        if any(domain == banned or domain.endswith(f".{banned}") 
               for banned in UserValidator.BANNED_EMAIL_DOMAINS):
            raise DomainValidationError("Disposable email domains are not permitted.")

    @staticmethod
    def validate_profile_update(data: UserUpdateProfile) -> None:
        if data.user_name:
            username = data.user_name.strip().lower()
            if any(reserved in username for reserved in UserValidator.RESERVED_USERNAMES):
                raise DomainValidationError("Username contains restricted keyword.")