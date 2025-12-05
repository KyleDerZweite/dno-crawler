"""
Authentication routes.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.models import APIResponse, Token, User, UserRole
from src.db import SessionModel, UserModel, get_db

router = APIRouter()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# Request/Response models
class RegisterRequest(BaseModel):
    email: EmailStr
    name: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: User


# Utility functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(user_id: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        )
    
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
    }
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserModel:
    """Dependency to get the current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    query = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: Annotated[UserModel, Depends(get_current_user)],
) -> UserModel:
    """Dependency to ensure user is active and approved."""
    if current_user.role == UserRole.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account pending approval",
        )
    return current_user


async def get_admin_user(
    current_user: Annotated[UserModel, Depends(get_current_active_user)],
) -> UserModel:
    """Dependency to ensure user is admin."""
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


# Routes
@router.post("/register")
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse:
    """Register a new user account."""
    # Check if email already exists
    query = select(UserModel).where(UserModel.email == request.email)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user
    user = UserModel(
        email=request.email,
        name=request.name,
        password_hash=get_password_hash(request.password),
        role=UserRole.PENDING.value,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    return APIResponse(
        success=True,
        message="Registration successful. Please wait for admin approval.",
        data={
            "id": str(user.id),
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
    )


@router.post("/login")
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LoginResponse:
    """Login with email and password."""
    # Find user by email
    query = select(UserModel).where(UserModel.email == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )
    
    # Create tokens
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    
    # Store session
    session = SessionModel(
        user_id=user.id,
        token_hash=get_password_hash(access_token[-32:]),  # Hash last 32 chars
        refresh_token_hash=get_password_hash(refresh_token[-32:]),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=settings.jwt_access_token_expire_minutes),
        refresh_expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.jwt_refresh_token_expire_days),
    )
    db.add(session)
    await db.commit()
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(
            id=user.id,
            email=user.email,
            name=user.name,
            role=UserRole(user.role),
            is_active=user.is_active,
            email_verified=user.email_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ),
    )


@router.post("/logout")
async def logout(
    current_user: Annotated[UserModel, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> APIResponse:
    """Logout current user (invalidate session)."""
    # Invalidate all sessions for user
    query = select(SessionModel).where(
        SessionModel.user_id == current_user.id,
        SessionModel.is_active == True,
    )
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    for session in sessions:
        session.is_active = False
    
    await db.commit()
    
    return APIResponse(success=True, message="Logged out successfully")


@router.get("/me")
async def get_current_user_info(
    current_user: Annotated[UserModel, Depends(get_current_user)],
) -> User:
    """Get current user information."""
    return User(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        role=UserRole(current_user.role),
        is_active=current_user.is_active,
        email_verified=current_user.email_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
    )


@router.post("/refresh")
async def refresh_token(
    db: Annotated[AsyncSession, Depends(get_db)],
    refresh_token: str,
) -> Token:
    """Refresh access token using refresh token."""
    try:
        payload = jwt.decode(
            refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    
    # Verify user exists and is active
    query = select(UserModel).where(UserModel.id == user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    # Create new tokens
    new_access_token = create_access_token(str(user.id))
    new_refresh_token = create_refresh_token(str(user.id))
    
    return Token(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
    )
