"""
Simplified Celery tasks for testing (without circular imports).
"""

from celery import Celery

# Simple Celery configuration for testing
def create_celery_app():
    """Create a simple Celery app for testing."""
    celery = Celery('research_tasks')
    celery.conf.update(
        broker_url='redis://localhost:6379/0',
        result_backend='redis://localhost:6379/0',
        task_serializer='json',
        accept_content=['json'],
        result_serializer='json',
        timezone='UTC',
        enable_utc=True,
    )
    return celery

# Create Celery instance
celery = create_celery_app()

@celery.task(bind=True)
def simple_research_task(self, research_id: int, task_data: dict):
    """Simple research task for testing."""
    import time
    time.sleep(2)  # Simulate research work
    return {
        'status': 'completed',
        'research_id': research_id,
        'message': 'Simple research completed'
    }