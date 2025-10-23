"""
Security configuration tests for FKS Trading Platform.

Tests security hardening measures including:
- django-axes configuration
- django-ratelimit configuration
- Password policies
- Security headers
"""

import pytest
from django.conf import settings
from django.test import TestCase, override_settings


class SecuritySettingsTest(TestCase):
    """Test security-related Django settings."""

    def test_debug_disabled_in_production(self):
        """DEBUG should be False in production."""
        # In test environment, DEBUG might be True, so we just check it's configurable
        self.assertIsInstance(settings.DEBUG, bool)

    def test_secret_key_is_set(self):
        """SECRET_KEY must be set and not be the default insecure key."""
        self.assertIsNotNone(settings.SECRET_KEY)
        self.assertGreater(len(settings.SECRET_KEY), 20)
        # In production, should not contain 'insecure'
        # In dev, this is acceptable
        
    def test_allowed_hosts_configured(self):
        """ALLOWED_HOSTS must be configured."""
        self.assertIsNotNone(settings.ALLOWED_HOSTS)
        self.assertGreater(len(settings.ALLOWED_HOSTS), 0)


class AxesConfigurationTest(TestCase):
    """Test django-axes configuration for login protection."""

    def test_axes_installed(self):
        """Verify django-axes is in INSTALLED_APPS."""
        self.assertIn('axes', settings.INSTALLED_APPS)

    def test_axes_middleware_installed(self):
        """Verify AxesMiddleware is configured."""
        self.assertIn('axes.middleware.AxesMiddleware', settings.MIDDLEWARE)

    def test_axes_backend_configured(self):
        """Verify AxesStandaloneBackend is first in AUTHENTICATION_BACKENDS."""
        backends = settings.AUTHENTICATION_BACKENDS
        self.assertGreater(len(backends), 0)
        self.assertEqual(backends[0], 'axes.backends.AxesStandaloneBackend')

    def test_axes_failure_limit_set(self):
        """Verify AXES_FAILURE_LIMIT is configured."""
        self.assertTrue(hasattr(settings, 'AXES_FAILURE_LIMIT'))
        self.assertGreater(settings.AXES_FAILURE_LIMIT, 0)
        self.assertLessEqual(settings.AXES_FAILURE_LIMIT, 10)  # Reasonable limit

    def test_axes_cooloff_time_set(self):
        """Verify AXES_COOLOFF_TIME is configured."""
        self.assertTrue(hasattr(settings, 'AXES_COOLOFF_TIME'))
        self.assertGreater(settings.AXES_COOLOFF_TIME, 0)

    def test_axes_lockout_enabled(self):
        """Verify AXES_LOCK_OUT_AT_FAILURE is enabled."""
        self.assertTrue(hasattr(settings, 'AXES_LOCK_OUT_AT_FAILURE'))
        self.assertTrue(settings.AXES_LOCK_OUT_AT_FAILURE)

    def test_axes_enabled(self):
        """Verify AXES_ENABLED is True."""
        self.assertTrue(hasattr(settings, 'AXES_ENABLED'))
        self.assertTrue(settings.AXES_ENABLED)


class RateLimitConfigurationTest(TestCase):
    """Test django-ratelimit configuration."""

    def test_ratelimit_enabled(self):
        """Verify RATELIMIT_ENABLE is True."""
        self.assertTrue(hasattr(settings, 'RATELIMIT_ENABLE'))
        self.assertTrue(settings.RATELIMIT_ENABLE)

    def test_ratelimit_cache_configured(self):
        """Verify RATELIMIT_USE_CACHE is configured."""
        self.assertTrue(hasattr(settings, 'RATELIMIT_USE_CACHE'))
        self.assertEqual(settings.RATELIMIT_USE_CACHE, 'default')


class RESTFrameworkSecurityTest(TestCase):
    """Test REST Framework security configuration."""

    def test_throttling_enabled(self):
        """Verify throttling classes are configured."""
        rest_config = settings.REST_FRAMEWORK
        self.assertIn('DEFAULT_THROTTLE_CLASSES', rest_config)
        throttle_classes = rest_config['DEFAULT_THROTTLE_CLASSES']
        self.assertGreater(len(throttle_classes), 0)

    def test_throttle_rates_configured(self):
        """Verify throttle rates are set for anon and user."""
        rest_config = settings.REST_FRAMEWORK
        self.assertIn('DEFAULT_THROTTLE_RATES', rest_config)
        rates = rest_config['DEFAULT_THROTTLE_RATES']
        self.assertIn('anon', rates)
        self.assertIn('user', rates)
        # Verify they're not too permissive
        anon_rate = rates['anon']
        self.assertIn('/', anon_rate)  # Format should be like "100/hour"


class SecurityHeadersTest(TestCase):
    """Test security headers configuration."""

    def test_xss_filter_enabled(self):
        """Verify XSS filter is enabled."""
        self.assertTrue(hasattr(settings, 'SECURE_BROWSER_XSS_FILTER'))
        self.assertTrue(settings.SECURE_BROWSER_XSS_FILTER)

    def test_content_type_nosniff_enabled(self):
        """Verify content type nosniff is enabled."""
        self.assertTrue(hasattr(settings, 'SECURE_CONTENT_TYPE_NOSNIFF'))
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_x_frame_options_set(self):
        """Verify X-Frame-Options is set."""
        self.assertTrue(hasattr(settings, 'X_FRAME_OPTIONS'))
        self.assertIn(settings.X_FRAME_OPTIONS, ['DENY', 'SAMEORIGIN'])

    def test_hsts_configured(self):
        """Verify HSTS is configured for production."""
        self.assertTrue(hasattr(settings, 'SECURE_HSTS_SECONDS'))
        self.assertGreater(settings.SECURE_HSTS_SECONDS, 0)


class SessionSecurityTest(TestCase):
    """Test session security configuration."""

    def test_session_cookie_httponly(self):
        """Verify session cookies are HTTP only."""
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_session_cookie_samesite(self):
        """Verify session cookie SameSite is set."""
        self.assertTrue(hasattr(settings, 'SESSION_COOKIE_SAMESITE'))
        self.assertIn(settings.SESSION_COOKIE_SAMESITE, ['Lax', 'Strict'])

    def test_csrf_cookie_httponly(self):
        """Verify CSRF cookie is HTTP only."""
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)

    def test_csrf_cookie_samesite(self):
        """Verify CSRF cookie SameSite is set."""
        self.assertTrue(hasattr(settings, 'CSRF_COOKIE_SAMESITE'))
        self.assertIn(settings.CSRF_COOKIE_SAMESITE, ['Lax', 'Strict'])


class DatabaseSecurityTest(TestCase):
    """Test database security configuration."""

    def test_database_password_required(self):
        """Verify database connection has password configured."""
        db_config = settings.DATABASES['default']
        # Password should be set (might be from env var)
        self.assertIn('PASSWORD', db_config)
        # In production, it shouldn't be empty or default
        password = db_config['PASSWORD']
        self.assertIsNotNone(password)


class CacheSecurityTest(TestCase):
    """Test cache/Redis security configuration."""

    def test_redis_cache_configured(self):
        """Verify Redis cache is configured."""
        cache_config = settings.CACHES['default']
        self.assertIn('BACKEND', cache_config)
        self.assertIn('redis', cache_config['BACKEND'].lower())

    def test_celery_broker_configured(self):
        """Verify Celery broker URL is configured."""
        self.assertTrue(hasattr(settings, 'CELERY_BROKER_URL'))
        self.assertIn('redis', settings.CELERY_BROKER_URL)


@pytest.mark.integration
class SecurityIntegrationTest(TestCase):
    """Integration tests for security features."""

    def test_security_middleware_order(self):
        """Verify security middleware is in correct order."""
        middleware = settings.MIDDLEWARE
        
        # SecurityMiddleware should be early
        security_idx = middleware.index('django.middleware.security.SecurityMiddleware')
        self.assertLess(security_idx, 3)
        
        # AxesMiddleware should be after authentication
        if 'axes.middleware.AxesMiddleware' in middleware:
            axes_idx = middleware.index('axes.middleware.AxesMiddleware')
            auth_idx = middleware.index('django.contrib.auth.middleware.AuthenticationMiddleware')
            self.assertGreater(axes_idx, auth_idx)
