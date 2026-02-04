from django.contrib import admin

from .models import CategoryGeneral, Company, CompanySettings, TypeCost, TypeGeneral, User, DocumentSeries, Membership, Subscription, SMTPSettings, UserProfile, UserSettings
from .admin_utils import DocumentSeriesNumberRangeFilter


import logging
logger = logging.getLogger(__name__)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):

    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal info & Subscription', {
         'fields': ('first_name', 'last_name',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff',
         'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {
         'fields': ('last_login', 'date_joined', 'date_registered', 'date_of_birth')}),
        ('Settings', {'fields': ('lang', 'base_country')}),
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
