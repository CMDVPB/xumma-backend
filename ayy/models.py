from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from phonenumber_field.modelfields import PhoneNumberField

from abb.constants import ACTION_CHOICES, UNIT_MEASUREMENT_CHOICES, VAT_CHOICES, VAT_EXEMPTION_REASON, VAT_TYPE_CHOICES
from abb.models import Country, Currency
from abb.utils import assign_new_num, hex_uuid, default_notification_status_3, upload_to

from app.models import Company
from axx.models import Ctr, Exp, Inv, Load, Tor, Trip
from att.models import Contact, Person, VehicleCompany

from .utils import dynamic_upload_path, user_photo_upload_path

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class PhoneNumber(models.Model):
    ''' Phone number '''
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    number = PhoneNumberField(region=None)  # stores in E.164 format
    is_primary = models.BooleanField(default=False)
    notes = models.CharField(max_length=255, blank=True)

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

        return f"{self.number} ({self.type}) – {owner}"


class DocumentType(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_document_types')
    contact = models.ForeignKey(
        Contact, on_delete=models.CASCADE, null=True, blank=True, related_name='contact_document_types')

    document_name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, null=True, blank=True)
    description = models.TextField(blank=True, null=True)

    is_for_vehicle = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Document Type"
        verbose_name_plural = "Document Types"

    def __str__(self):
        return self.document_name


class Document(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    doc_num = models.CharField(max_length=100, blank=True, null=True)
    date_doc = models.DateTimeField(blank=True, null=True)
    date_exp = models.DateTimeField()
    doc_det = models.CharField(max_length=500, blank=True, null=True)
    doc_type = models.ForeignKey(
        DocumentType, on_delete=models.CASCADE, blank=True, null=True, related_name='doc_type_documents')

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, blank=True, null=True, related_name='user_documents')

    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, blank=True, null=True, related_name='person_documents')

    company_vehicle = models.ForeignKey(
        VehicleCompany, on_delete=models.CASCADE, blank=True, null=True, related_name='company_vehicle_documents')

    notifications = ArrayField(models.BooleanField(
    ), default=default_notification_status_3, size=3)

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
    uf = models.CharField(max_length=36, default=hex_uuid)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_imageuploads')
    unique_field = models.UUIDField(
        default=hex_uuid, editable=False)
    file_name = models.CharField(
        max_length=500, blank=True, null=True)
    file_obj = models.FileField(blank=True, null=True, upload_to='uploads/')
    file_size = models.PositiveIntegerField(blank=True, null=True)

    load = models.ForeignKey(
        Load, on_delete=models.CASCADE, null=True, blank=True, related_name='load_imageuploads')

    def save(self, *args, **kwargs):

        if self.file_obj:
            # print('M676', )
            if self.company:
                company_short_uf = self.company.uf[0: 5]

                print('M678', company_short_uf)

                file_name_split = (self.file_obj.name).rsplit(
                    '.', 1)
                self.file_obj.name = company_short_uf + '_' + \
                    file_name_split[0] + '.'+file_name_split[1]
                self.file_name = file_name_split[0]

            self.file_size = int(self.file_obj.size)
            self.file_name = self.file_obj.name

            super(ImageUpload, self).save(*args, **kwargs)

    @property
    def s3_url(self):
        return self.file_obj.url

    def __str__(self):
        return str(self.file_obj) or ''


class FileUpload(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid)
    created_at = models.DateTimeField(auto_now_add=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_fileuploads')
    inv = models.ForeignKey(Inv, on_delete=models.CASCADE,
                            blank=True, null=True, related_name='inv_fileuploads')

    file_obj = models.FileField(
        blank=True, null=True, upload_to=dynamic_upload_path)
    file_size = models.PositiveIntegerField(blank=True, null=True)
    file_name = models.CharField(max_length=1000, blank=True, null=True)

    def save(self, *args, **kwargs):
        if self.file_obj:
            self.file_size = int(self.file_obj.size)

        super(FileUpload, self).save(*args, **kwargs)

    @property
    def s3_url(self):
        return self.file_obj.url if self.file_obj else None

    def __str__(self):
        return str(self.file_name or self.id or 'File name')


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
        VehicleCompany, on_delete=models.RESTRICT, blank=True, null=True, related_name='vehicle_tractor_route_sheets')
    vehicle_trailer = models.ForeignKey(
        VehicleCompany, on_delete=models.RESTRICT, blank=True, null=True, related_name='vehicle_trailer_route_sheets')
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
    contact = models.ForeignKey(
        Contact, on_delete=models.SET_NULL, blank=True, null=True, related_name='contact_entries')
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
    archived = models.BooleanField(default=False)

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
    is_fuel = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Item for itemcost"
        verbose_name_plural = "Items for itemcost"

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
    quantity = models.FloatField(null=True, blank=True)
    amount = models.FloatField(null=True, blank=True)
    vat = models.PositiveIntegerField(null=True, blank=True)
    discount = models.CharField(max_length=10, null=True, blank=True)

    item_for_item_cost = models.ForeignKey(
        ItemForItemCost, on_delete=models.RESTRICT, null=True, blank=True, related_name='item_for_item_cost_itemcosts')
    currency = models.ForeignKey(
        Currency, on_delete=models.RESTRICT, null=True, blank=True, related_name='currency_itemcosts')

    route_sheet = models.ForeignKey(
        RouteSheet, on_delete=models.CASCADE, null=True, blank=True, related_name='route_sheet_itemcosts')

    class Meta:
        verbose_name = "Item cost"
        verbose_name_plural = "Items cost"

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
