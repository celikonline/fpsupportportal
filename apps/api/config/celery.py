import os
from celery import Celery, Task

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
class SecureTask(Task):
    def __call__(self, *args, **kwargs):
        from portal.runtime import validate_runtime_role
        validate_runtime_role()
        return super().__call__(*args, **kwargs)

app = Celery('support', task_cls='config.celery:SecureTask')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

