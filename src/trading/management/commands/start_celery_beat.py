"""
Django management command to start Celery beat scheduler.
Usage: python manage.py start_celery_beat
"""

from django.core.management.base import BaseCommand
import subprocess
import sys


class Command(BaseCommand):
    help = 'Start Celery beat scheduler for periodic tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loglevel',
            type=str,
            default='info',
            help='Log level (debug, info, warning, error, critical)'
        )
        parser.add_argument(
            '--scheduler',
            type=str,
            default='django_celery_beat.schedulers:DatabaseScheduler',
            help='Scheduler class to use'
        )

    def handle(self, *args, **options):
        loglevel = options['loglevel']
        scheduler = options['scheduler']

        self.stdout.write(self.style.SUCCESS('Starting Celery beat scheduler...'))
        self.stdout.write(f'Log level: {loglevel}')
        self.stdout.write(f'Scheduler: {scheduler}')

        cmd = [
            'celery',
            '-A', 'django',
            'beat',
            f'--loglevel={loglevel}',
            f'--scheduler={scheduler}',
        ]

        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nStopping Celery beat...'))
            sys.exit(0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            sys.exit(1)
