import uuid
from datetime import datetime, timedelta, timezone
from restaurant_bot.session.base import SessionStore, ConversationSession


class InMemorySessionStore(SessionStore):
    def __init__(self, ttl_minutes: int = 30):
        self._sessions: dict[str, ConversationSession] = {}
        self._ttl = timedelta(minutes=ttl_minutes)

    async def get(self, session_id: str) -> ConversationSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        # Check expiry
        if datetime.now(timezone.utc) - session.last_active_at > self._ttl:
            del self._sessions[session_id]
            return None
        return session

    async def save(self, session: ConversationSession) -> None:
        self._sessions[session.session_id] = session

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    async def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        now = datetime.now(timezone.utc)
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active_at > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
