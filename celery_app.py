import os
from celery import Celery

# Ensure correct settings for Celery
# Redis is configured as both the broker and the results backend
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

celery_app = Celery(
    'sales_agent_celery',
    broker=redis_url,
    backend=redis_url,
    include=['tasks'] # Include the tasks module where tasks are defined
)

celery_app.conf.update(
    result_expires=3600,
    task_track_started=True,
    broker_connection_retry_on_startup=True,

    # Keep Redis connections alive during long-running tasks
    broker_transport_options={
        'visibility_timeout': 43200,   # 12 hours — prevents task requeue mid-run
        'socket_keepalive': True,
        'retry_on_timeout': True,
    },
    redis_socket_keepalive=True,
    redis_retry_on_timeout=True,
    redis_socket_timeout=300,          # 5 min socket timeout
    redis_socket_connect_timeout=30,

    # Retry policy for result backend writes
    result_backend_transport_options={
        'retry_policy': {
            'timeout': 30,
        }
    },

    # Worker settings for Windows (solo pool)
    worker_prefetch_multiplier=1,
    task_acks_late=True,               # ACK only after task completes
)

if __name__ == '__main__':
    celery_app.start()
