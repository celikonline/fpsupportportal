from importlib import import_module
from django.db import migrations

# Run data backfill after CreateModel's deferred foreign keys have been installed.
backfill_work = import_module('portal.migrations.0008_agent_workflow').backfill_work


class Migration(migrations.Migration):
    dependencies = [('portal', '0010_bridge_subject_index')]
    operations = [migrations.RunPython(backfill_work, migrations.RunPython.noop)]
