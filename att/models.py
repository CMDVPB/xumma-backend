from django.core.validators import MinValueValidator
import logging
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import models, IntegrityError
from django.db.models.functions import Lower
from django.core.exceptions import ValidationError

from abb.models import Currency, Country, BodyType
from abb.custom_exceptions import CustomApiException
from abb.utils import hex_uuid, get_contact_type_default, image_upload_path, normalize_reg_number
from abb.mixins import ProtectedDeleteMixin
from abb.constants import APP_LANGS_TUPLE, DOCUMENT_STATUS_CHOICES, VEHICLE_TYPES
from app.models import CategoryGeneral, Company, TypeGeneral, UnavailabilityReason


logger = logging.getLogger(__name__)

User = get_user_model()


class ContractReferenceDate(models.Model):
    USAGE_CONTRACT = "contract"
    USAGE_INVOICE = "invoice"
    USAGE_BOTH = "both"

    USAGE_CHOICES = [
        (USAGE_CONTRACT, "Contract"),
        (USAGE_INVOICE, "Invoice"),
        (USAGE_BOTH, "Both"),
    ]

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="company_contract_references"
    )

    code = models.CharField(
        max_length=50,
        unique=True,

    )

    label = models.CharField(
        max_length=255,

    )

    is_active = models.BooleanField(default=True)

    order = models.PositiveSmallIntegerField(default=0)

    is_system = models.BooleanField(default=False)

    usage = models.CharField(
        max_length=10,
        choices=USAGE_CHOICES,
        default=USAGE_BOTH,
        db_index=True
    )

    class Meta:
        verbose_name = "Contract reference date"
        verbose_name_plural = "Contract reference dates"
        ordering = ["order", "label"]

    def __str__(self):
        return self.label


class ContractReferenceDateTranslation(models.Model):
    reference_date = models.ForeignKey(
        ContractReferenceDate,
        on_delete=models.CASCADE,
        related_name="reference_date_translations"
    )

    language = models.CharField(
        max_length=2,
        choices=APP_LANGS_TUPLE,
        db_index=True
    )

    label = models.CharField(
        max_length=255
    )

    class Meta:
        verbose_name = ("Contract reference date translation")
        verbose_name_plural = ("Contract reference date translations")
        unique_together = ("reference_date", "language")

    def __str__(self):
        return f"{self.reference_date.code} [{self.language}]"


class TargetGroup(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_target_groups')

    group_name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __int__(self):
        return self.id or ''


class ContactStatus(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_contact_statuses')

    code = models.CharField(
        max_length=30,
        unique=True,
        db_index=True
    )
    name = models.CharField(
        max_length=100
    )
    description = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    # behavior flags
    is_blocking = models.BooleanField(
        default=False,
        help_text="If true, contact cannot be used in operations"
    )
    severity = models.PositiveSmallIntegerField(
        default=0,
        help_text="Higher = worse (used for sorting & UI color)"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact Status"
        verbose_name_plural = "Contact Statuses"
        ordering = ["severity", "name"]

    def __str__(self):
        return self.name


class ContactManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Contact(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_contacts')

    created_at = models.DateTimeField(auto_now_add=True)

    company_name = models.CharField(
        max_length=150, null=True, verbose_name=('company_name'))
    alias_company_name = models.CharField(
        max_length=150, null=True, blank=True)
    is_same_address = models.BooleanField(default=False)

    fiscal_code = models.CharField(
        max_length=20, blank=True, null=True)
    vat_code = models.CharField(max_length=20, blank=True, null=True)
    reg_com = models.CharField(max_length=30, blank=True, null=True)
    subscribed_capital = models.CharField(max_length=30, blank=True, null=True)

    country_code_legal = models.ForeignKey(
        Country, on_delete=models.SET_NULL, related_name='country_code_legal_contacts', null=True, blank=True)
    zip_code_legal = models.CharField(max_length=20, blank=True, null=True)
    city_legal = models.CharField(max_length=50, blank=True, null=True)
    address_legal = models.CharField(max_length=100, blank=True, null=True)
    county_legal = models.CharField(max_length=10, blank=True, null=True)
    sect_legal = models.CharField(max_length=100, blank=True, null=True)

    country_code_post = models.ForeignKey(
        Country, on_delete=models.SET_NULL, related_name='country_code_post_contacts', null=True, blank=True)
    zip_code_post = models.CharField(max_length=20, blank=True, null=True)
    city_post = models.CharField(max_length=50, blank=True, null=True)
    address_post = models.CharField(max_length=100, blank=True, null=True)
    county_post = models.CharField(max_length=10, blank=True, null=True)

    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    email = models.EmailField(
        max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    messanger = models.CharField(max_length=100, null=True, blank=True)
    comment1 = models.CharField(max_length=500, null=True, blank=True)
    comment2 = models.CharField(max_length=500, null=True, blank=True)
    other = models.CharField(max_length=200, null=True, blank=True)

    is_vat_payer = models.BooleanField(default=False)

    contact_type = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), default=get_contact_type_default, size=5)

    contract_reference_date = models.ForeignKey(
        ContractReferenceDate, on_delete=models.SET_NULL, related_name='contract_reference_date_contacts', null=True, blank=True)

    status = models.ForeignKey(
        ContactStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="status_contacts"
    )

    status_updated_at = models.DateTimeField(auto_now=True)

    objects = ContactManager()

    class Meta:
        verbose_name = "Contact"
        verbose_name_plural = "Contacts"
        constraints = [
            models.UniqueConstraint("company", Lower(
                "company_name"), name='unique_together company company_name')
        ]

    def save(self, *args, **kwargs):
        try:
            super(Contact, self).save(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f'ERRORLOG647 class Contact. save. Error: {e}')
            raise CustomApiException(409, 'unique_together')

    def natural_key(self):
        return (self.company_name)

    @property
    def is_blocked(self):
        return bool(self.status and self.status.is_blocking)

    def __str__(self):
        return self.company_name or str(self.id) or ''


class ContactStatusHistory(models.Model):
    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="status_histories"
    )

    old_status = models.ForeignKey(
        ContactStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="old_status_histories"
    )
    new_status = models.ForeignKey(
        ContactStatus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="new_status_histories"
    )

    reason = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changed_by_status_histories"
    )

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contact Status History"
        verbose_name_plural = "Contact Status History"
        ordering = ["-changed_at"]


class ContractTemplate(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_contract_templates"
    )

    name = models.CharField(max_length=255)
    language = models.CharField(max_length=5, choices=APP_LANGS_TUPLE)

    content = models.TextField()

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("company", "name", "language")

    def __str__(self):
        return f"{self.name} ({self.language})"


class Contract(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_contracts"
    )

    contact = models.ForeignKey(
        Contact,
        on_delete=models.CASCADE,
        related_name="contact_contracts"
    )

    template = models.ForeignKey(
        ContractTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="template_contracts"
    )

    number = models.CharField(max_length=50, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    title = models.CharField(max_length=100, blank=True, null=True)
    content = models.TextField()

    days_to_pay = models.PositiveSmallIntegerField(default=0)

    reference_date = models.ForeignKey(
        ContractReferenceDate,
        on_delete=models.PROTECT,
        related_name="reference_date_contracts",
    )

    invoice_date = models.ForeignKey(
        ContractReferenceDate,
        on_delete=models.PROTECT,
        blank=True, null=True,
        related_name="invoice_date_contracts",
    )

    is_active = models.BooleanField(default=True)
    is_signed = models.BooleanField(default=False)

    signed_at = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_by_contracts"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} – {self.contact}"


class ContactSite(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_contact_sites')

    date_modified = models.DateTimeField(auto_now=True)

    name_site = models.CharField(max_length=255)
    address_site = models.CharField(max_length=255, blank=True, null=True)
    city_site = models.CharField(max_length=100, blank=True, null=True)
    zip_code_site = models.CharField(max_length=20, blank=True, null=True)
    country_code_site = models.ForeignKey(
        Country, on_delete=models.PROTECT, related_name='country_code_sites', blank=True, null=True)

    phone = models.CharField(max_length=100, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    comment1 = models.CharField(max_length=500, null=True, blank=True)
    comment2 = models.CharField(max_length=500, null=True, blank=True)

    language = models.CharField(max_length=2, blank=True, null=True)

    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="contact_sites", blank=True, null=True)

    def __str__(self):
        return f"{self.name_site} – {self.company}"


class Person(ProtectedDeleteMixin, models.Model):
    '''
    Person to be used as contact person or driver at ContactSite
    '''
    # protected_related = ["routesheet_set"]
    protected_related = []

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    mobile = models.CharField(max_length=30, blank=True, null=True)
    comment = models.CharField(max_length=250, blank=True, null=True)

    is_driver = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)

    contact = models.ForeignKey(Contact, on_delete=models.CASCADE,
                                blank=True, null=True, related_name='contact_persons')

    site = models.ForeignKey(
        ContactSite, on_delete=models.CASCADE, blank=True, null=True, related_name="site_persons")

    default = models.BooleanField(default=False)

    target_group = models.ManyToManyField(
        TargetGroup, related_name="target_group_persons")

    def get_full_name(self):
        return " ".join(
            part for part in [self.first_name, self.last_name] if part
        )

    @property
    def full_name(self):
        return self.get_full_name()

    def __str__(self):
        return (self.first_name + ' ' + (self.last_name or '')) or ''


class EmissionClass(models.Model):
    """
    Vehicle emission classes (Euro 0, Euro 1, Euro 2, Euro 3, Euro 4, Euro 5, Euro 6)
    """
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_emission_classes')

    serial_number = models.SmallIntegerField(
        null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    code = models.CharField(max_length=20, unique=True)
    label = models.CharField(max_length=50)

    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Emission Class"
        verbose_name_plural = "Emission Classes"
        ordering = ["-serial_number"]
        unique_together = ("serial_number", "company")

    def __str__(self):
        return f'{self.code} - {self.label}'


class VehicleBrand(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicle_brands')

    name = models.CharField(max_length=100, unique=True)
    serial_number = models.PositiveSmallIntegerField(
        unique=True, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vehicle Brand"
        verbose_name_plural = "Vehicle Brands"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Vehicle(ProtectedDeleteMixin, models.Model):
    # protected_related = ["vehicle_tractor_route_sheets",
    #                      "vehicle_tractor_route_sheets"]

    protected_related = []

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicles')
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True, related_name='contact_vehicles')

    reg_number = models.CharField(max_length=50)
    normalized_reg_number = models.CharField(max_length=50)
    vin = models.CharField(max_length=50, null=True, blank=True)
    vehicle_type = models.CharField(
        choices=VEHICLE_TYPES, max_length=10, null=True, blank=True)

    brand = models.ForeignKey(
        VehicleBrand, on_delete=models.PROTECT, null=True, blank=True, related_name="brand_vehicles")
    vehicle_category = models.ForeignKey(
        CategoryGeneral, on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_category_vehicles')
    vehicle_category_type = models.ForeignKey(
        TypeGeneral, on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_category_type_vehicles')
    vehicle_body = models.ForeignKey(
        BodyType, on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_body_vehicles')
    emission_class = models.ForeignKey(
        EmissionClass, on_delete=models.CASCADE, null=True, blank=True, related_name='emission_class_vehicles')

    created_at = models.DateTimeField(auto_now_add=True)
    date_registered = models.DateField(null=True, blank=True)
    tank_volume = models.PositiveIntegerField(null=True, blank=True)
    adblue_tank_volume = models.PositiveIntegerField(null=True, blank=True)
    consumption_summer = models.PositiveIntegerField(null=True, blank=True)
    consumption_winter = models.PositiveIntegerField(null=True, blank=True)
    add_consumption_with_load = models.PositiveIntegerField(
        null=True, blank=True)
    change_oil_interval = models.PositiveIntegerField(null=True, blank=True)
    buy_price = models.PositiveIntegerField(null=True, blank=True)
    sell_price = models.PositiveIntegerField(null=True, blank=True)
    km_initial = models.PositiveIntegerField(null=True, blank=True)

    length = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    width = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    height = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    weight_capacity = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    volume_capacity = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)

    interval_taho = models.PositiveIntegerField(null=True, blank=True)
    last_date_unload_taho = models.DateField(null=True, blank=True)

    comment = models.CharField(
        max_length=500, blank=True, null=True)

    has_dgr = models.BooleanField(default=False)
    has_sanitary_certificate = models.BooleanField(default=False)
    has_l_paket = models.BooleanField(default=False)

    is_rented = models.BooleanField(default=False)
    is_service = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Vehicle"
        verbose_name_plural = "Vehicles"
        ordering = ['created_at']
        constraints = [
            models.UniqueConstraint(fields=[
                                    'company', "reg_number"], name='unique_together company reg_number')
        ]

    def save(self, *args, **kwargs):
        try:
            self.normalized_reg_number = normalize_reg_number(self.reg_number)
            super(Vehicle, self).save(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f'ERRORLOG951 class CompanyVehicle. save. Error: {e}')
            raise CustomApiException(409, 'unique_together')

    def __str__(self):
        return self.reg_number or ''


class VehicleDocument(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicle_documents')

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name='vehicle_documents'
    )

    document_type = models.ForeignKey(
        'ayy.DocumentType',
        on_delete=models.PROTECT,
        related_name='document_type_vehicle_documents'
    )

    document_number = models.CharField(
        max_length=100,
        blank=True
    )

    date_issued = models.DateField()
    date_expiry = models.DateField(null=True, blank=True)

    file = models.FileField(
        upload_to=image_upload_path,
        null=True,
        blank=True
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_expiry']

    def __str__(self):
        return f'{self.vehicle} – {self.document_type}'


class VehicleUnavailability(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicle_unavailabilities')

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name='vehicle_unavailabilities')

    start_date = models.DateField()
    end_date = models.DateField()

    reason = models.ForeignKey(
        UnavailabilityReason,
        on_delete=models.PROTECT,
        related_name='reason_vehicle_unavailabilities'
    )

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['vehicle', 'start_date', 'end_date']),
        ]

    def clean(self):
        qs = (VehicleUnavailability.objects
              .filter(
                  vehicle=self.vehicle,
                  start_date__lte=self.end_date,
                  end_date__gte=self.start_date,
              )
              .exclude(pk=self.pk))

        if qs.exists():
            raise ValidationError('Overlapping unavailability period vehicle')

    def __str__(self):
        return f'{self.vehicle} unavailable ({self.reason}) {self.start_date} → {self.end_date}'


class VehicleKmRate(models.Model):
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="vehicle_km_rates")
    rate_per_km = models.DecimalField(max_digits=6, decimal_places=3)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-valid_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["vehicle", "valid_from"],
                name="unique_vehicle_km_rate_start"
            )
        ]


class UserBaseSalary(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_base_salaries")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, related_name="currency_userbasesalary")
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-valid_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "valid_from"],
                name="unique_user_salary_start_date"
            )
        ]


class UserDailyAllowance(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="user_daily_allowances")
    amount_per_day = models.DecimalField(max_digits=8, decimal_places=2)
    currency = models.ForeignKey(
        Currency, on_delete=models.CASCADE, null=True, blank=True)
    applies_only_during_trip = models.BooleanField(default=True)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-valid_from"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "valid_from"],
                name="unique_user_daily_allowance_start"
            )
        ]


class UserVehicleKmRateOverride(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_vehicle_km_rate_overrides"
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.CASCADE,
        related_name="user_rate_overrides"
    )
    rate_per_km = models.DecimalField(max_digits=6, decimal_places=3)
    currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "vehicle", "valid_from"],
                name="unique_user_vehicle_km_override"
            )
        ]


class UserLoadingPointRate(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_loading_point_rates"
    )

    amount_per_point = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT
    )

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-valid_from"]
        verbose_name = "Loading point rate"
        verbose_name_plural = "Loading point rates"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(valid_to__gte=models.F("valid_from")) |
                    models.Q(valid_to__isnull=True)
                ),
                name="loading_point_rate_valid_range",
            )
        ]

    def __str__(self):
        return f"{self.user} – {self.amount_per_point} {self.currency} / loading point"


class UserUnloadingPointRate(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="user_unloading_point_rates"
    )

    amount_per_point = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT
    )

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-valid_from"]
        verbose_name = "Unloading point rate"
        verbose_name_plural = "Unloading point rates"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(valid_to__gte=models.F("valid_from")) |
                    models.Q(valid_to__isnull=True)
                ),
                name="unloading_point_rate_valid_range",
            )
        ]

    def __str__(self):
        return f"{self.user} – {self.amount_per_point} {self.currency} / unloading point"


class DriverUnavailability(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_driver_unavailabilities')

    driver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='driver_unavailabilities')

    start_date = models.DateField()
    end_date = models.DateField()

    reason = models.ForeignKey(
        UnavailabilityReason,
        on_delete=models.PROTECT,
        related_name='reason_driver_unavailabilities'
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['driver', 'start_date', 'end_date']),
        ]

    def clean(self):
        qs = (DriverUnavailability.objects
              .filter(
                  driver=self.driver,
                  start_date__lte=self.end_date,
                  end_date__gte=self.start_date,
              )
              .exclude(pk=self.pk))

        if qs.exists():
            raise ValidationError('Overlapping unavailability period driver')

    def __str__(self):
        return f'{self.driver} unavailable ({self.reason}) {self.start_date} → {self.end_date}'


class VehicleUnit(ProtectedDeleteMixin, models.Model):
    ''' Used for vehicle units of contacts '''

    # protected_related = ["vehicle_tractor_route_sheets",
    #                      "vehicle_tractor_route_sheets"]

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)

    reg_number = models.CharField(max_length=20)
    vehicle_type = models.CharField(
        choices=VEHICLE_TYPES, max_length=10, null=True, blank=True)
    payload = models.PositiveIntegerField(null=True, blank=True)
    volume = models.PositiveIntegerField(null=True, blank=True)
    comment = models.CharField(
        max_length=500, blank=True, null=True)

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, blank=True, null=True, related_name='contact_vehicle_units')

    class Meta:
        verbose_name = "Vehicle Unit"
        verbose_name_plural = "Vehicle Units"
        ordering = ['reg_number']
        constraints = [
            models.UniqueConstraint(fields=[
                                    'contact', "reg_number",], name='unique_together contact reg_number')
        ]

    def save(self, *args, **kwargs):
        try:
            super(VehicleUnit, self).save(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f'ERRORLOG951 class VehicleUnit. save. Error: {e}')
            raise CustomApiException(409, 'unique_together')

    def __str__(self):
        return self.reg_number or ''


class BankAccount(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_bank_accounts')

    currency_code = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, null=True, blank=True, related_name='bankaccountscurrency')
    iban_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=150, null=True, blank=True)
    bank_code = models.CharField(max_length=30)
    bank_address = models.CharField(max_length=250, null=True, blank=True)
    add_instructions = models.TextField(max_length=700, null=True, blank=True)
    include_in_inv = models.BooleanField(default=False, null=True, blank=True)

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True, related_name='contact_bank_accounts')

    class Meta:
        verbose_name = "Bank account"
        verbose_name_plural = "Bank accounts"

    def __str__(self):
        return self.iban_number or ''


class Note(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_notes')

    note_short = models.CharField(
        max_length=100, blank=True, null=True)
    note_description = models.CharField(
        max_length=1000, blank=True, null=True)

    class Meta:
        verbose_name = "Note"
        verbose_name_plural = "Notes"

    def __str__(self) -> str:
        return str(self.id) or ''


class PaymentTerm(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_payment_terms')

    payment_term_short = models.CharField(
        max_length=100)
    payment_term_description = models.CharField(
        max_length=1000, blank=True, null=True)
    payment_term_days = models.SmallIntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "Payment Term"
        verbose_name_plural = "Payment Terms"

    def __str__(self) -> str:
        return str(self.id) or ''


class Term(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_terms')
    term_short = models.CharField(max_length=100, blank=True, null=True)
    term_description = models.CharField(
        max_length=40000, blank=True, null=True)

    class Meta:
        verbose_name = "Term"
        verbose_name_plural = "Terms"

    def __str__(self) -> str:
        return str(self.id) or ''


class AuthorizationCEMTCategories(models.Model):
    ''' Categories for Authorizations, CEMTS '''
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_authorization_cemt_categories")

    serial_number = models.PositiveSmallIntegerField(unique=True)
    order_number = models.PositiveSmallIntegerField(unique=True)
    st = models.CharField(
        max_length=25, blank=True, null=True)
    description = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = "Status"
        verbose_name_plural = "Statuses"
        ordering = ['serial_number']

    def __str__(self):
        return self.st or ''


class AuthorizationCEMT(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_authorization_cemts")

    created_at = models.DateTimeField(auto_now_add=True)
    date_received = models.DateField(null=True, blank=True)
    date_expire = models.DateField()
    fee_amount = models.PositiveSmallIntegerField(null=True, blank=True)

    series = models.CharField(max_length=20, null=True, blank=True)
    number = models.CharField(max_length=20)

    countries = models.ManyToManyField(
        Country, related_name="countries_authorization_cemts")
    restricted_countries = models.ManyToManyField(
        Country, related_name="restricted_countries_authorization_cemts")
    category = models.ForeignKey(
        AuthorizationCEMTCategories, on_delete=models.CASCADE, null=True,
        blank=True, related_name="category_authorization_cemts")
    company_vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, null=True,
        blank=True, related_name="company_vehicle_authorization_cemts")

    is_standard_authorization = models.BooleanField(default=False)
    is_cemt_authorization = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Authorization CEMT"
        verbose_name_plural = "Authorization CEMTs"
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'series', 'number'],
                name='unique_company_series_number'
            )
        ]

    def clean(self):

        if self.date_expire and self.date_received:
            if self.date_expire <= self.date_received:
                raise ValidationError(
                    "Expiration date must be after the received date.")

    def save(self, *args, **kwargs):

        try:
            super(AuthorizationCEMT, self).save(*args, **kwargs)
        except IntegrityError as e:
            logger.error(
                f'ERRORLOG351 class AuthorizationCEMT. save. Error: {e}')
            raise CustomApiException(409, 'unique_together')

    def __str__(self):
        return f"{self.company.company_name} - {self.series or 'N/A'} {self.number}"


class RouteSheetStockBatch(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_route_sheet_stock")

    series = models.CharField(max_length=20, blank=True, null=True)

    number_from = models.PositiveIntegerField()
    number_to = models.PositiveIntegerField()

    received_at = models.DateField(null=True, blank=True)

    total_count = models.PositiveIntegerField(editable=False)
    used_count = models.PositiveIntegerField(default=0)

    notes = models.TextField(max_length=1000, blank=True)

    route_sheet_status = models.CharField(
        max_length=10, choices=DOCUMENT_STATUS_CHOICES, default=DOCUMENT_STATUS_CHOICES[0][0])
    reserved_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("company", "series", "number_from", "number_to")

    def save(self, *args, **kwargs):
        self.total_count = self.number_to - self.number_from + 1
        super().save(*args, **kwargs)

    @property
    def available_count(self):
        return self.total_count - self.used_count


class RouteSheetNumber(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_route_sheet_number")

    batch = models.ForeignKey(
        RouteSheetStockBatch, on_delete=models.PROTECT, related_name="batch_route_sheet_numbers")

    number = models.CharField(max_length=30)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["number"]

    def __str__(self):
        return self.number
