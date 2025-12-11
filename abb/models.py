from django.db import models

from .utils import hex_uuid


class Country(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    serial_number = models.PositiveSmallIntegerField(unique=True)
    label = models.CharField(max_length=2, blank=False, null=False)
    value = models.CharField(
        max_length=120, blank=False, null=False, unique=True)
    value_iso3 = models.CharField(max_length=3, blank=False, null=False)
    value_numeric = models.CharField(max_length=3, blank=False, null=False)

    class Meta:
        verbose_name = "Country"
        verbose_name_plural = "Countries"
        ordering = ['serial_number']

    def __str__(self):
        return self.value or ''


class Currency(models.Model):
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    currency_code = models.CharField(max_length=3, unique=True)
    currency_name = models.CharField(max_length=70, null=True, blank=True)
    currency_symbol = models.CharField(max_length=70, null=True, blank=True)
    currency_numeric = models.PositiveSmallIntegerField(
        unique=True, null=True, blank=True)
    serial_number = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        verbose_name = "Currency"
        verbose_name_plural = "Currencies"

    def save(self, *args, **kwargs):
        self.currency_code = self.currency_code.upper()
        return super(Currency, self).save(*args, **kwargs)

    def __str__(self):
        return self.currency_code or ''


class ExchangeRate(models.Model):
    ''' Exchange rates to be received daily authomatically by a task'''
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    date = models.DateField()
    metadata_nbr = models.JSONField(blank=True, null=True)
    metadata_nbm = models.JSONField(blank=True, null=True)
    metadata_nbu = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Exchange Rate"
        verbose_name_plural = "Exchange Rates"

    def __str__(self):
        return f"{self.date}"


class Incoterm(models.Model):
    ''' All incoterms to be pre-defined '''
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    serial_number = models.PositiveSmallIntegerField(unique=True)
    it = models.CharField(max_length=3)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Incoterm"
        verbose_name_plural = "Incoterms"

    def save(self, *args, **kwargs):
        self.lt = self.it.upper()
        return super(Incoterm, self).save(*args, **kwargs)

    def __str__(self):
        return self.it or ''


class BodyType(models.Model):
    ''' Vehicle body type '''
    uf = models.CharField(max_length=36, default=hex_uuid, unique=True)
    serial_number = models.PositiveSmallIntegerField(unique=True)
    bt = models.CharField(max_length=25, blank=True, null=True)
    description = models.CharField(max_length=60, blank=True, null=True)

    class Meta:
        verbose_name = "Body type"
        verbose_name_plural = "Body types"

    def __str__(self):
        return self.description or ''


class ModeType(models.Model):
    ''' Mode transport type '''
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    serial_number = models.PositiveSmallIntegerField(unique=True)
    mt = models.CharField(max_length=15)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Mode transport type"
        verbose_name_plural = "Mode transport types"

    def save(self, *args, **kwargs):
        self.lt = self.mt.upper()
        return super(ModeType, self).save(*args, **kwargs)

    def __str__(self):
        return self.mt or ''


class StatusType(models.Model):
    ''' Status type '''
    uf = models.CharField(max_length=36, default=hex_uuid,
                          db_index=True, unique=True)
    serial_number = models.PositiveSmallIntegerField(unique=True)
    order_number = models.PositiveSmallIntegerField(
        unique=True, blank=True, null=True)
    st = models.CharField(
        max_length=25, blank=True, null=True)
    description = models.CharField(max_length=150, blank=True, null=True)

    class Meta:
        verbose_name = "Status"
        verbose_name_plural = "Statuses"
        ordering = ['serial_number']

    def __str__(self):
        return self.st or ''
