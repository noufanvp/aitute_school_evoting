from django.core.cache import cache


def throttle_request(request, bucket, limit=60, window_seconds=60):
    if request.user and request.user.is_authenticated:
        # Isolate by authenticated user to prevent shared IP/proxy collisions
        identifier = f"user:{request.user.username}"
    else:
        # Fallback to proxy-aware client IP
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            identifier = f"ip:{x_forwarded_for.split(',')[0].strip()}"
        else:
            identifier = f"ip:{request.META.get('REMOTE_ADDR', 'unknown')}"

    key = f"rl:{bucket}:{identifier}"
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
