from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection

def validate_runtime_role():
    if settings.DEBUG:
        return
    if connection.vendor != 'postgresql':
        raise ImproperlyConfigured('Production requires PostgreSQL')
    with connection.cursor() as cursor:
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        superuser, bypass = cursor.fetchone()
        cursor.execute("SELECT count(*) FROM pg_class WHERE relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user) AND relname LIKE 'portal_%%'")
        owns_tables = cursor.fetchone()[0]
        cursor.execute("SELECT has_table_privilege(current_user,'portal_auditevent','DELETE') OR has_table_privilege(current_user,'portal_auditevent','UPDATE')")
        audit_mutable = cursor.fetchone()[0]
    if superuser or bypass or owns_tables or audit_mutable:
        raise ImproperlyConfigured('Unsafe production DB role: owner, RLS bypass or mutable audit permissions')
