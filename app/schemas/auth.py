from datetime import datetime

from pydantic import BaseModel


class GoogleCallbackRequest(BaseModel):
    code: str
    code_verifier: str = ""


class AppleCallbackRequest(BaseModel):
    identity_token: str
    nonce: str


class RefreshRequest(BaseModel):
    refresh_token: str


class SessionUser(BaseModel):
    id: str
    email: str | None = None
    name: str | None = None


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: datetime


class AuthResponse(BaseModel):
    user: SessionUser
    session: SessionResponse


class AuthStartResponse(BaseModel):
    auth_url: str
