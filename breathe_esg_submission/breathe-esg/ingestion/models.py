"""
Core data model for Breathe ESG ingestion platform.

Design principles:
- Multi-tenancy via Organization FK on every emissions row
- Immutable audit trail: EmissionsRecord is append-only; edits create new versions
- Source-of-truth tracking: every row knows which IngestionBatch produced it
- Scope 1/2/3 at the record level, not inferred
- Unit normalization happens at ingest time; raw value + raw unit preserved forever
- Analyst review workflow: PENDING -> APPROVED | FLAGGED | REJECTED
"""

from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid


# ---------------------------------------------------------------------------
# Tenancy
# ---------------------------------------------------------------------------

class Organization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE,
        null=True, blank=True, related_name='users'
    )
    ROLE_ANALYST = 'analyst'
    ROLE_ADMIN = 'admin'
    ROLES = [(ROLE_ANALYST, 'Analyst'), (ROLE_ADMIN, 'Admin')]
    role = models.CharField(max_length=20, choices=ROLES, default=ROLE_ANALYST)


# ---------------------------------------------------------------------------
# Ingestion batches (source-of-truth tracking)
# ---------------------------------------------------------------------------

class IngestionBatch(models.Model):
    """
    One upload/pull event. Everything produced from it references back here.
    Immutable after creation — we never mutate batch records.
    """
    SOURCE_SAP = 'sap'
    SOURCE_UTILITY = 'utility'
    SOURCE_TRAVEL = 'travel'
    SOURCES = [
        (SOURCE_SAP, 'SAP Fuel & Procurement'),
        (SOURCE_UTILITY, 'Utility / Electricity'),
        (SOURCE_TRAVEL, 'Corporate Travel'),
    ]

    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETE = 'complete'
    STATUS_FAILED = 'failed'
    STATUSES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETE, 'Complete'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCES)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PROCESSING)
    original_filename = models.CharField(max_length=512, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    row_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.source_type} batch {self.id} ({self.organization})"


class IngestionError(models.Model):
    """Individual parse/validation errors from a batch."""
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='errors')
    row_number = models.IntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    raw_value = models.TextField(blank=True)
    error_message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


# ---------------------------------------------------------------------------
# Reference / lookup tables
# ---------------------------------------------------------------------------

class FacilityLookup(models.Model):
    """
    SAP plant codes / cost centres mapped to human-readable sites.
    In real deployments this is uploaded by the client's SAP admin.
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    sap_plant_code = models.CharField(max_length=50)
    site_name = models.CharField(max_length=255)
    country_code = models.CharField(max_length=3)  # ISO 3166-1 alpha-3
    region = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('organization', 'sap_plant_code')


class EmissionFactor(models.Model):
    """
    Emission factors with provenance. We store the factor used at ingest time
    so recalculations are traceable.
    """
    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3
    SCOPES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    activity_type = models.CharField(max_length=100)   # e.g. 'diesel', 'electricity_uk', 'flight_economy'
    scope = models.IntegerField(choices=SCOPES)
    factor_kg_co2e_per_unit = models.DecimalField(max_digits=12, decimal_places=6)
    unit = models.CharField(max_length=30)             # the denominator unit: 'litre', 'kWh', 'km'
    source = models.CharField(max_length=200)          # e.g. 'DEFRA 2023', 'IEA 2022'
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.activity_type} ({self.factor_kg_co2e_per_unit} kgCO2e/{self.unit})"


# ---------------------------------------------------------------------------
# Core emissions records
# ---------------------------------------------------------------------------

class EmissionsRecord(models.Model):
    """
    The canonical normalised emissions row.

    Immutability contract:
    - Records are NEVER updated in place once approved.
    - If an analyst edits a row, a new version is created (version > 1) and
      the old row gets superseded_by set to the new record's id.
    - Deletes are logical only (is_deleted flag).

    Unit normalisation:
    - raw_quantity + raw_unit preserve exactly what came in.
    - quantity_kwh or quantity_litres or quantity_km stores normalised values
      so downstream code never has to re-parse units.
    - co2e_kg is always kilograms CO2-equivalent.
    """

    SCOPE_1 = 1
    SCOPE_2 = 2
    SCOPE_3 = 3
    SCOPE_CHOICES = [(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')]

    CATEGORY_FUEL = 'fuel'
    CATEGORY_PROCUREMENT = 'procurement'
    CATEGORY_ELECTRICITY = 'electricity'
    CATEGORY_FLIGHT = 'flight'
    CATEGORY_HOTEL = 'hotel'
    CATEGORY_GROUND = 'ground_transport'
    CATEGORIES = [
        (CATEGORY_FUEL, 'Fuel'),
        (CATEGORY_PROCUREMENT, 'Procurement'),
        (CATEGORY_ELECTRICITY, 'Electricity'),
        (CATEGORY_FLIGHT, 'Flight'),
        (CATEGORY_HOTEL, 'Hotel'),
        (CATEGORY_GROUND, 'Ground Transport'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_FLAGGED = 'flagged'
    STATUS_REJECTED = 'rejected'
    STATUSES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_FLAGGED, 'Flagged'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='emissions_records')

    # Versioning / audit trail
    version = models.IntegerField(default=1)
    superseded_by = models.UUIDField(null=True, blank=True)  # points to newer version's id
    is_deleted = models.BooleanField(default=False)

    # Source tracking
    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='records')
    source_type = models.CharField(max_length=20)      # denormalised from batch for query speed
    source_row_id = models.CharField(max_length=200, blank=True)  # e.g. SAP doc number, travel booking ref

    # Scope / category
    scope = models.IntegerField(choices=SCOPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORIES)

    # Temporal
    activity_date = models.DateField()                 # normalised to the day the activity occurred
    billing_period_start = models.DateField(null=True, blank=True)  # for utility bills
    billing_period_end = models.DateField(null=True, blank=True)

    # Raw values (preserved verbatim from source)
    raw_quantity = models.CharField(max_length=100)
    raw_unit = models.CharField(max_length=50)
    raw_description = models.TextField(blank=True)

    # Normalised quantity (unit depends on category)
    # We use separate columns rather than a single "normalised_value" to keep
    # units explicit and avoid a second lookup to interpret the number.
    quantity_kwh = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    quantity_litres = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    quantity_km = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    quantity_nights = models.IntegerField(null=True, blank=True)

    # Emissions calculation
    co2e_kg = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    emission_factor = models.ForeignKey(
        EmissionFactor, on_delete=models.SET_NULL, null=True, blank=True
    )
    calculation_method = models.CharField(max_length=100, blank=True)  # e.g. 'factor*quantity', 'distance_based'

    # Location / facility
    facility = models.ForeignKey(
        FacilityLookup, on_delete=models.SET_NULL, null=True, blank=True
    )
    country_code = models.CharField(max_length=3, blank=True)
    city = models.CharField(max_length=100, blank=True)

    # Source-specific structured data (flexible JSON for fields that don't
    # belong in normalised columns — e.g. airport codes, SAP cost centre,
    # tariff name, vehicle registration)
    extra = models.JSONField(default=dict, blank=True)

    # Analyst review
    review_status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_records'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    # Suspicious / quality flags (set automatically during ingestion)
    is_flagged_suspicious = models.BooleanField(default=False)
    flag_reasons = models.JSONField(default=list, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-activity_date', '-created_at']
        indexes = [
            models.Index(fields=['organization', 'scope', 'activity_date']),
            models.Index(fields=['organization', 'review_status']),
            models.Index(fields=['batch']),
            models.Index(fields=['superseded_by']),
        ]

    def __str__(self):
        return f"{self.category} | {self.activity_date} | {self.co2e_kg} kgCO2e"


class AuditLog(models.Model):
    """
    Append-only log of all analyst actions on records.
    This is separate from Django's admin log — it's the audit trail
    that goes to the external auditor.
    """
    ACTION_APPROVE = 'approve'
    ACTION_FLAG = 'flag'
    ACTION_REJECT = 'reject'
    ACTION_EDIT = 'edit'
    ACTION_NOTE = 'note'
    ACTIONS = [
        (ACTION_APPROVE, 'Approved'),
        (ACTION_FLAG, 'Flagged'),
        (ACTION_REJECT, 'Rejected'),
        (ACTION_EDIT, 'Edited'),
        (ACTION_NOTE, 'Note Added'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(EmissionsRecord, on_delete=models.CASCADE, related_name='audit_log')
    action = models.CharField(max_length=20, choices=ACTIONS)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    before_state = models.JSONField(default=dict)   # snapshot of relevant fields before change
    after_state = models.JSONField(default=dict)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['performed_at']
