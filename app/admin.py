import logging
import json
from django import forms
from django.contrib import admin
from django.contrib.auth.hashers import make_password

from .models import (CategoryGeneral, Company, CompanySettings, 
                     LoadWarehouse, TypeCost, TypeGeneral, User, DocumentSeries, 
                     Membership, Subscription, SMTPSettings, UserProfile, UserSettings)
from .admin_utils import DocumentSeriesNumberRangeFilter


logger = logging.getLogger(__name__)

class UserAdminForm(forms.ModelForm):
    # admin-only helper field (not stored)
    lync_sequence_plain = forms.CharField(
        required=False,
        label="Set Lync sequence",
        help_text="Example: shift alt l p",
    )

    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm

    # # Not expose the hash in admin
    # exclude = ("lync_key_sequence_hash",)

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info & Subscription', {
         'fields': ('first_name', 'last_name',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff',
         'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {
         'fields': ('last_login', 'date_joined', 'date_registered', 'date_of_birth')}),
        ('Settings', {'fields': ('lang', 'base_country', 'lync_sequence_plain', 'lync_key_sequence_hash')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'first_name', 'last_name'),
        }),
    )

    def user_companies(self, obj):
        try:
            return ", ".join([k.company_name or k.id for k in obj.company_set.all()])
        except:
            return ''

    def user_groups(self, obj):
        return ", ".join([k.name for k in obj.groups.all()])

    list_display = ('id', 'email', 'user_companies', 'user_groups',
                    'get_full_name', 'base_country', 'is_superuser', 'is_staff', 'is_active', 'lang', 'uf')

    search_fields = ('id', 'email', 'username', 'groups__name')

    def save_model(self, request, obj, form, change):
        sequence_plain = form.cleaned_data.get("lync_sequence_plain")

        if sequence_plain:
            # normalize: split by spaces → list
            sequence = [k.strip().lower() for k in sequence_plain.split() if k.strip()]

            sequence_str = json.dumps(sequence, separators=(",", ":"))

            obj.lync_key_sequence_hash = make_password(sequence_str)

        super().save_model(request, obj, form, change)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    list_display = ('id', 'user', 'position', 'avatar',)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):

    def company_users(self, obj):
        return ", ".join([k.email for k in obj.user.all()])

    list_display = ('id', 'company_name', 'company_users',)

    search_fields = ("company_name", 'uf')


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'currency',)

    search_fields = ("company__company_name", 'company__uf', 'uf')


@admin.register(DocumentSeries)
class DocumentSeriesAdmin(admin.ModelAdmin):
    list_display = ('id', 'series', 'number_from', 'number_to', 'company')

    search_fields = ("series", "company__company_name")
    list_filter = (DocumentSeriesNumberRangeFilter,)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ('membership_type', 'price')


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'plan', 'company_users',
                    'active', 'date_start_formatted', 'exp_date_formatted', 'internal_use_only')

    ordering = ('-date_exp',)

    def date_start_formatted(self, obj):
        try:
            return obj.date_start.strftime("%d %b %Y")
        except Exception as e:
            logger.error(
                f'ERRORLOG771 SubscriptionAdmin. date_start_formatted. Error: {e}')
            return ''

    def exp_date_formatted(self, obj):
        try:
            return obj.date_exp.strftime("%d %b %Y")
        except Exception as e:
            logger.error(
                f'ERRORLOG773 SubscriptionAdmin. exp_date_formatted. Error: {e}')
            return ''

    def company_users(self, obj):
        if obj.company:
            return ", ".join([k.email for k in obj.company.user.all()])
        else:
            return ''

    search_fields = ('company__uf', 'company__user__email',
                     'company__company_name', 'active')


@admin.register(SMTPSettings)
class SMTPSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'email', 'username', 'server')

    search_fields = ('user__email', 'email', 'username', 'server')


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', )

    search_fields = ('user__email',)


@admin.register(CategoryGeneral)
class CategoryGeneralAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'serial_number',
                    'code', 'label', 'is_system')


@admin.register(TypeGeneral)
class TypeGeneralAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'serial_number',
                    'code', 'label', 'is_system')


@admin.register(TypeCost)
class TypeCostAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'serial_number',
                    'code', 'label', 'is_system')


@admin.register(LoadWarehouse)
class LoadWarehouseAdmin(admin.ModelAdmin):

    list_display = ('id', 'company', 'name_warehouse', "country_warehouse", 'is_active', 'uf',
                    )
