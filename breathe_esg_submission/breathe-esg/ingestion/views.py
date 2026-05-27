from django.utils import timezone
from django.db.models import Count, Sum, Q
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import (EmissionsRecord, IngestionBatch, IngestionError,
                     Organization, EmissionFactor, AuditLog, FacilityLookup)
from .serializers import (EmissionsRecordSerializer, IngestionBatchSerializer,
                          ReviewActionSerializer, AuditLogSerializer, OrganizationSerializer)
from .ingest import process_upload


class IngestionBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = IngestionBatchSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = self.request.user.organization
        return IngestionBatch.objects.filter(organization=org).prefetch_related('errors')


class UploadView(generics.CreateAPIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('file')
        source_type = request.data.get('source_type')
        
        if not file:
            return Response({'error': 'No file provided'}, status=400)
        if source_type not in ('sap', 'utility', 'travel'):
            return Response({'error': 'source_type must be sap, utility, or travel'}, status=400)
        
        org = request.user.organization
        if not org:
            return Response({'error': 'User has no organisation'}, status=400)
        
        batch = IngestionBatch.objects.create(
            organization=org,
            source_type=source_type,
            original_filename=file.name,
            uploaded_by=request.user,
            status=IngestionBatch.STATUS_PROCESSING,
        )
        
        try:
            content = file.read()
            result = process_upload(content, file.name, source_type, batch, org, request.user)
            return Response({
                'batch_id': str(batch.id),
                'rows_created': result['rows_created'],
                'errors': result['errors'],
                'status': batch.status,
            })
        except Exception as e:
            batch.status = IngestionBatch.STATUS_FAILED
            batch.notes = str(e)
            batch.save()
            return Response({'error': str(e), 'batch_id': str(batch.id)}, status=500)


class EmissionsRecordViewSet(viewsets.ModelViewSet):
    serializer_class = EmissionsRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = self.request.user.organization
        qs = EmissionsRecord.objects.filter(
            organization=org,
            is_deleted=False,
            superseded_by__isnull=True
        ).select_related('batch', 'emission_factor', 'facility')
        
        # Filters
        scope = self.request.query_params.get('scope')
        if scope:
            qs = qs.filter(scope=scope)
        
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        
        review_status = self.request.query_params.get('review_status')
        if review_status:
            qs = qs.filter(review_status=review_status)
        
        source_type = self.request.query_params.get('source_type')
        if source_type:
            qs = qs.filter(source_type=source_type)
        
        flagged = self.request.query_params.get('flagged')
        if flagged == 'true':
            qs = qs.filter(is_flagged_suspicious=True)
        
        return qs.order_by('-activity_date')

    @action(detail=True, methods=['post'])
    def review(self, request, pk=None):
        record = self.get_object()
        serializer = ReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_name = serializer.validated_data['action']
        notes = serializer.validated_data.get('notes', '')
        
        before_state = {
            'review_status': record.review_status,
            'review_notes': record.review_notes,
        }
        
        status_map = {
            'approve': EmissionsRecord.STATUS_APPROVED,
            'flag': EmissionsRecord.STATUS_FLAGGED,
            'reject': EmissionsRecord.STATUS_REJECTED,
        }
        
        record.review_status = status_map[action_name]
        record.reviewed_by = request.user
        record.reviewed_at = timezone.now()
        record.review_notes = notes
        record.save()
        
        AuditLog.objects.create(
            record=record,
            action=action_name,
            performed_by=request.user,
            before_state=before_state,
            after_state={'review_status': record.review_status, 'review_notes': notes},
            notes=notes,
        )
        
        return Response(EmissionsRecordSerializer(record).data)

    @action(detail=True, methods=['get'])
    def audit_trail(self, request, pk=None):
        record = self.get_object()
        logs = AuditLog.objects.filter(record=record)
        return Response(AuditLogSerializer(logs, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_stats(request):
    org = request.user.organization
    if not org:
        return Response({'error': 'No organisation'}, status=400)
    
    base_qs = EmissionsRecord.objects.filter(
        organization=org, is_deleted=False, superseded_by__isnull=True
    )
    
    totals = base_qs.aggregate(
        total_co2e=Sum('co2e_kg'),
        total_records=Count('id'),
        pending=Count('id', filter=Q(review_status='pending')),
        approved=Count('id', filter=Q(review_status='approved')),
        flagged=Count('id', filter=Q(review_status='flagged')),
        rejected=Count('id', filter=Q(review_status='rejected')),
        suspicious=Count('id', filter=Q(is_flagged_suspicious=True)),
    )
    
    by_scope = list(
        base_qs.values('scope').annotate(
            co2e=Sum('co2e_kg'), count=Count('id')
        ).order_by('scope')
    )
    
    by_source = list(
        base_qs.values('source_type').annotate(
            co2e=Sum('co2e_kg'), count=Count('id')
        )
    )
    
    by_category = list(
        base_qs.values('category').annotate(
            co2e=Sum('co2e_kg'), count=Count('id')
        )
    )
    
    recent_batches = IngestionBatch.objects.filter(organization=org).order_by('-uploaded_at')[:5]
    
    return Response({
        'totals': totals,
        'by_scope': by_scope,
        'by_source': by_source,
        'by_category': by_category,
        'recent_batches': IngestionBatchSerializer(recent_batches, many=True).data,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    return Response({'status': 'ok', 'service': 'breathe-esg'})
