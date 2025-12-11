from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models.functions import Lower
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from abb.models import Currency, Country, BodyType
from abb.custom_exceptions import YourCustomApiExceptionName
from abb.utils import hex_uuid, get_contact_type_default
from abb.mixins import ProtectedDeleteMixin
from abb.constants import VEHICLE_TYPES
from app.models import Company

import logging
logger = logging.getLogger(__name__)


class EmissionClass(models.Model):
    """
    Vehicle emission classes (Euro 1, Euro 2, Euro 3, Euro 4, Euro 5, Euro 6)
    """
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_emission_classes')

    created_at = models.DateTimeField(auto_now_add=True)
    class_code = models.CharField(max_length=20, unique=True)
    class_name = models.CharField(max_length=50)
    description = models.TextField(blank=True, null=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Emission Class"
        verbose_name_plural = "Emission Classes"
        ordering = ["-class_code"]

    def __str__(self):
        return self.class_name


class VehicleBrand(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicle_brands')
    brand_name = models.CharField(max_length=100, unique=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vehicle Brand"
        verbose_name_plural = "Vehicle Brands"
        ordering = ["brand_name"]

    def __str__(self):
        return self.brand_name


class CompanyVehicle(ProtectedDeleteMixin, models.Model):
    protected_related = ["vehicle_tractor_route_sheets",
                         "vehicle_tractor_route_sheets"]

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicle_units')

    brand = models.ForeignKey(
        VehicleBrand, on_delete=models.PROTECT, null=True, blank=True, related_name="brand_company_vehicles")

    reg_number = models.CharField(max_length=50)
    vin = models.CharField(max_length=50, null=True, blank=True)
    vehicle_type = models.CharField(
        choices=VEHICLE_TYPES, max_length=10, null=True, blank=True)
    vehicle_body = models.ForeignKey(
        BodyType, on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_body_company_vehicles')
    emission_class = models.ForeignKey(
        EmissionClass, on_delete=models.CASCADE, null=True, blank=True, related_name='emission_class_company_vehicles')

    date_registered = models.DateField(null=True, blank=True)
    tank_volume = models.PositiveIntegerField(null=True, blank=True)
    consumption_summer = models.PositiveIntegerField(null=True, blank=True)
    consumption_winter = models.PositiveIntegerField(null=True, blank=True)
    add_consumption_with_load = models.PositiveIntegerField(
        null=True, blank=True)
    change_oil_interval = models.PositiveIntegerField(null=True, blank=True)
    buy_price = models.PositiveIntegerField(null=True, blank=True)
    sell_price = models.PositiveIntegerField(null=True, blank=True)
    length = models.PositiveIntegerField(null=True, blank=True)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    weight_capacity = models.PositiveIntegerField(null=True, blank=True)
    volume_capacity = models.PositiveIntegerField(null=True, blank=True)
    interval_taho = models.PositiveIntegerField(null=True, blank=True)
    last_date_unload_taho = models.DateField(null=True, blank=True)

    comment = models.CharField(
        max_length=500, blank=True, null=True)

    has_dgr = models.BooleanField(default=False)
    has_sanitary_certificate = models.BooleanField(default=False)
    has_l_paket = models.BooleanField(default=False)

    is_available = models.BooleanField(default=False)
    is_rented = models.BooleanField(default=False)
    is_service_vehicle = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Company Vehicle"
        verbose_name_plural = "Company Vehicles"
        ordering = ['reg_number']
        constraints = [
            models.UniqueConstraint(fields=[
                                    'company', "reg_number"], name='unique_together company reg_number')
        ]

    def save(self, *args, **kwargs):

        try:
            super(CompanyVehicle, self).save(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f'ERRORLOG951 class CompanyVehicle. save. Error: {e}')
            raise YourCustomApiExceptionName(409, 'unique_together')

    def __str__(self):
        return self.reg_number or ''


class TargetGroup(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_target_groups')

    group_name = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True, null=True)

    def __int__(self):
        return self.id or ''


class ContactManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Contact(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_contacts')

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
    is_vat_on_receipt = models.BooleanField(default=False)

    contact_type = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), default=get_contact_type_default, size=5)

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
            raise YourCustomApiExceptionName(409, 'unique_together')

    def natural_key(self):
        return (self.company_name)

    def __str__(self):
        return self.company_name or str(self.id) or ''


class ContactSite(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, related_name="contact_sites")

    name_site = models.CharField(max_length=255)
    address_site = models.CharField(max_length=255)
    city_site = models.CharField(max_length=100, blank=True, null=True)
    country_code_site = models.ForeignKey(
        Country, on_delete=models.SET_NULL, related_name='country_code_sites', null=True, blank=True)

    def __str__(self):
        return f"{self.name_site} – {self.contact.company_name}"


class Person(ProtectedDeleteMixin, models.Model):
    '''
    Person to be used as contact person or driver at ContactSite
    '''
    protected_related = ["routesheet_set"]

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    site = models.ForeignKey(
        ContactSite, on_delete=models.CASCADE, related_name="site_persons")

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=30, blank=True, null=True)
    mobile = models.CharField(max_length=30, blank=True, null=True)
    comment = models.CharField(max_length=250, blank=True, null=True)

    is_driver = models.BooleanField(default=False, null=True, blank=True)
    archived = models.BooleanField(default=False)

    target_group = models.ManyToManyField(
        TargetGroup, related_name="target_group_persons")

    def __str__(self):
        return (self.first_name + ' ' + (self.last_name or '')) or ''


class VehicleUnit(ProtectedDeleteMixin, models.Model):
    protected_related = ["vehicle_tractor_route_sheets",
                         "vehicle_tractor_route_sheets"]

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
            raise YourCustomApiExceptionName(409, 'unique_together')

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
    bank_name = models.CharField(max_length=150)
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


class PaymentTerm(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_payment_terms')
    payment_term_short = models.CharField(
        max_length=100, blank=True, null=True)
    payment_term_description = models.CharField(
        max_length=1000, blank=True, null=True)

    class Meta:
        verbose_name = "Payment Term"
        verbose_name_plural = "Payment Terms"

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
        CompanyVehicle, on_delete=models.CASCADE, null=True,
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
            raise YourCustomApiExceptionName(409, 'unique_together')

    def __str__(self):
        return f"{self.company.company_name} - {self.series or 'N/A'} {self.number}"
