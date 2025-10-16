"""
Django management command to start Celery worker.
Usage: python manage.py start_celery_worker
"""

from django.core.management.base import BaseCommand
import subprocess
import sys


class Command(BaseCommand):
    help = 'Start Celery worker for processing tasks'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loglevel',
            type=str,
            default='info',
            help='Log level (debug, info, warning, error, critical)'
        )
        parser.add_argument(
            '--concurrency',
            type=int,
            default=4,
            help='Number of concurrent worker processes'
        )
        parser.add_argument(
            '--queues',
            type=str,
            default='celery',
            help='Comma-separated list of queues to consume from'
        )

    def handle(self, *args, **options):
        loglevel = options['loglevel']
        concurrency = options['concurrency']
        queues = options['queues']

        self.stdout.write(self.style.SUCCESS('Starting Celery worker...'))
        self.stdout.write(f'Log level: {loglevel}')
        self.stdout.write(f'Concurrency: {concurrency}')
        self.stdout.write(f'Queues: {queues}')

        cmd = [
            'celery',
            '-A', 'django',
            'worker',
            f'--loglevel={loglevel}',
            f'--concurrency={concurrency}',
            f'--queues={queues}',
        ]

        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nStopping Celery worker...'))
            sys.exit(0)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
            sys.exit(1)
