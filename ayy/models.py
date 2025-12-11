from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import ArrayField
from phonenumber_field.modelfields import PhoneNumberField

from abb.utils import hex_uuid, default_notification_status_3, upload_to

from app.models import Company
from axx.models import Load
from att.models import Contact, Person, CompanyVehicle

from .utils import user_photo_upload_path

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
        CompanyVehicle, on_delete=models.CASCADE, blank=True, null=True, related_name='company_vehicle_documents')

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


class ImageUpload(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, null=True, blank=True, related_name='company_image_uploads')

    unique_field = models.UUIDField(
        default=hex_uuid, editable=False)
    file_name = models.CharField(
        max_length=500, blank=True, null=True)
    file_obj = models.FileField(blank=True, null=True, upload_to=upload_to)
    file_size = models.PositiveIntegerField(blank=True, null=True)

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='user_image_uploads')

    load = models.ForeignKey(
        Load, on_delete=models.CASCADE, null=True, blank=True, related_name='load_image_uploads')

    company_vehicle = models.ForeignKey(
        CompanyVehicle, on_delete=models.CASCADE, null=True, blank=True, related_name='company_vehicle_image_uploads')

    class Meta:
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['load']),
            models.Index(fields=['company']),
            models.Index(fields=['company_vehicle']),
        ]

    def save(self, *args, **kwargs):
        if self.file_obj:
            if self.company:
                company_short_uf = self.company.uf[:5]
                file_name_split = self.file_obj.name.rsplit('.', 1)
                name_part = file_name_split[0]
                ext_part = file_name_split[1] if len(
                    file_name_split) > 1 else ''
                self.file_obj.name = f"{company_short_uf}_{name_part}{'.' + ext_part if ext_part else ''}"
            self.file_size = int(self.file_obj.size)
            self.file_name = self.file_obj.name
        super().save(*args, **kwargs)

    @property
    def s3_url(self):
        if self.file_obj:
            return self.file_obj.url
        return ""

    def __str__(self):
        return str(self.file_obj) or ''


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
