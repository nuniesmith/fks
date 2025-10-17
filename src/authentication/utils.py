"""
Authentication utility functions
"""
from django.core.cache import cache
from user_agents import parse


def get_client_ip(request):
    """Extract client IP from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_device_info(request):
    """Parse user agent and extract device info"""
    user_agent_string = request.META.get('HTTP_USER_AGENT', '')
    user_agent = parse(user_agent_string)
    
    if user_agent.is_mobile:
        return 'mobile'
    elif user_agent.is_tablet:
        return 'tablet'
    elif user_agent.is_pc:
        return 'desktop'
    elif user_agent.is_bot:
        return 'bot'
    return 'unknown'


def check_rate_limit(identifier, limit=100, window=60):
    """
    Check rate limit for an identifier
    
    Args:
        identifier: Unique identifier (user_id, api_key, ip, etc.)
        limit: Maximum requests allowed
        window: Time window in seconds
    
    Returns:
        tuple: (is_allowed, current_count, remaining)
    """
    key = f"rate_limit:{identifier}"
    current = cache.get(key, 0)
    
    if current >= limit:
        return False, current, 0
    
    # Increment counter
    cache.set(key, current + 1, timeout=window)
    return True, current + 1, limit - current - 1


def validate_api_key(key):
    """
    Validate API key and check rate limits
    
    Returns:
        tuple: (is_valid, api_key_object, error_message)
    """
    from .models import APIKey
    from datetime import datetime
    
    try:
        api_key = APIKey.objects.get(key=key)
        
        # Check if active
        if not api_key.is_active:
            return False, None, "API key is inactive"
        
        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.now():
            return False, None, "API key has expired"
        
        # Check rate limit
        if api_key.is_rate_limited():
            return False, api_key, "Rate limit exceeded"
        
        # Increment usage
        api_key.increment_usage()
        
        return True, api_key, None
        
    except APIKey.DoesNotExist:
        return False, None, "Invalid API key"


def create_session_token(user):
    """Create a session token for a user"""
    import secrets
    token = secrets.token_urlsafe(32)
    key = f"session_token:{token}"
    
    # Store in Redis with 24 hour expiration
    cache.set(key, {
        'user_id': user.id,
        'username': user.username,
        'user_type': user.user_type,
    }, timeout=86400)
    
    return token


def validate_session_token(token):
    """
    Validate session token
    
    Returns:
        tuple: (is_valid, user_data)
    """
    key = f"session_token:{token}"
    user_data = cache.get(key)
    
    if user_data:
        return True, user_data
    return False, None
