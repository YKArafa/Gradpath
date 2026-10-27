from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.database import get_session
from src.shared.models import Advisor
from src.shared.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# Router initialization
router = APIRouter(tags=["Authentication"])
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class AdvisorRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Full name of the advisor")
    email: EmailStr = Field(..., description="Unique email address")
    password: str = Field(..., min_length=6, max_length=128, description="Password (min 6 characters)")
    institution: str = Field(..., min_length=1, max_length=255, description="Associated academic institution")


class AdvisorLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class AdvisorResponse(BaseModel):
    id: int
    name: str
    email: str
    institution: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    advisor: AdvisorResponse


# ---------------------------------------------------------------------------
# Authentication Dependency
# ---------------------------------------------------------------------------

async def get_current_advisor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Advisor:
    """Dependency to validate the JWT bearer token and retrieve the logged-in Advisor."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired or is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    advisor_id = payload.get("sub")
    if not advisor_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    stmt = select(Advisor).where(Advisor.id == int(advisor_id))
    result = await session.execute(stmt)
    advisor = result.scalar_one_or_none()

    if not advisor:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Advisor associated with this token not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return advisor


async def get_optional_current_advisor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> Optional[Advisor]:
    """Dependency to retrieve the logged-in Advisor if credentials are provided, or None."""
    if not credentials or not credentials.credentials:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None

    advisor_id = payload.get("sub")
    if not advisor_id:
        return None

    stmt = select(Advisor).where(Advisor.id == int(advisor_id))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Controller Endpoints: Register & Login
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Advisor",
    description="Registers a new advisor account with hashed password and returns an access token.",
)
@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def register(
    data: AdvisorRegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Register a new advisor account."""
    normalized_email = data.email.strip().lower()

    # 1. Check if email is already registered
    existing_stmt = select(Advisor).where(Advisor.email == normalized_email)
    existing_result = await session.execute(existing_stmt)
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An advisor with email '{data.email}' already exists.",
        )

    # 2. Hash password securely using bcrypt
    hashed_password = hash_password(data.password)

    # 3. Create new advisor record
    new_advisor = Advisor(
        name=data.name.strip(),
        email=normalized_email,
        password_hash=hashed_password,
        institution=data.institution.strip(),
    )
    session.add(new_advisor)
    await session.commit()
    await session.refresh(new_advisor)

    # 4. Generate JWT access token
    token = create_access_token(
        data={
            "sub": str(new_advisor.id),
            "email": new_advisor.email,
            "role": "advisor",
        }
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        advisor=AdvisorResponse.model_validate(new_advisor),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Login an Advisor",
    description="Authenticates an advisor using email and password, returning a JWT access token.",
)
@router.post(
    "/auth/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def login(
    data: AdvisorLoginRequest,
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Authenticate an advisor and issue a JWT access token."""
    normalized_email = data.email.strip().lower()

    # 1. Retrieve advisor by email
    stmt = select(Advisor).where(Advisor.email == normalized_email)
    result = await session.execute(stmt)
    advisor = result.scalar_one_or_none()

    # 2. Verify existence and password hash
    if not advisor or not verify_password(data.password, advisor.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Generate JWT access token
    token = create_access_token(
        data={
            "sub": str(advisor.id),
            "email": advisor.email,
            "role": "advisor",
        }
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        advisor=AdvisorResponse.model_validate(advisor),
    )


@router.get(
    "/me",
    response_model=AdvisorResponse,
    summary="Get current logged-in Advisor",
    description="Returns the profile of the currently authenticated advisor.",
)
@router.get(
    "/auth/me",
    response_model=AdvisorResponse,
    include_in_schema=False,
)
async def get_me(
    current_advisor: Advisor = Depends(get_current_advisor),
) -> AdvisorResponse:
    """Return profile of the authenticated advisor."""
    return AdvisorResponse.model_validate(current_advisor)
