from fastapi import APIRouter, HTTPException, Depends
import httpx
from urllib.parse import urlencode
import json
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

# Try to import database components
try:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import select
    from ..database import get_db
    from ..models import User, UserCredential
    from ..auth import create_access_token, get_current_user, get_password_hash, verify_password
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

from ..config import settings

router = APIRouter()


class ManualRegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class ManualLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


def _ensure_allowed_domain(email: str):
    allowed_domain = settings.allowed_email_domain.strip().lower()
    normalized_email = email.strip().lower()
    if "@" not in normalized_email:
        raise HTTPException(status_code=400, detail="Invalid email format")
    if not normalized_email.endswith(f"@{allowed_domain}"):
        raise HTTPException(status_code=403, detail="Only Amzur employees are allowed")


def _build_auth_payload(user: User):
    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name
        }
    }

if DATABASE_AVAILABLE:
    @router.post("/register")
    async def register_manual_user(payload: ManualRegisterRequest, db: AsyncSession = Depends(get_db)):
        email = payload.email.strip().lower()
        _ensure_allowed_domain(email)

        existing_user_result = await db.execute(select(User).where(User.email == email))
        if existing_user_result.scalars().first():
            raise HTTPException(status_code=409, detail="Account already exists")

        user = User(
            email=email,
            name=payload.name.strip(),
            google_id=f"local:{email}",
        )
        db.add(user)
        await db.flush()

        credentials = UserCredential(
            user_id=user.id,
            password_hash=get_password_hash(payload.password),
        )
        db.add(credentials)
        await db.commit()
        await db.refresh(user)

        return _build_auth_payload(user)

    @router.post("/login")
    async def login_manual_user(payload: ManualLoginRequest, db: AsyncSession = Depends(get_db)):
        email = payload.email.strip().lower()
        _ensure_allowed_domain(email)

        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalars().first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        cred_result = await db.execute(select(UserCredential).where(UserCredential.user_id == user.id))
        credentials = cred_result.scalars().first()
        if not credentials or not verify_password(payload.password, credentials.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        return _build_auth_payload(user)

    @router.get("/google/login")
    async def google_login():
        """Redirect to Google OAuth"""
        query = urlencode({
            "client_id": settings.google_client_id,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": settings.google_redirect_uri,
            "access_type": "offline",
            "prompt": "consent",
            "hd": settings.allowed_email_domain,
        })
        google_auth_url = f"https://accounts.google.com/o/oauth2/auth?{query}"
        return {"auth_url": google_auth_url}

    @router.get("/google/callback")
    async def google_callback(code: str, mode: str | None = None, db: AsyncSession = Depends(get_db)):
        """Handle Google OAuth callback"""
        # Exchange code for access token
        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.google_redirect_uri,
        }

        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_json = token_response.json()

            # Get user info
            user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {token_json['access_token']}"}
            user_response = await client.get(user_info_url, headers=headers)
            user_response.raise_for_status()
            user_info = user_response.json()

        email = user_info["email"].strip().lower()
        _ensure_allowed_domain(email)

        # Check if user exists, create if not
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()

        if not user:
            user = User(
                email=email,
                name=user_info["name"],
                google_id=user_info["id"]
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        auth_payload = _build_auth_payload(user)

        if mode == "json":
            return auth_payload

        redirect_query = urlencode({
            "access_token": auth_payload["access_token"],
            "token_type": auth_payload["token_type"],
            "user": json.dumps(auth_payload["user"]),
        })
        return RedirectResponse(url=f"{settings.frontend_base_url}/auth/callback?{redirect_query}")

    @router.get("/me")
    async def get_current_user_info(current_user: User = Depends(get_current_user)):
        """Get current user info"""
        return {
            "id": current_user.id,
            "email": current_user.email,
            "name": current_user.name
        }
else:
    # Fallback implementation without database
    @router.post("/register")
    async def register_manual_user_fallback():
        raise HTTPException(status_code=503, detail="Authentication not available - database not configured")

    @router.post("/login")
    async def login_manual_user_fallback():
        raise HTTPException(status_code=503, detail="Authentication not available - database not configured")

    @router.get("/google/login")
    async def google_login_fallback():
        """Google OAuth not available without database"""
        raise HTTPException(status_code=503, detail="Authentication not available - database not configured")

    @router.get("/google/callback")
    async def google_callback_fallback():
        """Google OAuth callback not available without database"""
        raise HTTPException(status_code=503, detail="Authentication not available - database not configured")

    @router.get("/me")
    async def get_current_user_info_fallback():
        """User info not available without database"""
        raise HTTPException(status_code=503, detail="Authentication not available - database not configured")