from django.core.cache import cache


def throttle_request(request, bucket, limit=60, window_seconds=60):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    key = f"rl:{bucket}:{ip}"
    current = cache.get(key)
    if current is None:
        cache.set(key, 1, timeout=window_seconds)
        return False
    if current >= limit:
        return True
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, current + 1, timeout=window_seconds)
    return False
