from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from portal.models import Tenant, TenantMembership
from portal.security import audit

class Command(BaseCommand):
    help = 'Provision tenant for existing admin without granting project content access.'
    def add_arguments(self, parser):
        parser.add_argument('--name', required=True)
        parser.add_argument('--admin', required=True)
    def handle(self, *args, **options):
        user=get_user_model().objects.filter(username=options['admin'],is_active=True).first()
        if not user or not options['name'].strip() or len(options['name'])>120:
            raise CommandError('Existing active administrator and valid tenant name required')
        from django.db import transaction
        with transaction.atomic():
            tenant=Tenant.objects.create(name=options['name'].strip())
            TenantMembership.objects.create(tenant=tenant,user=user,role='admin')
            audit('operator',tenant,None,'tenant_provisioned',tenant.pk)
        self.stdout.write(str(tenant.pk))
