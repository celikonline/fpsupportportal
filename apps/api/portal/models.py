import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q

class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    class Meta:
        abstract = True

class Tenant(UUIDModel):
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)
    quota_bytes = models.BigIntegerField(default=1024 * 1024 * 1024)
    retention_days = models.PositiveIntegerField(default=365)
    audit_retention_days = models.PositiveIntegerField(default=730)
    retention_approved = models.BooleanField(default=False)

class TenantMembership(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=24, default='member')
    active = models.BooleanField(default=True)
    anonymized = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant', 'user'], name='tenant_user_unique')]

class Project(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=16)
    archived = models.BooleanField(default=False)
    timezone = models.CharField(max_length=64, default='Europe/Istanbul')
    first_response_minutes = models.PositiveIntegerField(default=240)
    resolution_minutes = models.PositiveIntegerField(default=1440)
    business_start = models.PositiveSmallIntegerField(default=9)
    business_end = models.PositiveSmallIntegerField(default=18)
    holidays = models.JSONField(default=list)
    categories = models.JSONField(default=list)
    next_number = models.PositiveIntegerField(default=1)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['tenant', 'code'], name='tenant_project_code'),
                       models.CheckConstraint(condition=Q(business_start__lt=models.F('business_end')) & Q(business_end__lte=24), name='project_hours_valid')]

class ProjectMembership(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=24, default='requester')
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'user'], name='project_user_unique')]

class Ticket(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=64, default='Genel')
    priority = models.CharField(max_length=16, default='normal')
    status = models.CharField(max_length=24, default='new')
    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='requested_tickets')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_tickets')
    tags = models.JSONField(default=list)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True)
    first_response_at = models.DateTimeField(null=True)
    first_response_due = models.DateTimeField()
    resolution_due = models.DateTimeField()
    waiting_since = models.DateTimeField(null=True)
    policy_snapshot = models.JSONField(default=dict)
    legal_hold = models.BooleanField(default=False)
    external_subject = models.CharField(max_length=64, blank=True)
    external_origin = models.CharField(max_length=32, blank=True)
    external_reference = models.CharField(max_length=128, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'number'], name='ticket_project_number')]
        indexes = [models.Index(fields=['tenant', 'project', 'status', '-updated_at']),
                   models.Index(fields=['tenant', 'project', 'external_subject'])]

class Comment(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    visibility = models.CharField(max_length=16, default='public')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(max_length=24, default='human')

class AutomationConfig(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.OneToOneField(Project, on_delete=models.CASCADE)
    enabled = models.BooleanField(default=False)
    bot = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    instructions = models.TextField(blank=True)
    external_agents = models.JSONField(default=list)

class AgentWork(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE, related_name='agent_work')
    state = models.CharField(max_length=24, default='review')
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reason = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    ticket_version = models.PositiveIntegerField(default=1)
    claim_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

class AutomationReply(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    ticket = models.OneToOneField(Ticket, on_delete=models.CASCADE)
    requested_version = models.PositiveIntegerField()
    processed_version = models.PositiveIntegerField(default=0)
    claim_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    attempts = models.PositiveIntegerField(default=0)
    retry_at = models.DateTimeField(null=True)
    error = models.CharField(max_length=200, blank=True)

class Draft(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, null=True, on_delete=models.CASCADE)
    visibility = models.CharField(max_length=16, default='public')
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)

class Attachment(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    draft = models.ForeignKey(Draft, null=True, on_delete=models.SET_NULL, related_name='attachments')
    ticket = models.ForeignKey(Ticket, null=True, on_delete=models.CASCADE, related_name='attachments')
    comment = models.ForeignKey(Comment, null=True, on_delete=models.CASCADE, related_name='attachments')
    filename = models.CharField(max_length=200)
    mime_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    state = models.CharField(max_length=16, default='scanning')
    reason = models.CharField(max_length=200, blank=True)
    storage_key = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=(Q(ticket__isnull=True) | Q(comment__isnull=True)), name='attachment_single_parent')]

class TicketEvent(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=48)
    detail = models.CharField(max_length=240, blank=True)
    reason = models.TextField(blank=True)
    visibility = models.CharField(max_length=16, default='public')
    created_at = models.DateTimeField(auto_now_add=True)

class AuditEvent(UUIDModel):
    tenant = models.ForeignKey(Tenant, null=True, on_delete=models.PROTECT)
    project = models.ForeignKey(Project, null=True, on_delete=models.PROTECT)
    actor_id = models.CharField(max_length=40)
    action = models.CharField(max_length=64)
    target_id = models.CharField(max_length=64, blank=True)
    result = models.CharField(max_length=24, default='success')
    created_at = models.DateTimeField(auto_now_add=True)

class Outbox(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    action = models.CharField(max_length=48)
    delivered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class Notification(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    event = models.ForeignKey(Outbox, on_delete=models.CASCADE)
    read = models.BooleanField(default=False)
    emailed = models.BooleanField(default=False)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'user'], name='notification_once')]

class IdempotencyRecord(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    key = models.CharField(max_length=128)
    operation = models.CharField(max_length=160)
    digest = models.CharField(max_length=64)
    response = models.JSONField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['project', 'user', 'key', 'operation'], name='idempotency_scope')]

class APIKey(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    prefix = models.CharField(max_length=12, unique=True)
    secret_hash = models.CharField(max_length=64)
    mode = models.CharField(max_length=16, choices=[('read', 'Read'), ('read_write', 'Read/write'), ('customer_bridge', 'Customer bridge')])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        indexes = [models.Index(fields=['tenant', 'project', 'user', '-created_at'])]

class PrivacyRequest(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16)
    status = models.CharField(max_length=24, default='pending')
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='privacy_approvals')
    verified = models.BooleanField(default=False)
    review_reason = models.CharField(max_length=500, blank=True)

class Invitation(UUIDModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, null=True, on_delete=models.CASCADE)
    email = models.EmailField()
    role = models.CharField(max_length=24, default='requester')
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    accepted = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

class MFADevice(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    encrypted_secret = models.TextField()
    enabled = models.BooleanField(default=False)
    last_counter = models.BigIntegerField(default=-1)

class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    failures = models.PositiveIntegerField(default=0)
    last_at = models.DateTimeField()
