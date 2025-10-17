"""
Custom authentication middleware for Redis-backed sessions
"""
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from .utils import validate_api_key, get_client_ip, check_rate_limit

User = get_user_model()


class APIKeyAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to authenticate requests using API keys
    """
    
    def process_request(self, request):
        # Skip if user is already authenticated
        if request.user.is_authenticated:
            return None
        
        # Check for API key in headers
        api_key = request.headers.get('X-API-Key') or request.GET.get('api_key')
        
        if api_key:
            is_valid, api_key_obj, error = validate_api_key(api_key)
            
            if not is_valid:
                return JsonResponse({
                    'error': error,
                    'message': 'API authentication failed'
                }, status=401)
            
            # Attach user to request
            request.user = api_key_obj.user
            request.api_key = api_key_obj
        
        return None


class SessionTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track user sessions and store metadata
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Update last activity
            session_key = request.session.session_key
            if session_key:
                from .models import UserSession
                try:
                    session = UserSession.objects.get(
                        session_key=session_key,
                        is_active=True
                    )
                    session.save()  # Updates last_activity via auto_now
                except UserSession.DoesNotExist:
                    pass
        
        return None


class RateLimitMiddleware(MiddlewareMixin):
    """
    Middleware for IP-based rate limiting
    """
    
    def process_request(self, request):
        # Skip for authenticated staff users
        if request.user.is_authenticated and request.user.is_staff:
            return None
        
        # Get identifier (use user ID if authenticated, otherwise IP)
        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
            limit = 300  # Higher limit for authenticated users
        else:
            identifier = f"ip:{get_client_ip(request)}"
            limit = 100  # Lower limit for anonymous users
        
        # Check rate limit
        is_allowed, current, remaining = check_rate_limit(identifier, limit=limit, window=60)
        
        if not is_allowed:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'message': 'Too many requests. Please try again later.',
                'retry_after': 60
            }, status=429)
        
        # Add rate limit info to response headers
        request.rate_limit_info = {
            'limit': limit,
            'current': current,
            'remaining': remaining
        }
        
        return None
    
    def process_response(self, request, response):
        # Add rate limit headers
        if hasattr(request, 'rate_limit_info'):
            info = request.rate_limit_info
            response['X-RateLimit-Limit'] = str(info['limit'])
            response['X-RateLimit-Remaining'] = str(info['remaining'])
        
        return response


class UserStateMiddleware(MiddlewareMixin):
    """
    Middleware to attach user state from Redis to request
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Attach user state to request
            request.user_state = request.user.get_user_state()
        
        return None
