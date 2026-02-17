import os
import binascii
from django.db import models, IntegrityError
from django.conf import settings
from django.core.exceptions import ValidationError
from abb.custom_exceptions import CustomApiException
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from cryptography.fernet import Fernet

from abb.models import Country, Currency
from abb.utils import get_default_empty_strings_20, get_order_by_default, \
    hex_uuid, get_default_notification_status_3, image_upload_path, validate_columns_arrayfield_length_min_5
from abb.constants import BASE_COUNTRIES, BASE_COUNTRIES_LIST, APP_LANGS, DOC_LANG_CHOICES, MEMBERSHIP_CHOICES
from abb.validators import validate_columns_arrayfield_length_exactly_20

import logging
logger = logging.getLogger(__name__)


class UserAccountManager(BaseUserManager):
    def create_user(self, email, password=None, **kwargs):
        if not email:
            raise ValueError('Users must have an email address')

        email = self.normalize_email(email)
        email = email.lower()

        user = self.model(
            email=email,
            **kwargs
        )

        print('M240', kwargs)

        base_country = kwargs.get('base_country', 'md')
        if base_country not in BASE_COUNTRIES_LIST:
            base_country = 'ro'

        user_lang = kwargs.get('lang', 'ro')
        if user_lang not in APP_LANGS:
            user_lang = 'en'

        logger.info(
            f'AA002 User created. User: {email}, user lang: {user_lang}, user base country: {base_country}')

        user.set_password(password)
        user.username = email
        user.lang = user_lang
        user.base_country = base_country
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **kwargs):
        user = self.create_user(
            email,
            password=password,
            **kwargs
        )

        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)

        return user


class User(AbstractUser):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    email = models.EmailField(max_length=255, unique=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    date_registered = models.DateField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    date_termination = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=100, null=True, blank=True)
    personal_id = models.CharField(max_length=50, null=True, blank=True)
    messanger = models.CharField(max_length=100, null=True, blank=True)
    comment = models.CharField(max_length=500, null=True, blank=True)

    lang = models.CharField(max_length=2, blank=True, null=True)
    base_country = models.CharField(choices=BASE_COUNTRIES,
                                    blank=True, null=True, max_length=2)

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    is_archived = models.BooleanField(default=False)

    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_activity = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['first_name', 'last_name', 'lang', 'base_country']

    objects = UserAccountManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['-date_joined']

    def save(self, *args, **kwargs):
        super(User, self).save(*args, **kwargs)

    def get_full_name(self) -> str:
        """
        Returns 'First Last' if available,
        otherwise falls back to email.
        """
        first = (self.first_name or "").strip()
        last = (self.last_name or "").strip()

        full_name = f"{first} {last}".strip()

        return full_name if full_name else self.email

    def __str__(self):
        return self.email


class UserProfile(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='user_profile')

    position = models.CharField(max_length=100, blank=True,
                                )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    avatar = models.ImageField(
        upload_to=image_upload_path,
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user} profile'


class UserCompensationSettings(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="compensation_settings")

    has_per_km_income = models.BooleanField(default=False)
    paid_by_loading_points = models.BooleanField(default=False)
    paid_by_unloading_points = models.BooleanField(default=False)


class UserSettings(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, db_index=True)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='user_settings')
    theme = models.CharField(max_length=20, default='light')
    notifications_enabled = models.BooleanField(default=True)
    simplified_load = models.BooleanField(default=False)
    default_document_tab = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), default=get_default_empty_strings_20,
        size=20, validators=[validate_columns_arrayfield_length_exactly_20]
    )

    base_doc_lang = models.CharField(
        choices=DOC_LANG_CHOICES, max_length=2, blank=True, null=True)
    rows_per_page = models.PositiveSmallIntegerField(
        blank=True, null=True, default=15)
    myitems_all = models.CharField(
        max_length=10, blank=True, null=True, default='all')
    order_by = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), default=get_order_by_default, size=7)

    load_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    load_2_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    load_3_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    load_4_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    load_due_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    trip_loads_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    trip_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    tor_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    ctr_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    quote_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    inv_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])
    exp_columns = ArrayField(models.CharField(
        max_length=20, null=True, blank=True), null=True, blank=True, size=30, validators=[validate_columns_arrayfield_length_min_5])

    currency_default = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, blank=True, null=True, related_name='currency_default_user_settings')

    class Meta:
        verbose_name = "User Settings"
        verbose_name_plural = "User Settings"

    def __str__(self) -> str:
        return f"Settings for {self.user}"


class UserPermission(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="user_custom_permissions"
    )

    # LOAD PERMISSIONS
    can_view_loads = models.BooleanField(default=False)
    can_edit_loads = models.BooleanField(default=False)

    # # FINANCIAL PERMISSIONS
    can_view_financials = models.BooleanField(default=False)
    can_edit_financials = models.BooleanField(default=False)
    # can_manage_invoices = models.BooleanField(default=False)

    # DRIVER / CARRIER PERMISSIONS
    can_view_carriers = models.BooleanField(default=False)
    can_edit_carriers = models.BooleanField(default=False)
    # can_manage_drivers = models.BooleanField(default=False)

    # ADMIN-LEVEL
    can_manage_users = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)

    def __str__(self):
        return f"Permissions for {self.user.username}"


class CompanyManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Company(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    user = models.ManyToManyField(User)

    logo = models.CharField(max_length=36, blank=True, null=True)
    stamp = models.CharField(max_length=36, blank=True, null=True)
    company_name = models.CharField(max_length=150, null=True, blank=True)
    fiscal_code = models.CharField(max_length=20, blank=True, null=True)
    vat_code = models.CharField(max_length=20, blank=True, null=True)
    reg_com = models.CharField(max_length=20, blank=True, null=True)
    subscribed_capital = models.CharField(max_length=30, blank=True, null=True)

    country_code_legal = models.ForeignKey(
        Country, on_delete=models.SET_NULL, blank=True, null=True, related_name='companycountry1')
    zip_code_legal = models.CharField(max_length=20, blank=True, null=True)
    city_legal = models.CharField(max_length=50, blank=True, null=True)
    address_legal = models.CharField(max_length=120, blank=True, null=True)
    county_legal = models.CharField(max_length=10, blank=True, null=True)
    sect_legal = models.CharField(max_length=100, blank=True, null=True)

    country_code_post = models.ForeignKey(
        Country, on_delete=models.SET_NULL, blank=True, null=True, related_name='companycountry2')
    zip_code_post = models.CharField(max_length=20, blank=True, null=True)
    city_post = models.CharField(max_length=50, blank=True, null=True)
    address_post = models.CharField(max_length=120, blank=True, null=True)
    county_post = models.CharField(max_length=10, blank=True, null=True)

    email = models.EmailField(max_length=150, blank=True, null=True)
    phone = models.CharField(max_length=30, null=True, blank=True)
    messanger = models.CharField(max_length=30, null=True, blank=True)
    comment = models.CharField(max_length=500, null=True, blank=True)

    is_vat_payer = models.BooleanField(default=False)
    e_factura = models.BooleanField(default=False)

    objects = CompanyManager()

    def natural_key(self):
        return (self.company_name)

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.company_name or str(self.id) or ''


class CompanySettings(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="company_settings"
    )

    # # General
    currency = models.ForeignKey(
        Currency, on_delete=models.SET_NULL, blank=True, null=True, related_name='currency_company_settings')
    # language = models.CharField(max_length=5, default="en")

    # # Financial
    # vat_rate = models.DecimalField(
    #     max_digits=5,
    #     decimal_places=2,
    #     default=0
    # )

    # # System behavior
    # timezone = models.CharField(max_length=50, default="Europe/Berlin")

    updated_at = models.DateTimeField(auto_now=True)


class Team(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='company_teams')
    leader = models.OneToOneField(User, on_delete=models.CASCADE)
    team_name = models.CharField(max_length=100)


class Warehouse(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_warehouses")

    name_warehouse = models.CharField(max_length=255)
    address_warehouse = models.TextField(blank=True, null=True)
    city_warehouse = models.CharField(max_length=100, blank=True, null=True)
    zip_code_warehouse = models.CharField(max_length=20, blank=True, null=True)
    country_warehouse = models.ForeignKey(
        Country, on_delete=models.SET_NULL, null=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name_warehouse} ({self.company.company_name})"


class Membership(models.Model):
    slug = models.SlugField(null=True, blank=True)
    membership_type = models.CharField(
        choices=MEMBERSHIP_CHOICES, default='basic',
        max_length=20
    )
    price = models.DecimalField(decimal_places=2, max_digits=6, default=0)

    def __str__(self):
        return self.membership_type


class Subscription(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)

    date_created = models.DateTimeField(auto_now_add=True)
    date_start = models.DateTimeField(null=True, blank=True)
    date_exp = models.DateTimeField(null=True, blank=True)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_subscriptions')
    plan = models.ForeignKey(Membership, on_delete=models.CASCADE, default=1)

    active = models.BooleanField(default=True)

    notifications = ArrayField(models.BooleanField(
    ), default=get_default_notification_status_3, size=3)

    internal_use_only = models.TextField(
        max_length=1000, null=True, blank=True)

    def is_subscription_date_exp_less_than_date(self, check_date, notifications_arr_index):
        # print('M3636', check_date, )
        if self.date_exp and self.date_exp.date() < check_date and self.notifications[notifications_arr_index] == False:

            # print('M3838', )
            return True
        # print('M4040')
        return False

    class Meta:
        ordering = ['date_exp']

    def __str__(self):
        return str(self.id)


class UserPersonalApiToken(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    encrypted_api_key = models.BinaryField(null=True, blank=True)
    encrypted_refresh_key = models.BinaryField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    comments = models.CharField(max_length=200, null=True, blank=True)

    is_active = models.BooleanField(default=True)

    @staticmethod
    def generate_key():
        return binascii.hexlify(os.urandom(20)).decode()

    @property
    def api_key(self) -> str:
        """Decrypt and return the API key."""
        if not self.encrypted_api_key:
            return ""

        cipher = Fernet(settings.ENCRYPTION_KEY)
        encrypted = bytes(self.encrypted_api_key)
        return cipher.decrypt(encrypted).decode()

    @api_key.setter
    def api_key(self, raw_value: str) -> None:
        cipher = Fernet(settings.ENCRYPTION_KEY)
        self.encrypted_api_key = cipher.encrypt(raw_value.encode())

    @property
    def refresh_key(self) -> str:
        if not self.encrypted_refresh_key:
            return ""

        cipher = Fernet(settings.ENCRYPTION_KEY)
        encrypted = bytes(self.encrypted_refresh_key)
        return cipher.decrypt(encrypted).decode()

    @refresh_key.setter
    def refresh_key(self, raw_value: str) -> None:
        cipher = Fernet(settings.ENCRYPTION_KEY)
        self.encrypted_refresh_key = cipher.encrypt(raw_value.encode())

    def ensure_keys(self):
        """Generate missing API key or refresh key."""
        if not self.encrypted_api_key:
            self.api_key = self.generate_key()

        if not self.encrypted_refresh_key:
            self.refresh_key = self.generate_key()

            # Set expiry if not already set
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=365)

    def save(self, *args, **kwargs):
        self.ensure_keys()
        super().save(*args, **kwargs)

    def is_token_valid(self):
        if not self.expires_at:
            return True

        buffer_time = timezone.timedelta(hours=3)
        return timezone.now() < self.expires_at - buffer_time


class DocumentSeries(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="company_document_series")

    created_at = models.DateTimeField(auto_now_add=True)
    series = models.CharField(max_length=20)       # e.g. "MD", "RO", "AB"
    number_from = models.PositiveIntegerField()    # e.g. 000001
    number_to = models.PositiveIntegerField()      # e.g. 999999

    is_fiscal_invoice = models.BooleanField(default=False)
    is_route_sheet = models.BooleanField(default=False)
    is_cmr = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Document Series"
        verbose_name_plural = "Document Series"
        constraints = [
            models.UniqueConstraint(
                fields=['company', 'series', 'number_from', 'number_to'],
                name='unique_constraint Documents company-series-number_from-number_to'
            )
        ]

    def clean(self):
        if self.number_from >= self.number_to:
            raise ValidationError("number_from must be less than number_to.")

    def save(self, *args, **kwargs):
        try:
            super(DocumentSeries, self).save(*args, **kwargs)
        except IntegrityError as e:
            logger.error(f'ERRORLOG647 DocumentSeries. save. Error: {e}')
            raise CustomApiException(409, 'unique_together')

    def __str__(self):
        return f"{self.company.company_name} - {self.series} {self.number_from}-{self.number_to}"


class SMTPSettings(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='user_smpt_settings')

    server = models.CharField(max_length=255)
    port = models.IntegerField()
    email = models.EmailField()
    username = models.CharField(max_length=255, null=True, blank=True)
    reply_to_email = models.EmailField(null=True, blank=True)
    default_from_name = models.CharField(max_length=30)
    encrypted_password = models.BinaryField()
    encryption_type = models.CharField(
        max_length=10, choices=[('ssl', 'SSL'), ('tls', 'TLS')])

    @property
    def key(self) -> str:
        if not self.encrypted_password:
            return ""  # Handle the case where no key is stored

        try:
            cipher_suite = Fernet(settings.ENCRYPTION_KEY)
            # Convert memoryview to bytes if necessary
            if isinstance(self.encrypted_password, memoryview):
                encrypted_data = self.encrypted_password.tobytes()  # Convert memoryview to bytes
            else:
                encrypted_data = self.encrypted_password

            decrypted_key = cipher_suite.decrypt(encrypted_data)
            return decrypted_key.decode('utf-8')
        except Exception as e:
            return f"Decryption error: {str(e)}"

    @key.setter
    def key(self, value: str) -> None:
        if value:
            cipher_suite = Fernet(settings.ENCRYPTION_KEY)
            self.encrypted_password = cipher_suite.encrypt(
                value.encode('utf-8'))  # Encrypt and store as bytes

        else:
            self.encrypted_password = None  # Handle case where the key is empty or None

    def __str__(self):
        return f"{self.user}'s SMTP Settings"


class CategoryGeneral(models.Model):
    '''
    CategoryGeneral can be used as categories model for different other modules filtering by serial_number
    '''

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_categories')

    serial_number = models.SmallIntegerField(unique=True)
    code = models.CharField(unique=True)
    label = models.CharField(max_length=100)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Category General"
        verbose_name_plural = "Categories General"
        ordering = ['serial_number']


class TypeGeneral(models.Model):
    '''
    TypeGeneral can be used as type model for different other modules filtering by serial_number
    '''

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_types_general')

    serial_number = models.SmallIntegerField(unique=True)
    code = models.CharField(unique=True)
    label = models.CharField(max_length=100)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Type General"
        verbose_name_plural = "Type General"
        ordering = ['serial_number']


class TypeCost(models.Model):
    '''
    TypeCost to be use for ItemCost
    '''

    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_types_cost')

    serial_number = models.SmallIntegerField(unique=True)
    code = models.CharField(unique=True)
    label = models.CharField(max_length=100)

    is_system = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Type Cost"
        verbose_name_plural = "Types Cost"
        ordering = ['serial_number']

    def __str__(self):
        return self.label + ' / ' + self.code


class UnavailabilityReason(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_unavailability_reasons')

    serial_number = models.SmallIntegerField(unique=True)
    code = models.CharField(max_length=30, unique=True)
    label = models.CharField(max_length=100)

    for_vehicle = models.BooleanField(default=True)
    for_driver = models.BooleanField(default=True)

    is_system = models.BooleanField(default=False)

    def __str__(self):
        return self.label
