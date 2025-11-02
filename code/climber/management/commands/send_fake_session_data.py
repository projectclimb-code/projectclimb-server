import time
from django.core.management.base import BaseCommand
from climber.tasks import send_fake_session_data_task


class Command(BaseCommand):
    help = 'Send fake session data to WebSocket for testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--session-id',
            type=str,
            help='UUID of the session to send data for (creates a new one if not provided)'
        )
        parser.add_argument(
            '--ws-url',
            type=str,
            default='ws://localhost:8000/ws/session-live/',
            help='WebSocket URL to connect to'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=60,
            help='Duration of the fake session in seconds'
        )
        parser.add_argument(
            '--create-session',
            action='store_true',
            help='Create a new session in the database'
        )
        parser.add_argument(
            '--monitor',
            action='store_true',
            help='Monitor the task progress until completion'
        )

    def handle(self, *args, **options):
        session_id = options.get('session_id')
        ws_url = options.get('ws_url')
        duration = options.get('duration')
        create_session = options.get('create_session')
        
        self.stdout.write(self.style.SUCCESS('Starting Celery task to send fake session data...'))
        
        # Trigger the Celery task
        task = send_fake_session_data_task.delay(
            session_id=session_id,
            ws_url=ws_url,
            duration=duration,
            create_session=create_session
        )
        
        self.stdout.write(self.style.SUCCESS(f'Started Celery task with ID: {task.id}'))
        
        # Optionally, we can monitor the task progress
        if options.get('monitor', False):
            self.stdout.write(self.style.SUCCESS('Monitoring task progress...'))
            while not task.ready():
                result = task.result
                if isinstance(result, dict):
                    status = result.get('status', 'unknown')
                    message = result.get('message', 'No message')
                    progress = result.get('progress', 0)
                    
                    if status == 'PROGRESS':
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Task in progress: {message} ({progress}%)'
                            )
                        )
                    elif status == 'ERROR':
                        self.stdout.write(
                            self.style.ERROR(f'Task error: {message}')
                        )
                        break
                
                time.sleep(2)
            
            # Get final result
            final_result = task.get()
            if final_result.get('status') == 'success':
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Task completed successfully. Session ID: {final_result.get('session_id')}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Task failed: {final_result.get('message')}"
                    )
                )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    'Task is running in the background. '
                    'You can check its status using the web interface or Django admin.'
                )
            )