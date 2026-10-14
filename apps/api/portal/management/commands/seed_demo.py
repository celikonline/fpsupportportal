import os
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from portal.models import *
from portal.security import tenant_context
from portal.sla import business_due, snapshot

class Command(BaseCommand):
    help = 'Create synthetic demo tenants. Development only; requires DEMO_PASSWORD.'
    def handle(self, *args, **options):
        password = os.environ.get('DEMO_PASSWORD')
        if not settings.DEBUG or not password or len(password) < 12:
            raise CommandError('Development and DEMO_PASSWORD (12+ characters) required')
        users = {}
        for username, first, last in [('admin', 'Ayşe', 'Yılmaz'), ('agent', 'Deniz', 'Kaya'), ('customer', 'Ece', 'Demir'), ('other', 'Mert', 'Aydın'),
                                      ('customer-bot', 'AI Müşteri', 'Agentı'), ('solution-bot', 'Dış Çözüm', 'Agentı')]:
            user, created = get_user_model().objects.get_or_create(username=username, defaults={'first_name': first, 'last_name': last})
            if created:
                user.set_password(password)
                user.save()
            users[username] = user
        for name, code in [('FaturaPort', 'fp'), ('Atlas Teknoloji', 'atlas')]:
            tenant, _ = Tenant.objects.get_or_create(name=name)
            for username, user in users.items():
                if code == 'atlas' and username == 'customer':
                    continue
                TenantMembership.objects.get_or_create(tenant=tenant, user=user, defaults={'role': 'admin' if username == 'admin' else 'member'})
            with tenant_context(tenant.pk):
                for project_name, project_code in [(('FaturaPort Platform' if code == 'fp' else 'Atlas ERP'), code), ('Mobil Uygulama', code + '-mobil')]:
                    project, _ = Project.objects.get_or_create(tenant=tenant, code=project_code, defaults={'name': project_name})
                    for username in users:
                        if code == 'atlas' and username == 'customer':
                            continue
                        if project_code.endswith('mobil') and username == 'other':
                            continue
                        ProjectMembership.objects.get_or_create(tenant=tenant, project=project, user=users[username],
                                                                 defaults={'role': {'admin': 'manager', 'agent': 'agent', 'customer': 'requester', 'other': 'requester', 'customer-bot': 'agent', 'solution-bot': 'agent'}[username]})
                    AutomationConfig.objects.get_or_create(tenant=tenant, project=project, defaults={
                        'bot': users['customer-bot'], 'external_agents': [users['solution-bot'].pk]})
                    if Ticket.objects.filter(project=project).exists():
                        for ticket in Ticket.objects.filter(project=project).exclude(status__in=['resolved', 'closed', 'cancelled']):
                            AgentWork.objects.get_or_create(ticket=ticket, defaults={'tenant': tenant, 'project': project, 'ticket_version': ticket.version})
                        continue
                    titles = [('E-fatura gönderiminde bağlantı hatası', 'high', 'in_progress', 'Entegrasyon sırasında bağlantı zaman aşımı alıyoruz. Tekrar denemede işlem devam ediyor.'),
                              ('Rapor ekranında tarih filtresi', 'normal', 'waiting_requester', 'Aylık raporda başlangıç tarihi seçildiğinde bazı kayıtlar eksik görünüyor.'),
                              ('Yeni kullanıcı daveti ulaşmıyor', 'normal', 'new', 'Yeni ekip arkadaşımıza gönderdiğimiz davet e-postası ulaşmadı.'),
                              ('Mobil bildirim ayarları', 'low', 'resolved', 'Bildirim tercihleri hakkında yardım rica ediyoruz.')]
                    for number, (title, priority, status, description) in enumerate(titles, 1):
                        now, policy = timezone.now(), snapshot(project)
                        requester = users['customer'] if code == 'fp' else users['other']
                        ticket = Ticket.objects.create(tenant=tenant, project=project, number=number, title=title, priority=priority,
                                                       status=status, description=description, requester=requester,
                                                       assignee=users['agent'] if status != 'new' else None, policy_snapshot=policy,
                                                       first_response_due=business_due(now, 240, policy), resolution_due=business_due(now, 1440, policy),
                                                       waiting_since=now if status == 'waiting_requester' else None,
                                                       resolved_at=now if status == 'resolved' else None)
                        TicketEvent.objects.create(tenant=tenant, project=project, ticket=ticket, actor=requester, action='created', detail='Talep oluşturuldu')
                        if status == 'in_progress':
                            Comment.objects.create(tenant=tenant, project=project, ticket=ticket, author=users['agent'],
                                                   body='Merhaba, bağlantı kayıtlarını inceliyoruz. Gelişmeleri bu talep üzerinden paylaşacağız.')
                            Comment.objects.create(tenant=tenant, project=project, ticket=ticket, author=users['agent'], visibility='internal',
                                                   body='İç ekip notu: entegrasyon servisinin zaman aşımı politikasını kontrol edelim.')
                    project.next_number = len(titles) + 1
                    for ticket in Ticket.objects.filter(project=project).exclude(status__in=['resolved', 'closed', 'cancelled']):
                        AgentWork.objects.get_or_create(ticket=ticket, defaults={'tenant': tenant, 'project': project, 'ticket_version': ticket.version})
                    project.save(update_fields=['next_number'])
                for product_project in Project.objects.filter(tenant=tenant, code__in=['ototeklif', 'fphr', 'fpfinansman']):
                    for username in ['customer-bot', 'solution-bot']:
                        ProjectMembership.objects.get_or_create(tenant=tenant, project=product_project, user=users[username], defaults={'role': 'agent'})
                    AutomationConfig.objects.get_or_create(tenant=tenant, project=product_project, defaults={
                        'bot': users['customer-bot'], 'external_agents': [users['solution-bot'].pk]})
        self.stdout.write(self.style.SUCCESS('Synthetic demo seeded: admin, agent, customer, other, customer-bot, solution-bot. Password supplied through environment.'))
