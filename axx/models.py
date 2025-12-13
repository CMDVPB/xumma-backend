from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from abb.constants import DOCUMENT_TYPES, LOAD_SIZE, DOC_LANG_CHOICES
from abb.custom_exceptions import YourCustomApiExceptionName
from abb.models import Currency, BodyType, ModeType, StatusType, Incoterm
from abb.utils import assign_new_num_inv, hex_uuid, assign_new_num, tripLoadsTotals
from app.models import Company
from att.models import Contact, Person, Term, VehicleUnit, PaymentTerm

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class Series(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_series')
    user = models.ManyToManyField(User)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    prefix = models.CharField(max_length=10)
    description = models.CharField(max_length=100, blank=True, null=True)
    start_number = models.PositiveIntegerField(default=1)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    is_default = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Series"
        verbose_name_plural = "Series"
        constraints = [
            models.UniqueConstraint(fields=[
                                    'company', 'prefix', 'document_type'], name='unique_constraint company-prefix-document_type')
        ]

    def clean(self):
        """
        Ensure that a user cannot have multiple default series for the same document type.
        """
        if self.is_default:
            for user in self.user.all():
                existing_defaults = Series.objects.filter(
                    user=user,
                    document_type=self.document_type,
                    is_default=True
                ).exclude(id=self.id)  # Exclude self to allow updates

                if existing_defaults.exists():
                    raise ValidationError(
                        f"User {user} already has a default series for {self.document_type}")

    def save(self, *args, **kwargs):
        try:
            super(Series, self).save(*args, **kwargs)
        except IntegrityError as e:
            raise YourCustomApiExceptionName(409, 'unique_together')

    def __str__(self):
        return f"{self.document_type}-{self.prefix}"


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
    load_stages = ArrayField(models.CharField(
        max_length=20), blank=True, null=True, size=3)
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


class Tor(models.Model):
    ''' Carrier transport order '''
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_tors')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_tors',)
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    tn = models.CharField(max_length=12, null=True, blank=True)
    doc_number = models.CharField(max_length=50,
                                  blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_order = models.DateTimeField(blank=True, null=True)

    tor_details = models.CharField(
        max_length=300, blank=True, null=True)
    rate = models.CharField(
        max_length=20, blank=True, null=True)
    is_tor = models.BooleanField(
        blank=True, null=True, default=True)
    load_size = models.CharField(
        choices=LOAD_SIZE, max_length=20, null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    load_add_ons = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), blank=True, null=True, size=3)
    doc_lang = models.CharField(choices=DOC_LANG_CHOICES,
                                max_length=2, blank=True, null=True, default='en')

    bt = models.ForeignKey(BodyType, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='bt_tors')
    currency = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, blank=True, null=True, related_name='currency_tors',)
    mode = models.ForeignKey(ModeType, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='mode_tors')
    incoterm = models.ForeignKey(
        Incoterm, on_delete=models.SET_NULL, blank=True, null=True, related_name='incoterm_tors')
    status = models.ForeignKey(
        StatusType, on_delete=models.SET_NULL, blank=True, null=True, related_name='status_tors')
    carrier = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, blank=True, null=True, related_name='carrier_tors',)
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='person_tors',)
    driver = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='driver_tors',)
    vehicle_tractor = models.ForeignKey(
        VehicleUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_tractor_tors',)
    vehicle_trailer = models.ForeignKey(
        VehicleUnit, on_delete=models.SET_NULL, blank=True, null=True, related_name='vehicle_trailer_tors',)
    load = models.ForeignKey(
        Load, on_delete=models.SET_NULL, blank=True, null=True, related_name='load_tors')
    payment_term = models.ForeignKey(PaymentTerm, on_delete=models.SET_NULL,
                                     blank=True, null=True, related_name='payment_term_tors',)
    contract_terms = models.ForeignKey(Term, on_delete=models.SET_NULL,
                                       blank=True, null=True, related_name='contract_terms_tors',)

    def save(self, *args, **kwargs):
        # if self.assigned_user == None or self.assigned_user == '':
        #     self.assigned_user = self.owner

        if self.is_tor == False:
            self.tn = None
            # print("0122", self.vn)

        if self.is_tor == True and (self.tn == None or self.tn == ''):
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = Tor.objects.select_related('company').filter(
                    company__id=user_company.id).exclude(id=self.id)

                num_new = assign_new_num(items_list_qs, 'tn')
                # print('7272')
            except:
                print('EM373')
                pass

            self.tn = num_new if num_new else 1

        super(Tor, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Tor"
        verbose_name_plural = "Tors"

    def __str__(self):
        return str(self.tn) or str(self.id) or ''


class Ctr(models.Model):
    ''' Customer transport order '''
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_ctrs')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_ctrs',)
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    cn = models.CharField(max_length=12, null=True, blank=True)

    date_order = models.DateTimeField(blank=True, null=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    rate = models.CharField(max_length=20, blank=True, null=True)
    load_size = models.CharField(
        choices=LOAD_SIZE, max_length=20, null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    customer_ref = models.CharField(max_length=100,  blank=True, null=True)
    customer_notes = models.CharField(max_length=200, blank=True, null=True)
    doc_lang = models.CharField(choices=DOC_LANG_CHOICES,
                                max_length=2, blank=True, null=True, default='en')

    mode = models.ForeignKey(ModeType, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='mtype_ctrs')
    bt = models.ForeignKey(BodyType, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='bt_ctrs')
    incoterm = models.ForeignKey(
        Incoterm, on_delete=models.SET_NULL, blank=True, null=True, related_name='itype_ctrs')
    load_add_ons = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), blank=True, null=True, size=3)

    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='currency_ctrs',)
    bill_to = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, blank=True, null=True, related_name='contact_ctrs',)
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='person_ctrs',)
    load = models.ForeignKey(
        Load, on_delete=models.SET_NULL, blank=True, null=True, related_name='load_ctrs')
    payment_term = models.ForeignKey(PaymentTerm, on_delete=models.SET_NULL,
                                     blank=True, null=True, related_name='payment_term_ctrs')
    status = models.ForeignKey(
        StatusType, on_delete=models.SET_NULL, blank=True, null=True, related_name='status_ctrs')
    contract_terms = models.ForeignKey(Term, on_delete=models.SET_NULL,
                                       blank=True, null=True, related_name='contract_terms_ctrs')

    def save(self, *args, **kwargs):
        # if self.assigned_user == None or self.assigned_user == '':
        #     self.assigned_user = self.owner

        if self.cn == None or self.cn == '':
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = Ctr.objects.filter(
                    company__id=user_company.id).exclude(id=self.id)
                num_new = assign_new_num(items_list_qs, 'cn')

            except:
                print('EM359')
                pass

            self.cn = num_new if num_new else 1

        super(Ctr, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Ctr"
        verbose_name_plural = "Ctrs"

    def __str__(self):
        return str(self.id) or ''


class Inv(models.Model):
    ''' invoice & quote model '''

    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_invs')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_invs',)

    qn = models.CharField(max_length=12, null=True, blank=True)
    vn = models.CharField(max_length=12, null=True, blank=True)
    series = models.ForeignKey(
        Series, on_delete=models.PROTECT, null=True, blank=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_inv = models.DateTimeField(blank=True, null=True)
    date_due = models.DateTimeField(blank=True, null=True)
    an = models.CharField(max_length=12, null=True, blank=True)
    date_act = models.DateTimeField(blank=True, null=True)
    load_detail = models.CharField(max_length=300, blank=True, null=True)
    load_address = models.CharField(max_length=100, blank=True, null=True)
    unload_address = models.CharField(max_length=100, blank=True, null=True)
    date_load = models.DateTimeField(blank=True, null=True)
    date_unload = models.DateTimeField(blank=True, null=True)
    load_size = models.CharField(
        choices=LOAD_SIZE, max_length=20, null=True, blank=True)
    is_locked = models.BooleanField(default=False)
    load_add_ons = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), blank=True, null=True, size=3)
    doc_lang = models.CharField(choices=DOC_LANG_CHOICES,
                                max_length=2, blank=True, null=True, default='en')

    customer_ref = models.CharField(max_length=100,  blank=True, null=True)
    customer_notes = models.CharField(max_length=200, blank=True, null=True)
    note_act = models.CharField(max_length=1000, blank=True, null=True)
    is_quote = models.BooleanField(blank=True, null=True, default=False)

    exported = models.BooleanField(default=False)
    exported_at = models.DateTimeField(blank=True, null=True)

    bill_to = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, null=True, blank=True, related_name='bill_to_invs',)
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='person_invs',)
    currency = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, null=True, related_name='currency_invs',)
    mode = models.ForeignKey(
        ModeType, on_delete=models.SET_NULL, blank=True, null=True, related_name='mode_inv')
    bt = models.ForeignKey(BodyType, on_delete=models.SET_NULL,
                           null=True, blank=True, related_name='bt_invs')
    incoterm = models.ForeignKey(
        Incoterm, on_delete=models.SET_NULL, blank=True, null=True, related_name='incoterm_invs')
    payment_term = models.ForeignKey(PaymentTerm, on_delete=models.SET_NULL,
                                     blank=True, null=True, related_name='payment_term_invs',)
    status = models.ForeignKey(
        StatusType, on_delete=models.SET_NULL, blank=True, null=True, related_name='status_invs')
    load = models.ForeignKey(
        Load, on_delete=models.SET_NULL, blank=True, null=True, related_name='load_invs',)
    contract_terms = models.ForeignKey(Term, on_delete=models.SET_NULL,
                                       blank=True, null=True, related_name='contract_terms_invs')

    internal_use_only = ArrayField(models.CharField(
        max_length=1000, null=True, blank=True), blank=True, null=True, size=10)

    def save(self, *args, **kwargs):

        # print('223344', )

        if self.is_quote == False and (self.vn == None or self.vn == ''):
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = Inv.objects.filter(
                    company__id=user_company.id, series=self.series, is_quote=False).exclude(id=self.id)

                # print('2321', )
                num_new = assign_new_num_inv(items_list_qs, 'vn')
            except Exception as e:
                logger.error(f'EM201 class Inv: {e}')
                pass

            self.vn = num_new if num_new else 1

        if self.is_quote == True and (self.qn == None or self.qn == ''):
            items_list_qs, num_new = None, None

            # print('223388', )

            try:
                user_company = self.company
                items_list_qs = Inv.objects.filter(
                    company__id=user_company.id, is_quote=True).exclude(id=self.id)

                num_new = assign_new_num(items_list_qs, 'qn')

            except Exception as e:
                logger.error(f'EM219 class Inv {e}')
                pass

            self.qn = num_new if num_new else 1

        super(Inv, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Inv"
        verbose_name_plural = "Invs"

    def __str__(self):
        return str(self.id) or ''


class Exp(models.Model):
    ''' expense model '''

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_exps')
    assigned_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_user_exps',)
    uf = models.CharField(max_length=36, default=hex_uuid,
                          unique=True, db_index=True)
    xn = models.CharField(max_length=12, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)
    date_record = models.DateTimeField(blank=True, null=True)

    doc_number = models.CharField(max_length=30, blank=True, null=True)
    date_issue = models.DateTimeField(blank=True, null=True)
    date_due = models.DateTimeField(blank=True, null=True)
    is_locked = models.BooleanField(default=False)
    doc_lang = models.CharField(choices=DOC_LANG_CHOICES,
                                max_length=2, blank=True, null=True, default='en')

    comment = models.CharField(max_length=300, blank=True, null=True)

    currency = models.ForeignKey(Currency, on_delete=models.SET_NULL,
                                 blank=True, null=True, related_name='currency_exps',)
    status = models.ForeignKey(
        StatusType, on_delete=models.SET_NULL, blank=True, null=True, related_name='status_exps')
    supplier = models.ForeignKey(
        Contact, on_delete=models.RESTRICT, blank=True, null=True, related_name='supplier_exps')
    person = models.ForeignKey(
        Person, on_delete=models.SET_NULL, blank=True, null=True, related_name='person_exps')
    load = models.ForeignKey(
        Load, on_delete=models.CASCADE, blank=True, null=True, related_name='load_exps')
    tor = models.ForeignKey(
        Tor, on_delete=models.CASCADE, blank=True, null=True, related_name='tor_exps')

    def save(self, *args, **kwargs):
        if (self.xn == None or self.xn == ''):
            items_list_qs, num_new = None, None

            try:
                user_company = self.company
                items_list_qs = Exp.objects.select_related('company').filter(
                    company__id=user_company.id).exclude(id=self.id)

                num_new = assign_new_num(items_list_qs, 'xn')

            except Exception as e:
                print('EM409', e)
                pass

            self.xn = num_new if num_new else 1

        super(Exp, self).save(*args, **kwargs)

    class Meta:
        verbose_name = "Exp"
        verbose_name_plural = "Exps"

    def __str__(self):
        return str(self.id) or ''
