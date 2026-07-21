import time
from collections import defaultdict
from fastapi import Request, HTTPException


class InMemoryRateLimiter:
    """Simple in-memory rate limiter. Use Redis-based for production with multiple workers."""

    def __init__(self, requests_per_minute: int = 30, burst_limit: int = 10):
        self._rpm = requests_per_minute
        self._burst = burst_limit
        self._requests: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str, now: float):
        """Remove requests older than 1 minute."""
        cutoff = now - 60
        self._requests[key] = [t for t in self._requests[key] if t > cutoff]

    def check(self, key: str) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        now = time.time()
        self._cleanup(key, now)

        # Check burst (requests in last 1 second)
        recent = [t for t in self._requests[key] if t > now - 1]
        if len(recent) >= self._burst:
            return False

        # Check per-minute limit
        if len(self._requests[key]) >= self._rpm:
            return False

        self._requests[key].append(now)
        return True

    def get_key(self, request: Request) -> str:
        """Generate rate limit key from request (IP + restaurant_id if present)."""
        client_ip = request.client.host if request.client else "unknown"
        restaurant_id = request.path_params.get("restaurant_id", "global")
        return f"{client_ip}:{restaurant_id}"


# Global rate limiter instance
rate_limiter = InMemoryRateLimiter(requests_per_minute=60, burst_limit=15)


async def check_rate_limit(request: Request):
    """FastAPI dependency for rate limiting."""
    key = rate_limiter.get_key(request)
    if not rate_limiter.check(key):
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please slow down.",
            headers={"Retry-After": "10"},
        )
