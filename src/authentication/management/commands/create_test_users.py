"""
Management command to create test users for authentication testing

Usage:
    python manage.py create_test_users
    python manage.py create_test_users --clear  # Delete existing test users first
"""

import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from authentication.models import APIKey, UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = "Create test users for authentication testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing test users before creating new ones",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Deleting existing test users...")
            User.objects.filter(username__startswith="test_").delete()
            User.objects.filter(email__contains="@test.com").delete()

        self.stdout.write(self.style.SUCCESS("Creating test users..."))

        # Create admin user
        admin, created = User.objects.get_or_create(
            username="test_admin",
            defaults={
                "email": "admin@test.com",
                "user_type": "admin",
                "status": "active",
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Admin",
                "last_name": "User",
            },
        )
        if created:
            admin.set_password("admin123")
            admin.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created admin: {admin.username} / admin123")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ Admin user already exists: {admin.username}")
            )

        # Create trader user
        trader, created = User.objects.get_or_create(
            username="test_trader",
            defaults={
                "email": "trader@test.com",
                "user_type": "trader",
                "status": "active",
                "api_key_enabled": True,
                "max_concurrent_sessions": 5,
                "first_name": "Trader",
                "last_name": "User",
            },
        )
        if created:
            trader.set_password("trader123")
            trader.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created trader: {trader.username} / trader123")
            )

            # Create API key for trader
            api_key = APIKey.objects.create(
                user=trader,
                name="Test Trading Bot",
                key=secrets.token_urlsafe(48),
                permissions=["trading", "read_data", "backtest"],
                rate_limit=200,
            )
            self.stdout.write(self.style.SUCCESS(f"  API Key: {api_key.key}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ Trader user already exists: {trader.username}")
            )

        # Create analyst user
        analyst, created = User.objects.get_or_create(
            username="test_analyst",
            defaults={
                "email": "analyst@test.com",
                "user_type": "analyst",
                "status": "active",
                "first_name": "Analyst",
                "last_name": "User",
            },
        )
        if created:
            analyst.set_password("analyst123")
            analyst.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Created analyst: {analyst.username} / analyst123"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ Analyst user already exists: {analyst.username}")
            )

        # Create trial user
        trial, created = User.objects.get_or_create(
            username="test_trial",
            defaults={
                "email": "trial@test.com",
                "user_type": "viewer",
                "status": "trial",
                "max_concurrent_sessions": 1,
                "first_name": "Trial",
                "last_name": "User",
            },
        )
        if created:
            trial.set_password("trial123")
            trial.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created trial: {trial.username} / trial123")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ Trial user already exists: {trial.username}")
            )

        # Create viewer user
        viewer, created = User.objects.get_or_create(
            username="test_viewer",
            defaults={
                "email": "viewer@test.com",
                "user_type": "viewer",
                "status": "active",
                "first_name": "Viewer",
                "last_name": "User",
            },
        )
        if created:
            viewer.set_password("viewer123")
            viewer.save()
            self.stdout.write(
                self.style.SUCCESS(f"✓ Created viewer: {viewer.username} / viewer123")
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"⚠ Viewer user already exists: {viewer.username}")
            )

        # Set user states for testing
        trader.set_user_state(
            {
                "theme": "dark",
                "selected_exchange": "binance",
                "watchlist": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
                "active_strategy": "grid_trading",
                "notification_settings": {
                    "email": True,
                    "discord": True,
                    "trades": True,
                },
            }
        )

        analyst.set_user_state(
            {
                "theme": "light",
                "selected_timeframe": "1h",
                "favorite_indicators": ["RSI", "MACD", "BB"],
            }
        )

        self.stdout.write(self.style.SUCCESS("\n=== Test Users Created ==="))
        self.stdout.write("\nCredentials:")
        self.stdout.write("  Admin:   test_admin / admin123")
        self.stdout.write("  Trader:  test_trader / trader123")
        self.stdout.write("  Analyst: test_analyst / analyst123")
        self.stdout.write("  Trial:   test_trial / trial123")
        self.stdout.write("  Viewer:  test_viewer / viewer123")

        self.stdout.write("\nUser Types & Permissions:")
        self.stdout.write("  Admin:   All features")
        self.stdout.write("  Trader:  Trading, Backtest, Analytics, API")
        self.stdout.write("  Analyst: Analytics, Backtest, Reports")
        self.stdout.write("  Viewer:  Dashboard, Reports")

        self.stdout.write("\nNext Steps:")
        self.stdout.write("  1. Test login: POST /auth/login/")
        self.stdout.write("  2. Check admin: http://localhost/admin/")
        self.stdout.write("  3. Test API: bash scripts/test_auth.sh")
        self.stdout.write("  4. View Redis: docker-compose exec redis redis-cli")
