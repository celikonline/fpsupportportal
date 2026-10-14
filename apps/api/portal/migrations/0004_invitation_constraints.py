from django.db import migrations

def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('ALTER TABLE portal_invitation ADD CONSTRAINT invitation_project_scope FOREIGN KEY (tenant_id, project_id) REFERENCES portal_project (tenant_id, id) DEFERRABLE INITIALLY DEFERRED')
        cursor.execute("CREATE UNIQUE INDEX auth_user_email_unique ON auth_user (lower(email)) WHERE email <> ''")

class Migration(migrations.Migration):
    dependencies = [('portal', '0003_privacyrequest_approved_by_and_more')]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
