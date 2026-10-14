from django.db import migrations

SCOPED = ['project', 'projectmembership', 'ticket', 'comment', 'draft', 'attachment', 'ticketevent',
          'outbox', 'notification', 'idempotencyrecord', 'privacyrequest']

def install(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        for name in SCOPED:
            table = 'portal_' + name
            cursor.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')
            cursor.execute(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY')
            cursor.execute(f"CREATE POLICY tenant_boundary ON {table} USING (tenant_id::text = current_setting('app.tenant_id', true)) WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))")
        # Audit includes global authentication events, but runtime access is append-only.
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = 'support_app'")
        if cursor.fetchone():
            cursor.execute('GRANT USAGE ON SCHEMA public TO support_app')
            cursor.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO support_app')
            cursor.execute('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO support_app')
            cursor.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO support_app')
            cursor.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO support_app')
            cursor.execute('REVOKE UPDATE, DELETE, TRUNCATE ON portal_auditevent FROM support_app')
        cursor.execute('ALTER TABLE portal_project ADD CONSTRAINT project_tenant_id_unique UNIQUE (tenant_id, id)')
        cursor.execute('ALTER TABLE portal_ticket ADD CONSTRAINT ticket_scope_id_unique UNIQUE (tenant_id, project_id, id)')
        cursor.execute('ALTER TABLE portal_comment ADD CONSTRAINT comment_scope_id_unique UNIQUE (tenant_id, project_id, id)')
        cursor.execute('ALTER TABLE portal_draft ADD CONSTRAINT draft_scope_id_unique UNIQUE (tenant_id, project_id, id)')
        for name in ['projectmembership', 'ticket', 'comment', 'draft', 'attachment', 'ticketevent', 'outbox', 'notification', 'idempotencyrecord']:
            cursor.execute(f'ALTER TABLE portal_{name} ADD CONSTRAINT {name}_project_scope FOREIGN KEY (tenant_id, project_id) REFERENCES portal_project (tenant_id, id) DEFERRABLE INITIALLY DEFERRED')
        for name in ['comment', 'draft', 'attachment', 'ticketevent', 'outbox', 'notification']:
            cursor.execute(f'ALTER TABLE portal_{name} ADD CONSTRAINT {name}_ticket_scope FOREIGN KEY (tenant_id, project_id, ticket_id) REFERENCES portal_ticket (tenant_id, project_id, id) DEFERRABLE INITIALLY DEFERRED')
        cursor.execute('ALTER TABLE portal_attachment ADD CONSTRAINT attachment_comment_scope FOREIGN KEY (tenant_id, project_id, comment_id) REFERENCES portal_comment (tenant_id, project_id, id) DEFERRABLE INITIALLY DEFERRED')
        cursor.execute('ALTER TABLE portal_attachment ADD CONSTRAINT attachment_draft_scope FOREIGN KEY (tenant_id, project_id, draft_id) REFERENCES portal_draft (tenant_id, project_id, id) DEFERRABLE INITIALLY DEFERRED')

class Migration(migrations.Migration):
    dependencies = [('portal', '0001_initial')]
    operations = [migrations.RunPython(install, migrations.RunPython.noop)]
