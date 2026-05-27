from rest_framework import serializers
from .models import (EmissionsRecord, IngestionBatch, IngestionError,
                     Organization, EmissionFactor, AuditLog)


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ['id', 'name', 'slug']


class IngestionErrorSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionError
        fields = ['id', 'row_number', 'field_name', 'raw_value', 'error_message', 'created_at']


class IngestionBatchSerializer(serializers.ModelSerializer):
    errors = IngestionErrorSerializer(many=True, read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()

    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username if obj.uploaded_by else None

    class Meta:
        model = IngestionBatch
        fields = ['id', 'source_type', 'status', 'original_filename',
                  'uploaded_by_name', 'uploaded_at', 'row_count', 'error_count', 'notes', 'errors']


class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = ['id', 'activity_type', 'scope', 'factor_kg_co2e_per_unit', 'unit', 'source']


class EmissionsRecordSerializer(serializers.ModelSerializer):
    batch_info = serializers.SerializerMethodField()
    emission_factor_detail = EmissionFactorSerializer(source='emission_factor', read_only=True)
    facility_name = serializers.SerializerMethodField()

    def get_batch_info(self, obj):
        return {
            'id': str(obj.batch.id),
            'source_type': obj.batch.source_type,
            'uploaded_at': obj.batch.uploaded_at,
            'filename': obj.batch.original_filename,
        }

    def get_facility_name(self, obj):
        return obj.facility.site_name if obj.facility else None

    class Meta:
        model = EmissionsRecord
        fields = [
            'id', 'version', 'superseded_by', 'source_type', 'source_row_id',
            'scope', 'category', 'activity_date', 'billing_period_start', 'billing_period_end',
            'raw_quantity', 'raw_unit', 'raw_description',
            'quantity_kwh', 'quantity_litres', 'quantity_km', 'quantity_nights',
            'co2e_kg', 'calculation_method',
            'country_code', 'city', 'facility_name', 'extra',
            'review_status', 'reviewed_by_id', 'reviewed_at', 'review_notes',
            'is_flagged_suspicious', 'flag_reasons',
            'created_at', 'updated_at',
            'batch_info', 'emission_factor_detail',
        ]
        read_only_fields = ['id', 'version', 'superseded_by', 'created_at', 'updated_at',
                            'batch_info', 'source_type']


class ReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'flag', 'reject'])
    notes = serializers.CharField(required=False, allow_blank=True)


class AuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.SerializerMethodField()

    def get_performed_by_name(self, obj):
        return obj.performed_by.get_full_name() or obj.performed_by.username if obj.performed_by else 'System'

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'performed_by_name', 'performed_at',
                  'before_state', 'after_state', 'notes']
