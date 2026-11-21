"""Sign-in sessions: make refresh tokens revocable and single-use.

Each login opens a session. The refresh token carries the session id (sid) and a one-time id
(jti); a refresh rotates the jti. Presenting an old jti again means the token was copied, so the
whole session is revoked. Sign-out revokes the session, and access tokens carry the sid, so a
signed-out access token stops working at once (not only after its 30 minutes).
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.platform import new_id, utcnow


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    current_jti: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)  # logout | reuse | user_inactive
