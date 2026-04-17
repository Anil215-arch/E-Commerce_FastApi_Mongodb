from beanie import PydanticObjectId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from pydantic import ValidationError

from app.core.security import decode_token
from app.core.user_role import UserRole
from app.models.revoked_token_model import RevokedToken
from app.models.user_model import User
from app.schemas.user_schema import UserTokenData


bearer_scheme = HTTPBearer()


def get_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    return credentials.credentials


async def get_current_access_token_data(token: str = Depends(get_bearer_token)) -> UserTokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        token_data = UserTokenData.model_validate(payload)
        if not token_data.email or token_data.token_type != "access" or not token_data.jti:
            raise credentials_exception
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValidationError:
        raise credentials_exception
    except InvalidTokenError:
        raise credentials_exception

    revoked_token = await RevokedToken.find_one(RevokedToken.jti == token_data.jti)
    if revoked_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def get_current_user(token_data: UserTokenData = Depends(get_current_access_token_data)) -> User:
    user = await User.find_one(User.email == token_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

def RoleChecker(allowed_roles: list[UserRole]):
    def _role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action"
            )
        return user
    return _role_checker

def _require_user_id(current_user: User) -> PydanticObjectId:
    if current_user.id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing"
        )
    return current_user.id
