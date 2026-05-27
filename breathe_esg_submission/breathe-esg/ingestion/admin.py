from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (User, Organization, IngestionBatch, EmissionsRecord,
                     EmissionFactor, FacilityLookup, AuditLog, IngestionError)

admin.site.register(Organization)
admin.site.register(EmissionFactor)
admin.site.register(FacilityLookup)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Breathe ESG', {'fields': ('organization', 'role')}),
    )

@admin.register(IngestionBatch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'source_type', 'status', 'row_count', 'error_count', 'uploaded_at']
    list_filter = ['source_type', 'status']

@admin.register(EmissionsRecord)
class RecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'organization', 'scope', 'category', 'activity_date', 'co2e_kg', 'review_status']
    list_filter = ['scope', 'category', 'review_status', 'source_type']

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'action', 'performed_by', 'performed_at']
    readonly_fields = ['id', 'record', 'action', 'performed_by', 'performed_at', 'before_state', 'after_state']
