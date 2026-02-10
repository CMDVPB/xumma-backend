from django.conf import settings
import os
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db.models import QuerySet, Prefetch, Q, F
from django.core.exceptions import ValidationError
from phonenumber_field.modelfields import PhoneNumberField

from abb.constants import ACTION_CHOICES, UNIT_MEASUREMENT_CHOICES, VAT_CHOICES, VAT_EXEMPTION_REASON, VAT_TYPE_CHOICES
from abb.models import Country, Currency
from abb.utils import assign_new_num, hex_uuid, default_notification_status_3, image_upload_path
from app.models import CategoryGeneral, Company, TypeCost, TypeGeneral
from axx.models import Ctr, Exp, Inv, Load, Tor, Trip
from att.models import Contact, ContactSite, Person, Vehicle

from .utils import user_photo_upload_path

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class ColliType(models.Model):
    ''' Type of collies: loose collies, euro pallets, industrial pallets, etc '''
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_colli_types', blank=True, null=True)

    serial_number = models.PositiveSmallIntegerField(
        null=True, blank=True, unique=True)
    code = models.CharField(max_length=10, blank=True)
    label = models.CharField(max_length=20, blank=True)

    description = models.CharField(max_length=12, blank=True)
    ldm = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Colli Type"
        verbose_name_plural = "Colli Types"
        unique_together = ('code', 'company')
        ordering = ['code']

    def __str__(self):
        return self.code


class PhoneNumber(models.Model):
    ''' Phone number '''
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    number = PhoneNumberField(region=None)  # stores in E.164 format
    notes = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)

    # Linked to either a User OR Contact OR Person
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             null=True, blank=True, related_name="user_phone_numbers")

    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True, related_name="contact_phone_numbers")

    person = models.ForeignKey(Person, on_delete=models.CASCADE,
                               null=True, blank=True, related_name="person_phone_numbers")

    class Meta:
        verbose_name = "Phone number"
        verbose_name_plural = "Phone numbers"

    def __str__(self):
        if self.person:
            owner = self.person.first_name
        elif self.contact:
            owner = self.contact.company_name
        else:
            owner = "Unassigned"

        return f"{self.number} – {owner}"


class DocumentType(models.Model):
    TARGET_CHOICES = [
        ('user', 'User'),
        ('vehicle', 'Vehicle'),
    ]

    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_document_types')

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    expiry_alert_days = models.PositiveIntegerField(
        default=0,
        help_text="Number of days before expiry to send alerts. 0 = no alerts."
    )

    is_active = models.BooleanField(default=True)

    order = models.PositiveIntegerField(default=0)

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_by_document_types'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    is_system = models.BooleanField(default=False)

    target = models.CharField(
        max_length=20,
        choices=TARGET_CHOICES,
        default='vehicle'
    )

    class Meta:
        verbose_name = "Document Type"
        verbose_name_plural = "Document Types"

    def __str__(self):
        return self.name


class UserDocument(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    document_number = models.CharField(max_length=100, blank=True, null=True)
    date_issued = models.DateTimeField(blank=True, null=True)
    date_expiry = models.DateTimeField()
    notes = models.TextField(max_length=500, blank=True, null=True)

    document_type = models.ForeignKey(
        DocumentType, on_delete=models.CASCADE, blank=True, null=True, related_name='document_type_user_documents')

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True, related_name='user_documents')

    notifications = ArrayField(models.BooleanField(
    ), default=default_notification_status_3, size=3)

    file = models.FileField(upload_to=image_upload_path, null=True, blank=True)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        if self.document_type and self.document_type.target != 'user':
            raise ValidationError({
                'document_type': 'This document type is not allowed for user documents.'
            })

    def check_exp_date_less_than_time(self, time, notifications_arr_index):
        try:
            if self.date_exp and time > self.date_exp and self.notifications[notifications_arr_index] == False:
                return True
            return False
        except Exception as e:
            logger.error(
                f"ERRORLOG673 Document. check_exp_date_less_than_time. Error: {e}")
            return False


class UserPhoto(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='user_photo')
    file = models.ImageField(blank=True, null=True,
                             upload_to=user_photo_upload_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    @property
    def url(self):
        """
        Returns the URL to access the photo locally.
        """
        if self.file:
            return self.file.url
        return ""

    def __str__(self):
        return f"Photo of {self.user.username}"


class ImageUpload(models.Model):
    SOURCE_CHOICES = (
        ('upload', 'User upload'),
        ('generated', 'System generated'),
    )

    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('final', 'Final'),
    )

    uf = models.CharField(max_length=36, default=hex_uuid)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_imageuploads')

    file_name = models.CharField(
        max_length=500, blank=True, null=True)
    file_obj = models.FileField(upload_to=image_upload_path)
    file_size = models.PositiveIntegerField(blank=True, null=True)

    load = models.ForeignKey(
        Load, on_delete=models.CASCADE, null=True, blank=True, related_name='load_imageuploads')
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='user_imageuploads')
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, null=True, blank=True, related_name='vehicle_imageuploads')
    damage = models.ForeignKey(
        'DamageReport', on_delete=models.CASCADE, null=True, blank=True, related_name='damage_imageuploads')

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    document_type = models.CharField(
        max_length=50,
        choices=(
            ('invoice', 'Invoice'),
            ('order', 'Order'),
            ('act', 'Act of execution'),
        ),
        null=True,
        blank=True
    )

    def clean(self):
        relations = [self.load, self.vehicle, self.user]
        if sum(bool(r) for r in relations) != 1:
            raise ValidationError(
                'Exactly one relation (load, vehicle, user, damage) must be set.'
            )

    def save(self, *args, **kwargs):
        if self.file_obj:
            self.file_size = self.file_obj.size
            self.file_name = os.path.basename(self.file_obj.name)

        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.file_obj) or ''


class ImageZipToken(models.Model):
    token = models.CharField(
        max_length=36,
        default=hex_uuid,
        unique=True,
        db_index=True
    )
    image_ufs = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(
            seconds=settings.SIGNED_URL_TTL_SECONDS
        )


class RouteSheet(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_route_sheets')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_route_sheets')

    is_locked = models.BooleanField(default=False)

    rs_number = models.CharField(max_length=50, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_issue = models.DateTimeField()
    date_departure = models.DateTimeField(null=True, blank=True)
    date_arrival = models.DateTimeField(null=True, blank=True)

    km_departure = models.FloatField(null=True, blank=True)
    km_arrival = models.FloatField(null=True, blank=True)
    fuel_start = models.FloatField(null=True, blank=True)
    fuel_end = models.FloatField(null=True, blank=True)
    notes_date = models.CharField(max_length=100, null=True, blank=True)
    notes_km = models.CharField(max_length=100, null=True, blank=True)
    notes_fuel = models.CharField(max_length=100, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    stops = models.JSONField(null=True, blank=True)

    trip = models.ForeignKey(
        Trip, on_delete=models.RESTRICT, null=True, blank=True, related_name="trip_route_sheets")
    start_location = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, null=True, blank=True, related_name="starting_route_sheets")
    end_location = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, null=True, blank=True, related_name="ending_route_sheets")
    vehicle_tractor = models.ForeignKey(
        Vehicle, on_delete=models.RESTRICT, blank=True, null=True, related_name='vehicle_tractor_route_sheets')
    vehicle_trailer = models.ForeignKey(
        Vehicle, on_delete=models.RESTRICT, blank=True, null=True, related_name='vehicle_trailer_route_sheets')
    currency = models.ForeignKey(
        Currency, on_delete=models.RESTRICT, null=True, blank=True, related_name='currency_route_sheets')

    drivers = models.ManyToManyField(
        User, through="RouteSheetDriver", related_name="route_sheets",  blank=True)

    def save(self, *args, **kwargs):
        if self.rs_number == None or self.rs_number == '':
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = RouteSheet.objects.select_related('company').filter(
                    company__id=user_company.id).exclude(id=self.id)

                num_new = assign_new_num(items_list_qs, 'rs_number')

            except Exception as e:
                logger.error(f"EM454 RouteSheet def save. Error: {e}")
                pass

            self.rs_number = num_new if num_new else 1

        super(RouteSheet, self).save(*args, **kwargs)


class RouteSheetDriver(models.Model):
    route_sheet = models.ForeignKey(
        RouteSheet,
        on_delete=models.SET_NULL,
        related_name="driver_links",
        null=True
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.RESTRICT,
        related_name="route_sheet_links"
    )

    class Meta:
        unique_together = ("route_sheet", "driver")
        verbose_name = "Route sheet driver"
        verbose_name_plural = "Route sheet drivers"

    def __str__(self):
        return f"{self.driver} → RouteSheet #{self.route_sheet_id}"


class Entry(models.Model):
    ''' entry '''
    uf = models.CharField(max_length=36, default=hex_uuid)
    action = models.CharField(
        choices=ACTION_CHOICES, max_length=20, null=True, blank=True)
    shipper = models.ForeignKey(
        ContactSite, on_delete=models.SET_NULL, blank=True, null=True, related_name='shipper_entries')
    date_load = models.DateTimeField(null=True, blank=True)

    time_load_min = models.DateTimeField(null=True, blank=True)
    time_load_max = models.DateTimeField(null=True, blank=True)

    zip_load = models.CharField(max_length=20, blank=True, null=True)
    country_load = models.ForeignKey(
        Country, on_delete=models.SET_NULL, blank=True, null=True, related_name='country_load_entries')
    city_load = models.CharField(max_length=50, blank=True, null=True)
    shipperinstructions1 = models.CharField(
        max_length=250, blank=True, null=True)
    shipperinstructions2 = models.CharField(
        max_length=250, blank=True, null=True)

    is_stackable = models.BooleanField(default=False)
    palletexchange = models.BooleanField(blank=True, null=True, default=False)
    tail_lift = models.BooleanField(blank=True, null=True, default=False)
    dangerousgoods = models.BooleanField(blank=True, null=True, default=False)
    dangerousgoods_class = models.CharField(
        max_length=30, blank=True, null=True)
    temp_control = models.BooleanField(blank=True, null=True, default=False)
    temp_control_details = models.CharField(
        max_length=40, blank=True, null=True)

    load = models.ForeignKey(
        Load, on_delete=models.CASCADE, blank=True, null=True, related_name='entry_loads')
    tor = models.ForeignKey(
        Tor,  on_delete=models.CASCADE, blank=True, null=True, related_name='entry_tors')
    ctr = models.ForeignKey(
        Ctr, on_delete=models.CASCADE, blank=True, null=True,  related_name='entry_ctrs')
    inv = models.ForeignKey(
        Inv, on_delete=models.CASCADE, blank=True, null=True, related_name='entry_invs')

    order = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        verbose_name = "Entry"
        verbose_name_plural = "Entries"

    def __str__(self):
        return str(self.id) or ''


class Detail(models.Model):
    ''' sales Order '''
    uf = models.CharField(max_length=36, default=hex_uuid)
    pieces = models.CharField(max_length=10, null=True, blank=True)
    weight = models.CharField(max_length=10, null=True, blank=True)
    ldm = models.CharField(max_length=10, null=True, blank=True)
    volume = models.CharField(max_length=10, null=True, blank=True)
    dims = models.CharField(max_length=150, blank=True, null=True)

    entry = models.ForeignKey(Entry, on_delete=models.CASCADE,
                              blank=True, null=True, related_name='entry_details')
    colli_type = models.ForeignKey(
        ColliType, on_delete=models.PROTECT, related_name='colli_type_details', blank=True, null=True)

    def __str__(self):
        return str(self.entry) or ''


class ItemForItemInv(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_item_for_item_invs')

    description = models.CharField(max_length=150)
    um = models.CharField(choices=UNIT_MEASUREMENT_CHOICES, default='pc',
                          max_length=20, null=True, blank=True)
    code = models.CharField(max_length=30, null=True, blank=True)
    vat = models.PositiveIntegerField(
        choices=VAT_CHOICES, default=0, null=True, blank=True)
    vat_type = models.CharField(
        choices=VAT_TYPE_CHOICES, default='zero', max_length=20, null=True, blank=True)
    exemption_reason = models.CharField(
        choices=VAT_EXEMPTION_REASON, max_length=20, null=True, blank=True)

    is_sale = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Item for iteminv"
        verbose_name_plural = "Items for iteminv"

    def save(self, *args, **kwargs):
        if self.vat_type == 'reverse_charge':
            self.exemption_reason = 'vatex-eu-ae'

        super(ItemForItemInv, self).save(*args, **kwargs)

    def __str__(self):
        return self.description or ''


class ItemForItemCost(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_item_for_item_costs')

    serial_number = models.PositiveSmallIntegerField(
        null=True, blank=True, unique=True)
    description = models.CharField(max_length=150)
    code = models.CharField(max_length=30, null=True, blank=True)
    vat = models.PositiveIntegerField(null=True, blank=True)

    is_card = models.BooleanField(default=False)
    is_fuel = models.BooleanField(default=False)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Item for itemcost"
        verbose_name_plural = "Items for itemcost"
        ordering = ['-is_system', 'serial_number', 'company', '-id']

    def __str__(self):
        return self.description or ''


class ItemInv(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)

    quantity = models.FloatField(null=True, blank=True)
    amount = models.FloatField(null=True, blank=True)
    vat = models.PositiveIntegerField(null=True, blank=True)
    discount = models.CharField(max_length=10, null=True, blank=True)

    item_for_item_inv = models.ForeignKey(
        ItemForItemInv, on_delete=models.RESTRICT, null=True, blank=True, related_name='item_for_item_inv_iteminvs')

    item_for_item_cost = models.ForeignKey(
        ItemForItemCost, on_delete=models.RESTRICT, null=True, blank=True, related_name='item_for_item_cost_iteminvs')

    currency = models.ForeignKey(
        Currency, on_delete=models.RESTRICT, null=True, blank=True, related_name='currency_iteminvs')

    load = models.ForeignKey(
        Load, on_delete=models.CASCADE, null=True, blank=True, related_name='load_iteminvs')
    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, null=True, blank=True, related_name='trip_iteminvs')
    tor = models.ForeignKey(
        Tor, on_delete=models.CASCADE, null=True, blank=True, related_name='tor_iteminvs')
    ctr = models.ForeignKey(
        Ctr, on_delete=models.CASCADE, null=True, blank=True, related_name='ctr_iteminvs')
    inv = models.ForeignKey(
        Inv, on_delete=models.CASCADE, null=True, blank=True, related_name='iteminv_invs')
    exp = models.ForeignKey(
        Exp, on_delete=models.CASCADE, null=True, blank=True, related_name='exp_iteminvs')

    class Meta:
        verbose_name = "Item inv"
        verbose_name_plural = "Items inv"

    def __str__(self):
        return str(self.id) or ''


class ItemCost(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_itemcosts')

    date = models.DateTimeField(null=True, blank=True)
    type = models.ForeignKey(
        TypeCost, on_delete=models.RESTRICT, null=True, blank=True, related_name='type_itemscosts')
    country = models.ForeignKey(
        Country, on_delete=models.RESTRICT, null=True, blank=True, related_name='country_itemscosts')
    quantity = models.FloatField(null=True, blank=True)
    amount = models.FloatField(null=True, blank=True)
    vat = models.PositiveIntegerField(null=True, blank=True)
    discount = models.CharField(max_length=10, null=True, blank=True)

    item_for_item_cost = models.ForeignKey(
        ItemForItemCost, on_delete=models.RESTRICT, null=True, blank=True, related_name='item_for_item_cost_itemcosts')
    currency = models.ForeignKey(
        Currency, on_delete=models.RESTRICT, null=True, blank=True, related_name='currency_itemcosts')
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_by_itemcosts')

    trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, null=True, blank=True, related_name='trip_itemcosts')

    class Meta:
        verbose_name = "Item cost"
        verbose_name_plural = "Items cost"

    @property
    def total(self):
        if self.quantity is None or self.amount is None:
            return None
        vat = self.vat or 0
        return round(self.quantity * self.amount * (1 + vat / 100), 2)

    def __str__(self):
        return str(self.id) or ''


class Comment(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)

    comment = models.CharField(max_length=400, blank=True, null=True)

    load = models.ForeignKey(Load, on_delete=models.CASCADE,
                             blank=True, null=True, related_name='load_comments')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE,
                             blank=True, null=True, related_name='trip_comments')
    tor = models.ForeignKey(Tor, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='tor_comments')
    ctr = models.ForeignKey(Ctr, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='ctr_comments')
    inv = models.ForeignKey(Inv, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='inv_comments')

    class Meta:
        verbose_name = "Comment"
        verbose_name_plural = "Comments"

    def __str__(self):
        return str(self.id) or ''


class CMR(models.Model):
    """CMR (Consignment Note) data related to a Load"""
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_cmrs')

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    date_issue = models.DateTimeField(null=True, blank=True)
    place_issue = models.CharField(max_length=200, blank=True, null=True)
    place_load = models.CharField(max_length=200, blank=True, null=True)
    place_unload = models.CharField(max_length=200, blank=True, null=True)

    number = models.CharField(max_length=50, blank=True, null=True)
    list_of_documents = models.CharField(max_length=200, blank=True, null=True)
    special_agreement = models.CharField(max_length=100, blank=True, null=True)
    payment = models.CharField(max_length=100, blank=True, null=True)
    cod = models.CharField(max_length=100, blank=True, null=True)
    cod_amount = models.CharField(max_length=100, blank=True, null=True)

    load = models.OneToOneField(
        Load, on_delete=models.CASCADE, related_name='cmr', null=True, blank=True)

    class Meta:
        verbose_name = "cmr"
        verbose_name_plural = "cmrs"
        ordering = ['-date_created']
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'number'], name='unique_company_cmr_number'
            )
        ]

    def __str__(self):
        return f"CMR #{self.number or self.id} for Load {self.load.id if self.load else 'No load'}"


class History(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE,
                                   blank=True, null=True, related_name='changed_by_histories')

    date_registered = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, blank=True, null=True)

    load = models.ForeignKey(Load, on_delete=models.CASCADE,
                             blank=True, null=True, related_name='load_histories')
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE,
                             blank=True, null=True, related_name='trip_histories')
    tor = models.ForeignKey(Tor, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='tor_histories')
    ctr = models.ForeignKey(Ctr, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='ctr_histories')
    inv = models.ForeignKey(Inv, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='inv_histories')
    exp = models.ForeignKey(Exp, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='exp_histories')

    class Meta:
        verbose_name = "History"
        verbose_name_plural = "Histories"
        ordering = ['-date_registered']

    def __str__(self):
        return str(self.id) or ''


###### START CMR Models ######

class CMRStockBatch(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_cmr_stock"
    )

    series = models.CharField(max_length=20, blank=True, null=True)

    number_from = models.PositiveIntegerField()
    number_to = models.PositiveIntegerField()

    received_at = models.DateField()

    total_count = models.PositiveIntegerField(editable=False)

    notes = models.TextField(max_length=1000, blank=True)

    class Meta:
        unique_together = ("company", "series", "number_from", "number_to")

    def save(self, *args, **kwargs):
        self.total_count = self.number_to - self.number_from + 1
        super().save(*args, **kwargs)

    @property
    def available_count(self):
        return self.total_count


class CMRHolder(models.Model):
    COMPANY = "COMPANY"
    CUSTOMER = "CUSTOMER"
    VEHICLE = "VEHICLE"

    HOLDER_TYPES = (
        (COMPANY, "Company"),
        (CUSTOMER, "Customer"),
        (VEHICLE, "Vehicle"),
    )

    holder_type = models.CharField(max_length=20, choices=HOLDER_TYPES)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True
    )
    customer = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True
    )
    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="cmrholder_exactly_one_fk",
                condition=(
                    # at least one
                    (
                        models.Q(company__isnull=False) |
                        models.Q(customer__isnull=False) |
                        models.Q(vehicle__isnull=False)
                    )
                    &
                    # no two at the same time
                    ~(
                        (models.Q(company__isnull=False) & models.Q(customer__isnull=False)) |
                        (models.Q(company__isnull=False) & models.Q(vehicle__isnull=False)) |
                        (models.Q(customer__isnull=False)
                         & models.Q(vehicle__isnull=False))
                    )
                ),
            )
        ]


class CMRStockMovement(models.Model):
    TRANSFER = "TRANSFER"
    CONSUMED = "CONSUMED"

    MOVEMENT_TYPES = (
        (TRANSFER, "Transfer"),
        (CONSUMED, "Consumed"),
    )

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)

    batch = models.ForeignKey(
        CMRStockBatch,
        on_delete=models.CASCADE,
        related_name="movements"
    )

    series = models.CharField(max_length=20, blank=True, null=True)
    number_from = models.PositiveIntegerField()
    number_to = models.PositiveIntegerField()

    quantity = models.PositiveIntegerField(editable=False)

    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)

    from_holder = models.ForeignKey(
        CMRHolder,
        on_delete=models.PROTECT,
        related_name="outgoing_movements",
        null=True,
        blank=True,
    )

    to_holder = models.ForeignKey(
        CMRHolder,
        on_delete=models.PROTECT,
        related_name="incoming_movements",
        null=True,
        blank=True,
    )

    # WHICH LOAD USED THE CMR
    load = models.ForeignKey(
        Load,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cmr_movements"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    notes = models.TextField(blank=True)

    def save(self, *args, **kwargs):
        self.quantity = self.number_to - self.number_from + 1
        super().save(*args, **kwargs)

###### END CMR Models ######


class AuthorizationStockBatch(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_authorizations_stock"
    )

    series = models.CharField(max_length=20, null=True, blank=True)
    number = models.CharField(max_length=20)
    received_at = models.DateField(null=True, blank=True)
    date_expire = models.DateField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(max_length=1000, blank=True)

    type_authorization = models.ForeignKey(TypeGeneral, on_delete=models.SET_NULL,
                                           null=True, blank=True, related_name='type_authorizations')
    category_authorization = models.ForeignKey(CategoryGeneral, on_delete=models.SET_NULL,
                                               null=True, blank=True, related_name='category_authorizations')
    vehicle_authorization = models.ForeignKey(Vehicle, on_delete=models.SET_NULL,
                                              null=True, blank=True, related_name='vehicle_authorizations')
    countries_authorization = models.ManyToManyField(
        Country, related_name="authorization_countries")

    class Meta:
        unique_together = ('type_authorization', "company",
                           "number", "category_authorization")


class CTIRStockBatch(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_ctir_stock"
    )

    series = models.CharField(max_length=20, null=True, blank=True)
    number = models.CharField(max_length=30)
    received_at = models.DateField()
    date_expire = models.DateField(null=True, blank=True)
    price = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(max_length=1000, blank=True)

    class Meta:
        unique_together = ("company", "number")


###### Start Damages Models ######

class DamageReport(models.Model):
    DAMAGE_REPORT_TYPE_CHOICES = (
        ('vehicle_damage', 'Vehicle'),
        ('goods_damage', 'Goods'),
    )
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_damage_reports")

    vehicle = models.ForeignKey(
        Vehicle, on_delete=models.CASCADE, related_name="vehicle_damage_reports", null=True, blank=True)

    damage_report_type = models.CharField(
        max_length=20, choices=DAMAGE_REPORT_TYPE_CHOICES, blank=True)

    reported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)

    driver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="driver_damage_reports", null=True, blank=True
    )

    reported_at = models.DateTimeField(auto_now_add=True)

    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    is_insured = models.BooleanField(default=False)

    insurance_deductible = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    route_sheet = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"Damage report #{self.id} for {self.vehicle}"


class VehicleDamage(models.Model):
    DAMAGE_TYPE_CHOICES = (
        ('scratch', 'Scratch'),
        ('dent', 'Dent'),
        ('crack', 'Crack'),
        ('broken', 'Broken'),
        ('missing', 'Missing'),
        ('other', 'Other'),
    )

    SEVERITY_CHOICES = (
        ('minor', 'Minor'),
        ('medium', 'Medium'),
        ('severe', 'Severe'),
    )

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_vehicle_damages")

    report = models.ForeignKey(
        DamageReport,
        on_delete=models.CASCADE,
        related_name="report_vehicle_damages"
    )

    damage_type = models.CharField(
        max_length=20, choices=DAMAGE_TYPE_CHOICES, blank=True)
    severity = models.CharField(
        max_length=20, choices=SEVERITY_CHOICES, blank=True)

    part = models.CharField(
        max_length=100, blank=True, null=True

    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2, blank=True, null=True
    )

    description = models.TextField(blank=True)

    is_repaired = models.BooleanField(default=False)
    repaired_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.damage_type} ({self.severity}) - {self.part}"


class DamageLiability(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_damage_liabilities"
    )

    report = models.ForeignKey(
        DamageReport,
        on_delete=models.CASCADE,
        related_name="report_damage_liabilities", null=True, blank=True
    )

    driver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="driver_damage_liabilities", null=True, blank=True
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        related_name="currency_damage_liabilities"
    )

    reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    is_settled = models.BooleanField(default=False)

    def __str__(self):
        return (
            f"{self.driver} owes {self.total_amount} "
            f"for report #{self.report.id}"
        )


class DamagePayment(models.Model):
    liability = models.ForeignKey(
        DamageLiability,
        on_delete=models.CASCADE,
        related_name="liability_damage_payments"
    )

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    paid_at = models.DateField()

    method = models.CharField(
        max_length=30,
        choices=(
            ('cash', 'Cash'),
            ('salary_deduction', 'Salary deduction'),
            ('bank_transfer', 'Bank transfer'),
        )
    )

    note = models.TextField(blank=True)

    def __str__(self):
        return f"{self.amount} paid on {self.paid_at}"


###### End Damages Models ######

class UserEmail(models.Model):
    STATUS_CHOICES = (
        ('queued', 'Queued'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_sent_emails')

    # Mailbox fields
    from_email = models.EmailField()
    to = models.JSONField()
    cc = models.JSONField(blank=True, null=True)
    bcc = models.JSONField(blank=True, null=True)

    subject = models.CharField(max_length=255)
    body = models.TextField()

    # UX flags (gmail-like)
    is_read = models.BooleanField(default=True)  # sent mail is read
    is_draft = models.BooleanField(default=False)

    # Delivery status
    status = models.CharField(
        max_length=10,  choices=STATUS_CHOICES, default='queued')

    error = models.TextField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(blank=True, null=True)

    # sent mails are read by default
    is_read = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.subject} → {self.to}"


class UserEmailAttachment(models.Model):
    email = models.ForeignKey(
        UserEmail, related_name="email_attachments", on_delete=models.CASCADE)
    file = models.FileField(upload_to="email_attachments/")
    filename = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class EmailTemplate(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_email_templates")

    code = models.CharField(max_length=100)  # e.g. "invoice_sent"
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name="created_by_email_templates")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("company", "code")


class EmailTemplateTranslation(models.Model):
    template = models.ForeignKey(
        EmailTemplate, on_delete=models.CASCADE, related_name="template_email_translations")
    language = models.CharField(max_length=2)  # "en", "ro", "ru"
    subject = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)  # HTML

    class Meta:
        unique_together = ("template", "language")


class EmailTemplateVariable(models.Model):
    template = models.ForeignKey(EmailTemplate, on_delete=models.CASCADE)
    key = models.CharField(max_length=50)  # invoice_number
    description = models.CharField(max_length=255)


class MailLabelV2(models.Model):
    SYSTEM = "system"
    CUSTOM = "custom"

    TYPE_CHOICES = [
        (SYSTEM, "System"),
        (CUSTOM, "Custom"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mail_labels_v2",
        null=True,
        blank=True,
    )

    slug = models.SlugField()
    name = models.CharField(max_length=50)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("user", "slug")
        ordering = ["order"]

    def __str__(self):
        return f"{self.slug}"


class MailMessage(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mailbox_messages",
    )

    # Optional link to sent email
    sent_email = models.OneToOneField(
        UserEmail,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mail_message",
    )

    from_email = models.EmailField()
    to = models.JSONField()

    subject = models.CharField(max_length=255)
    body = models.TextField()

    labels = models.ManyToManyField(
        MailLabelV2,
        related_name="messages",
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject


###### START CARDS ######

class CompanyCard(models.Model):
    BANK = "BANK"
    FUEL = "FUEL"
    TOLL = "TOLL"

    CARD_TYPES = (
        (BANK, "Bank card"),
        (FUEL, "Fuel card"),
        (TOLL, "Toll card"),
    )

    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_cards"
    )

    card_type = models.CharField(max_length=20, choices=CARD_TYPES)

    provider = models.CharField(max_length=100)  # Visa, Shell, BP, etc.
    card_number = models.CharField(max_length=50, unique=True)

    expires_at = models.DateField(null=True, blank=True)

    # current allocation (IMPORTANT)
    current_employee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_employee_cards"
    )

    current_vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_vehicle_cards"
    )

    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="card_only_one_current_holder",
                condition=(
                    # either driver OR vehicle OR none
                    ~(
                        models.Q(current_employee__isnull=False) &
                        models.Q(current_vehicle__isnull=False)
                    )
                ),
            )
        ]


class CardAssignment(models.Model):
    ASSIGN = "ASSIGN"
    UNASSIGN = "UNASSIGN"

    ACTIONS = (
        (ASSIGN, "Assign"),
        (UNASSIGN, "Unassign"),
    )

    card = models.ForeignKey(
        CompanyCard,
        on_delete=models.CASCADE,
        related_name="card_assignments"
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employee_assigned_cards"
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vehicle_assigned_cards"
    )

    action = models.CharField(max_length=20, choices=ACTIONS)

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="card_assignment_one_target",
                condition=(
                    ~(
                        models.Q(employee__isnull=False) &
                        models.Q(vehicle__isnull=False)
                    )
                ),
            )
        ]

    def clean(self):
        targets = [self.employee, self.vehicle]

        if self.action == self.ASSIGN and sum(t is not None for t in targets) != 1:
            raise ValidationError(
                "ASSIGN must target exactly one of employee or vehicle."
            )

###### END CARDS ######
