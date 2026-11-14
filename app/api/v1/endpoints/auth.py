from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.security import (
    create_access_token,
    verify_password,
    verify_secret_key,
)
from app.models.platform import Platform
from app.models.user import TelegramAccount, User, UserPlatformMembership
from app.schemas.auth import (
    HostPlatformLearnerTokenRequest,
    LoginRequest,
    TelegramLinkRequest,
    TelegramPlatformOption,
    TelegramSelectPlatformRequest,
    TelegramVerifyRequest,
    Token,
    UserResponse,
)
from app.services.telegram_service import telegram_service

router = APIRouter()


@router.post("/token", response_model=Token)
async def obtain_token(
    payload: HostPlatformLearnerTokenRequest | LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Unified Token Endpoint:
    1. Server-to-server: Host platform requests a secure short-lived token for a logged-in learner.
    2. Direct login: Admin or teacher logging in directly with credentials.
    """
    # Case 1: Host platform server-to-server learner token
    if isinstance(payload, HostPlatformLearnerTokenRequest) or hasattr(payload, "secret_key"):
        req: HostPlatformLearnerTokenRequest = payload  # type: ignore
        stmt = select(Platform).where(
            Platform.public_key == req.public_key, Platform.enabled == True
        )
        res = await db.execute(stmt)
        platform = res.scalar_one_or_none()

        if not platform or not verify_secret_key(req.secret_key, platform.secret_key_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid platform integration credentials",
            )

        # Find or create learner user record
        learner_stmt = (
            select(User)
            .join(UserPlatformMembership, UserPlatformMembership.user_id == User.id)
            .where(
                UserPlatformMembership.platform_id == platform.id,
                UserPlatformMembership.external_learner_id == req.external_learner_id,
            )
        )
        learner_res = await db.execute(learner_stmt)
        user = learner_res.scalar_one_or_none()

        if not user:
            # Create user and membership
            user = User(
                email=req.learner_email,
                full_name=req.learner_name,
                role=req.role or "learner",
                is_active=True,
            )
            db.add(user)
            await db.flush()

            membership = UserPlatformMembership(
                user_id=user.id,
                platform_id=platform.id,
                external_learner_id=req.external_learner_id,
                role=req.role or "learner",
            )
            db.add(membership)
            await db.commit()

        # Mint short-lived learner integration token
        expires_delta = timedelta(minutes=settings.INTEGRATION_TOKEN_EXPIRE_MINUTES)
        token_str = create_access_token(
            subject=user.id,
            expires_delta=expires_delta,
            extra_claims={
                "platform_id": platform.id,
                "role": user.role,
                "external_learner_id": req.external_learner_id,
                "platform_name": platform.name,
            },
        )
        return Token(
            access_token=token_str,
            expires_in=settings.INTEGRATION_TOKEN_EXPIRE_MINUTES * 60,
        )

    # Case 2: Direct user password login
    login_req: LoginRequest = payload  # type: ignore
    user_stmt = select(User).where(
        (User.email == login_req.username_or_email) | (User.id == login_req.username_or_email)
    )
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if (
        not user
        or not user.hashed_password
        or not verify_password(login_req.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_str = create_access_token(
        subject=user.id,
        expires_delta=expires_delta,
        extra_claims={"role": user.role},
    )
    return Token(
        access_token=token_str,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: User = Depends(get_current_user),
):
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token_str = create_access_token(
        subject=current_user.id,
        expires_delta=expires_delta,
        extra_claims={"role": current_user.role},
    )
    return Token(
        access_token=token_str,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/telegram/link")
async def link_telegram_account(
    payload: TelegramLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Links current user account to Telegram chat ID."""
    stmt = select(TelegramAccount).where(TelegramAccount.user_id == current_user.id)
    res = await db.execute(stmt)
    tg = res.scalar_one_or_none()

    if not tg:
        tg = TelegramAccount(
            user_id=current_user.id,
            telegram_chat_id=payload.telegram_chat_id,
            telegram_username=payload.telegram_username,
            phone_number="",
            is_verified=False,
        )
        db.add(tg)
    else:
        tg.telegram_chat_id = payload.telegram_chat_id
        tg.telegram_username = payload.telegram_username

    await db.commit()
    return {"status": "success", "message": "Telegram account association created"}


@router.post("/telegram/verify")
async def verify_telegram_phone(
    payload: TelegramVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Verifies phone number received via Telegram contact sharing against
    registered platform learner phone records.
    """
    result_message = await telegram_service.verify_contact_and_link(
        db=db,
        chat_id=payload.telegram_chat_id,
        tg_user_id=payload.telegram_user_id,
        phone_number=payload.phone_number,
        first_name=payload.first_name,
    )
    return {"status": "completed", "message": result_message}


@router.get("/telegram/platforms", response_model=list[TelegramPlatformOption])
async def get_telegram_learner_platforms(
    telegram_chat_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieves all authorized platform memberships for a verified Telegram user."""
    stmt = select(TelegramAccount).where(
        TelegramAccount.telegram_chat_id == telegram_chat_id, TelegramAccount.is_verified == True
    )
    res = await db.execute(stmt)
    tg = res.scalar_one_or_none()

    if not tg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram account not linked or not verified",
        )

    mem_stmt = (
        select(UserPlatformMembership, Platform)
        .join(Platform, UserPlatformMembership.platform_id == Platform.id)
        .where(UserPlatformMembership.user_id == tg.user_id, Platform.enabled == True)
    )
    mem_res = await db.execute(mem_stmt)
    memberships = mem_res.all()

    return [
        TelegramPlatformOption(
            platform_id=plat.id,
            platform_name=plat.name,
            domain=plat.domain,
            role=mem.role,
        )
        for mem, plat in memberships
    ]


@router.post("/telegram/select-platform")
async def select_telegram_platform(
    payload: TelegramSelectPlatformRequest,
    db: AsyncSession = Depends(get_db),
):
    """Sets the active platform for a verified Telegram user."""
    stmt = select(TelegramAccount).where(
        TelegramAccount.telegram_chat_id == payload.telegram_chat_id,
        TelegramAccount.is_verified == True,
    )
    res = await db.execute(stmt)
    tg = res.scalar_one_or_none()

    if not tg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Telegram account not verified"
        )

    # Verify membership exists
    mem_stmt = select(UserPlatformMembership).where(
        UserPlatformMembership.user_id == tg.user_id,
        UserPlatformMembership.platform_id == payload.platform_id,
    )
    mem_res = await db.execute(mem_stmt)
    if not mem_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Learner is not authorized for this platform",
        )

    tg.active_platform_id = payload.platform_id
    await db.commit()
    return {"status": "success", "message": "Active platform updated"}
