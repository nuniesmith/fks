"""
Health check and system status views for FKS Trading Platform.
Provides comprehensive monitoring dashboard for solo development.
"""
import logging
import psutil
from datetime import datetime, timedelta
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis
import requests

logger = logging.getLogger(__name__)


class HealthDashboardView(View):
    """
    Comprehensive health dashboard for all FKS services.
    Shows service status, issues, and next steps for solo developer workflow.
    """
    
    def get(self, request):
        """Render the health dashboard with all system checks."""
        context = {
            'services': self._check_all_services(),
            'system_info': self._get_system_info(),
            'next_steps': self._get_next_steps(),
            'recent_issues': self._get_recent_issues(),
            'timestamp': datetime.now().isoformat(),
        }
        return render(request, 'web/health_dashboard.html', context)


    def _check_all_services(self):
        """Check status of all services."""
        services = {}
        
        # Database check
        services['database'] = self._check_database()
        
        # Redis check
        services['redis'] = self._check_redis()
        
        # Celery check
        services['celery'] = self._check_celery()
        
        # Prometheus check
        services['prometheus'] = self._check_service('http://prometheus:9090/-/healthy', 'Prometheus')
        
        # Grafana check
        services['grafana'] = self._check_service('http://grafana:3000/api/health', 'Grafana')
        
        # Tailscale check
        services['tailscale'] = self._check_tailscale()
        
        # RAG service check (GPU)
        services['rag_service'] = self._check_service('http://rag_service:8001/health', 'RAG Service', optional=True)
        
        return services


    def _check_database(self):
        """Check PostgreSQL database connection and stats."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                
                # Check TimescaleDB extension
                cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'timescaledb';")
                timescaledb = cursor.fetchone() is not None
                
                # Check pgvector extension
                cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector';")
                pgvector = cursor.fetchone() is not None
                
                # Get connection count
                cursor.execute("SELECT count(*) FROM pg_stat_activity;")
                connections = cursor.fetchone()[0]
                
            return {
                'status': 'healthy',
                'version': version.split(',')[0],
                'timescaledb': timescaledb,
                'pgvector': pgvector,
                'connections': connections,
                'message': '✓ Database operational'
            }
        except Exception as e:
            logger.error(f"Database check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': '✗ Database connection failed'
            }


    def _check_redis(self):
        """Check Redis connection and memory usage."""
        try:
            from django.conf import settings
            redis_url = settings.CACHES.get('default', {}).get('LOCATION', 'redis://redis:6379/1')
            
            # Test cache
            cache.set('health_check', 'ok', 10)
            test_value = cache.get('health_check')
            
            # Get Redis info
            r = redis.from_url(redis_url)
            info = r.info()
            
            return {
                'status': 'healthy',
                'version': info.get('redis_version'),
                'memory_used': info.get('used_memory_human'),
                'connected_clients': info.get('connected_clients'),
                'uptime_days': info.get('uptime_in_days'),
                'message': '✓ Redis operational'
            }
        except Exception as e:
            logger.error(f"Redis check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': '✗ Redis connection failed'
            }


    def _check_celery(self):
        """Check Celery worker status."""
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            
            # Check active workers
            stats = inspect.stats()
            active_tasks = inspect.active()
            scheduled_tasks = inspect.scheduled()
            
            if not stats:
                return {
                    'status': 'unhealthy',
                    'message': '✗ No Celery workers found',
                    'workers': 0
                }
            
            worker_count = len(stats)
            total_active = sum(len(tasks) for tasks in (active_tasks or {}).values())
            
            return {
                'status': 'healthy',
                'workers': worker_count,
                'active_tasks': total_active,
                'message': f'✓ {worker_count} worker(s) active'
            }
        except Exception as e:
            logger.error(f"Celery check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': '✗ Celery check failed'
            }


    def _check_service(self, url, name, optional=False):
        """Generic service health check via HTTP."""
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                return {
                    'status': 'healthy',
                    'message': f'✓ {name} operational'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': f'✗ {name} returned status {response.status_code}'
                }
        except requests.exceptions.RequestException as e:
            if optional:
                return {
                    'status': 'optional',
                    'message': f'⚠ {name} not available (optional service)'
                }
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': f'✗ {name} unreachable'
            }


    def _check_tailscale(self):
        """Check Tailscale VPN status."""
        try:
            # Check if tailscale container is responding
            # This is a simplified check - expand based on your needs
            response = requests.get('http://tailscale:41641/status', timeout=2)
            return {
                'status': 'healthy',
                'message': '✓ Tailscale VPN active'
            }
        except Exception as e:
            return {
                'status': 'optional',
                'message': '⚠ Tailscale not configured or inactive'
            }


    def _get_system_info(self):
        """Get system resource information."""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available': f"{memory.available / (1024**3):.2f} GB",
                'disk_percent': disk.percent,
                'disk_free': f"{disk.free / (1024**3):.2f} GB",
            }
        except Exception as e:
            logger.error(f"System info check failed: {e}")
            return {}


    def _get_next_steps(self):
        """
        Determine next development steps based on system status.
        Helps solo developer prioritize work.
        """
        steps = []
        
        # Check if tests are passing
        steps.append({
            'priority': 'high',
            'category': 'Testing',
            'task': 'Run test suite',
            'command': 'make test',
            'description': 'Ensure all tests pass before new development'
        })
        
        # Check if tasks are implemented
        steps.append({
            'priority': 'high',
            'category': 'Development',
            'task': 'Implement Celery tasks',
            'file': 'src/trading/tasks.py',
            'description': 'Currently stubs - implement signal generation, backtesting'
        })
        
        # RAG system development
        steps.append({
            'priority': 'high',
            'category': 'FKS Intelligence',
            'task': 'Build RAG-powered intelligence system',
            'file': 'src/rag/',
            'description': 'Implement trading recommendations based on account state'
        })
        
        # Web UI development
        steps.append({
            'priority': 'medium',
            'category': 'UI/UX',
            'task': 'Build out web templates',
            'file': 'src/web/templates/',
            'description': 'Create HTML/CSS for trading dashboard, signals page'
        })
        
        # Django migration
        steps.append({
            'priority': 'medium',
            'category': 'Migration',
            'task': 'Migrate FastAPI routes to Django',
            'file': 'src/api/',
            'description': 'Convert remaining API endpoints to Django views'
        })
        
        return steps


    def _get_recent_issues(self):
        """
        Scan for recent issues that need attention.
        Parses logs and system state.
        """
        issues = []
        
        # Check for database migrations needed
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                issues.append({
                    'severity': 'warning',
                    'category': 'Database',
                    'message': 'Unapplied migrations detected',
                    'action': 'Run: make migrate'
                })
        except Exception:
            pass
        
        # Check for disabled apps
        from django.conf import settings
        commented_apps = ['config', 'forecasting', 'chatbot', 'rag', 'data']
        for app in commented_apps:
            if app not in settings.INSTALLED_APPS:
                issues.append({
                    'severity': 'info',
                    'category': 'Configuration',
                    'message': f'App "{app}" is disabled in settings',
                    'action': 'Fix import issues to enable'
                })
        
        # Check system resources
        system = self._get_system_info()
        if system.get('memory_percent', 0) > 85:
            issues.append({
                'severity': 'warning',
                'category': 'Resources',
                'message': f'High memory usage: {system["memory_percent"]:.1f}%',
                'action': 'Consider restarting services or scaling'
            })
        
        if system.get('disk_percent', 0) > 85:
            issues.append({
                'severity': 'warning',
                'category': 'Resources',
                'message': f'Low disk space: {system["disk_free"]} free',
                'action': 'Clean up old logs and Docker volumes'
            })
        
        return issues


class HealthAPIView(View):
    """JSON API endpoint for health checks (for Prometheus/Grafana)."""
    
    def get(self, request):
        """Return health status as JSON."""
        dashboard = HealthDashboardView()
        
        services = dashboard._check_all_services()
        system_info = dashboard._get_system_info()
        
        # Determine overall health
        all_healthy = all(
            service.get('status') in ['healthy', 'optional'] 
            for service in services.values()
        )
        
        return JsonResponse({
            'status': 'healthy' if all_healthy else 'degraded',
            'timestamp': datetime.now().isoformat(),
            'services': services,
            'system': system_info,
        })
