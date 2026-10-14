from django.urls import path
from . import views as v, auth_views as a, invitations as i, api_keys as k, automation as bot
from . import customer_bridge as bridge

root = 'tenants/<uuid:t>/'
project = root + 'projects/<uuid:p>/'
urlpatterns = [path('health', v.health), path('session', a.session), path('auth/login', a.sign_in), path('auth/logout', a.sign_out),
               path('invitations/accept', i.accept), path(root + 'invitations', i.invitations),
               path('auth/mfa/setup', a.mfa_setup), path('auth/mfa/verify', a.mfa_verify), path('auth/password', a.change_password),
               path('me/tenants', v.tenants), path(root + 'projects', v.projects), path(root + 'admin', v.tenant_admin),
               path(root + 'audit-events', v.audit_events), path(root + 'privacy', v.privacy),
               path(root + 'privacy/<uuid:request_id>', v.privacy_action), path(project + 'settings', v.project_settings),
               path(project + 'capabilities', v.capabilities), path(project + 'members', v.members),
               path(project + 'api-keys', k.api_keys), path(project + 'api-keys/<uuid:key_id>', k.api_key_detail),
               path(project + 'automation', bot.automation_settings),
               path(project + 'automation/replies/<uuid:ticket_id>/retry', bot.retry_reply),
               path(project + 'work-items', bot.work_items),
               path(project + 'work-items/tickets/<uuid:ticket_id>', bot.work_detail),
               path(project + 'work-items/<uuid:work_id>/claim', bot.claim_work),
               path(project + 'work-items/<uuid:work_id>/update', bot.update_work),
               path(project + 'work-items/<uuid:work_id>/attachments/<uuid:attachment_id>', bot.work_attachment),
               path(project + 'customer-tickets', bridge.tickets),
               path(project + 'customer-tickets/<uuid:ticket_id>', bridge.detail),
               path(project + 'customer-tickets/<uuid:ticket_id>/comments', bridge.comments),
               path(project + 'customer-tickets/<uuid:ticket_id>/cancel', bridge.cancel),
               path(project + 'tickets', v.tickets),
               path(project + 'tickets/<uuid:ticket_id>', v.ticket_detail), path(project + 'tickets/<uuid:ticket_id>/transitions', v.transition),
               path(project + 'tickets/<uuid:ticket_id>/comments', v.comments), path(project + 'drafts', v.drafts),
               path(project + 'drafts/<uuid:draft_id>/uploads', v.uploads), path(project + 'attachments/<uuid:attachment_id>', v.attachment),
               path(project + 'notifications', v.notifications)]
