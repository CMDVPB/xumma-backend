from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField

from abb.constants import LOAD_SIZE, DOC_LANG_CHOICES
from abb.models import Currency, BodyType, ModeType, StatusType, Incoterm
from abb.utils import hex_uuid, assign_new_num, tripLoadsTotals
from app.models import Company
from att.models import Contact, Person, VehicleUnit, PaymentTerm

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class Trip(models.Model):
    ''' Trip model '''
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_trips')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_trips')

    rn = models.CharField(max_length=12, null=True, blank=True)
    date_created = models.DateTimeField(
        auto_now_add=True, null=True, blank=True)
    date_order = models.DateTimeField(blank=True, null=True)
    load_size = models.CharField(
        choices=LOAD_SIZE, max_length=20, null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    incl_loads_costs = models.BooleanField(default=False)
    doc_lang = models.CharField(choices=DOC_LANG_CHOICES,
                                max_length=2, blank=True, null=True, default='en')

    trip_number = models.CharField(max_length=20, blank=True, null=True)
    km_departure = models.CharField(max_length=20, blank=True, null=True)
    km_arrival = models.CharField(max_length=20, blank=True, null=True)
    date_trip = models.DateTimeField(blank=True, null=True)
    date_departure = models.DateTimeField(blank=True, null=True)
    date_arrival = models.DateTimeField(blank=True, null=True)
    trip_details = models.CharField(max_length=100, blank=True, null=True)

    l_departure = models.CharField(max_length=20, blank=True, null=True)
    l_arrival = models.CharField(max_length=20, blank=True, null=True)
    trip_add_info = models.CharField(max_length=100, blank=True, null=True)

    carrier = models.ForeignKey(Contact, on_delete=models.RESTRICT, null=True, blank=True,
                                related_name='carrier_trips')
    person = models.ForeignKey(Person, on_delete=models.SET_NULL,
                               blank=True, null=True, related_name='person_trips')
    driver = models.ForeignKey(Person, on_delete=models.SET_NULL,
                               blank=True, null=True, related_name='driver_trips')
    vehicle_tractor = models.ForeignKey(
        VehicleUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_tractor_trips')
    vehicle_trailer = models.ForeignKey(
        VehicleUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_trailer_trips')
    mode = models.ForeignKey(ModeType, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='modetype_trips')
    bt = models.ForeignKey(BodyType, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='bodytype_trips')
    currency = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, blank=True, null=True, related_name='currency_trips')
    status = models.ForeignKey(
        StatusType, on_delete=models.SET_NULL, blank=True, null=True, related_name='statustype_trips')

    load_order = ArrayField(ArrayField(models.CharField(
        max_length=36, null=True, blank=True), null=True, blank=True), null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.rn == None or self.rn == '':
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = Trip.objects.filter(
                    company__id=user_company.id).exclude(id=self.id)

                num_new = assign_new_num(items_list_qs, 'rn')

            except Exception as e:
                logger.error(f"ERRORLOG119 Trip. Error: {e}")
                pass

            self.rn = num_new if num_new else 1

        super(Trip, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Trip"
        verbose_name_plural = "Trips"

    @property
    def totals_trip(self):
        try:
            totals_trip = tripLoadsTotals(self)
            return totals_trip
        except Exception as e:
            logger.error(f"ERRORLOG123 Trip. Error: {e}")
            return [0, 0, 0, 0]

    @property
    def num_loads(self):
        try:
            num_loads = self.trip_loads.all().count()
            return num_loads
        except Exception as e:
            logger.error(f"ERRORLOG129 Trip. Error: {e}")

            return None

    def __str__(self):
        return str(self.rn) or ''


class Load(models.Model):
    ''' Load model '''
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_loads')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_loads')

    sn = models.CharField(max_length=12, blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_order = models.DateTimeField(blank=True, null=True)
    date_due = models.DateTimeField(blank=True, null=True)

    date_published = models.DateTimeField(blank=True, null=True)
    load_size = models.CharField(
        choices=LOAD_SIZE, max_length=20, null=True, blank=True)
    customer_ref = models.CharField(max_length=100,  blank=True, null=True)
    customer_notes = models.CharField(max_length=200, blank=True, null=True)
    load_add_ons = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), blank=True, null=True, size=3)
    doc_lang = models.CharField(choices=DOC_LANG_CHOICES,
                                max_length=2, blank=True, null=True, default='ro')
    is_locked = models.BooleanField(default=False)

    carrier = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, blank=True, null=True, related_name='carrier_loads')
    person_carrier = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='person_carrier_loads')
    driver = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='driver_loads')
    vehicle_tractor = models.ForeignKey(
        VehicleUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_tractor_loads')
    vehicle_trailer = models.ForeignKey(
        VehicleUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_trailer_loads')

    hb = models.CharField(max_length=30, blank=True, null=True)
    mb = models.CharField(max_length=30, blank=True, null=True)
    booking_number = models.CharField(max_length=30, blank=True, null=True)
    comment1 = models.CharField(max_length=200, blank=True, null=True)
    load_address = models.CharField(max_length=100, blank=True, null=True)
    unload_address = models.CharField(max_length=100, blank=True, null=True)
    load_detail = models.CharField(max_length=300, blank=True, null=True)

    mode = models.ForeignKey(ModeType, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='modetype_loads')
    bt = models.ForeignKey(BodyType, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='bodytype_loads')
    status = models.ForeignKey(StatusType, on_delete=models.SET_NULL,
                               blank=True, null=True, related_name='statustype_loads')
    incoterm = models.ForeignKey(Incoterm, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='incoterm_loads')
    currency = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, blank=True, null=True, related_name='currency_loads')
    payment_term = models.ForeignKey(
        PaymentTerm, on_delete=models.SET_NULL, blank=True, null=True, related_name='payment_term_loads')

    bill_to = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, blank=True, null=True, related_name='bill_to_loads')
    person = models.ForeignKey(Person, on_delete=models.SET_NULL,
                               blank=True, null=True, related_name='person_loads')
    trip = models.ForeignKey(Trip, on_delete=models.SET_NULL,
                             blank=True, null=True, related_name='trip_loads')

    def save(self, *args, **kwargs):
        if self.sn == None or self.sn == '':
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = Load.objects.select_related('company').filter(
                    company__id=user_company.id).exclude(id=self.id)

                num_new = assign_new_num(items_list_qs, 'sn')

            except Exception as e:
                logger.error(f"ERRORLOG163 Load. Error: {e}")
                pass

            self.sn = num_new if num_new else 1

        super(Load, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Load"
        verbose_name_plural = "Loads"

    def __str__(self):
        return str(self.sn) or ''
