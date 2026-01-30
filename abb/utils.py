from datetime import datetime
import pandas as pd
from django.utils.timezone import make_aware
import base64
import os
import uuid
import re
import hmac
import hashlib
import time
from django.utils import timezone
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.db.models.query import QuerySet
from django.core.exceptions import ValidationError
from urllib.parse import urlencode

import logging
logger = logging.getLogger(__name__)

translation_manager = settings.TRANSLATION_MANAGER


def hex_uuid():
    """ Docstring """
    return uuid.uuid4().hex


def get_default_notification_status_3():
    return [False, False, False]


def get_user_company(user):
    try:
        user_company = user.company_set.all().first()
        return user_company

    except Exception as e:
        logger.error(f'EU759 get_user_company. Error: {e}')
        return None


def get_company_manager(company):
    manager = None
    level_group_name = 'level_manager'

    try:
        company_users = company.user.all()
        for user in company_users:
            if user.groups.filter(name__exact=level_group_name).exists():
                manager = user

        return manager
    except Exception as e:
        logger.error(f'EU683 get_company_manager. Error: {e}')
        pass

    return manager


def get_company_users(user):
    try:
        user_company = get_user_company(user)

        if user_company is not None:
            com_users = user_company.user.all()
            return com_users
        else:
            return []
    except Exception as e:
        logger.error(f'EU571 get_company_users. Error: {e}')
        return []


def get_company_current_membership(user_or_company_instance=None):
    """
    Returns a tuple: (company_current_active_subscription, current_subscription_plan_str)
    Example:
        company_current_active_subscription, current_subscription_plan_str = get_company_current_membership(request.user)
    """
    today_date = timezone.now().date()

    current_subscription_plan_str = 'basic'
    company_current_active_subscription = None
    user_company = None

    if user_or_company_instance is not None:
        # print('U544',)

        try:
            if (hasattr(user_or_company_instance, 'first_name') and not user_or_company_instance.is_anonymous) \
                    or hasattr(user_or_company_instance, 'logo'):
                # print('U550',)

                if hasattr(user_or_company_instance, 'logo'):
                    user_company = user_or_company_instance
                else:
                    user_company = get_user_company(user_or_company_instance)

                # print('U552', user_company)

                if user_company is not None:
                    user_company_subsriptions = user_company.company_subscriptions.all()

                    # print('UT554',)

                    company_current_active_subscription = user_company_subsriptions.select_related('plan').filter(
                        Q(active=True) & Q(date_start__date__lte=today_date) & Q(date_exp__date__gte=today_date)).first()

                    if company_current_active_subscription:
                        current_subscription_plan_str = company_current_active_subscription.plan.membership_type

                        # print('UT558', current_subscription_plan_str)

        except Exception as e:
            logger.error(
                f'EU483 get_company_current_membership, error: {e}')
            pass

    return company_current_active_subscription, current_subscription_plan_str


def get_is_company_subscription_active(user_company):

    try:

        company_current_active_subscription, current_subscription_plan_str = get_company_current_membership(
            user_company)

        if company_current_active_subscription is not None:
            return company_current_active_subscription.active

        return False  # no active subscription found
    except Exception as e:
        logger.error(f"EU587 Error in get_is_company_subscription_active: {e}")
        return False


def get_contact_type_default():
    """ Docstring """
    return ['client']


def assign_new_num(items_list_qs, num):
    """
    Generate next sequential number based on the numeric suffix of the field `num`.
    Example: existing numbers ['CMR1', 'CMR2'] → returns 'CMR3'
    """
    items_list = []

    try:
        # Extract numeric parts
        for item in items_list_qs.iterator():
            value = getattr(item, num, None)
            if not value:
                continue
            match = re.search(r'\d+$', str(value))
            if match:
                items_list.append(int(match.group()))

        if items_list:
            max_int = max(items_list)
            # Get last object's non-numeric prefix
            query = {f"{num}__endswith": str(max_int)}
            last_obj = items_list_qs.filter(Q(**query)).first()
            if last_obj:
                last_value = getattr(last_obj, num, "")
                prefix = last_value[0:-len(str(max_int))] if last_value else ""
                new_num = f"{prefix}{max_int + 1}"
            else:
                # fallback, just use number
                new_num = str(max_int + 1)
        else:
            # No existing numbers → start with 1
            new_num = "1"

        return new_num

    except Exception as e:
        logger.error(f"EU433 Error in assign_new_num: {e}")
        return "1"  # fallback


def assign_new_num_inv(items_list_qs, num):
    """Assigns the next number with zero-padding based on the highest existing number."""

    items_list = []
    new_num = ''

    try:
        for item in items_list_qs.iterator():
            # Capture optional prefix (letters) and numeric part
            match = re.match(r'(\D*)(\d+)$', str(getattr(item, num)))
            if match:
                prefix, number_part = match.groups()
                items_list.append((prefix, int(number_part), len(number_part)))

        if not items_list:
            return '001'  # Default value if no records are found

        # Find the highest numeric value
        prefix, max_int, num_length = max(items_list, key=lambda x: x[1])

        # Generate the next number with leading zeros preserved
        next_number_str = str(max_int + 1).zfill(num_length)

        # Construct new number (with or without prefix)
        new_num = f'{prefix}{next_number_str}'

        return new_num

    except Exception as e:
        logger.error(f"EU433 Error in assign_new_num: {e}")
        return new_num


def _totalsEntries(entriesList):
    piecesList = []
    weightList = []
    volumeList = []
    ldmList = []
    if isinstance(entriesList, QuerySet):

        if any(entry.action == 'loading' for entry in entriesList):
            for entry in entriesList:
                if entry.action == 'loading':
                    for item in entry.entry_details.all():
                        piecesList.append(float(item.pieces or 0))
                        weightList.append(float(item.weight or 0))
                        volumeList.append(float(item.volume or 0))
                        ldmList.append(float(item.ldm or 0))
        else:
            for entry in entriesList:
                if entry.action == 'unloading':
                    for item in entry.entry_details.all():
                        piecesList.append(float(item.pieces or 0))
                        weightList.append(float(item.weight or 0))
                        volumeList.append(float(item.volume or 0))
                        ldmList.append(float(item.ldm or 0))
    else:
        return [0, 0, 0, 0]
    return [sum(piecesList), sum(weightList), sum(volumeList), sum(ldmList)]


def tripLoadsTotals(trip):
    piecesArray = []
    weightArray = []
    volumeArray = []
    ldmArray = []
    if trip and trip.trip_loads:
        for load in trip.trip_loads.all():
            arrayTotalsLoadings = _totalsEntries(load.entry_loads.all())
            piecesArray.append(arrayTotalsLoadings[0])
            weightArray.append(arrayTotalsLoadings[1])
            volumeArray.append(arrayTotalsLoadings[2])
            ldmArray.append(arrayTotalsLoadings[3])
    return [
        round(sum(piecesArray)),
        round(sum(weightArray), 2),
        round(sum(volumeArray), 2),
        round(sum(ldmArray), 2)
    ]


def default_notification_status_3():
    return [False, False, False]


def upload_to(instance, filename):
    company_prefix = instance.company.uf[:5] if instance.company else 'GEN'
    return f"umma-uploads/{company_prefix}/{filename}"


def get_default_empty_strings_20():
    return ['0']*20


def company_latest_exp_date_subscription(user_company):
    today_date = timezone.now().date()

    try:
        company_latest_exp_date_subscription = user_company.company_subscriptions.\
            filter(
                Q(date_start__date__lte=today_date) &
                Q(date_exp__date__gte=today_date) &
                Q(active=True)
            ).select_related("plan").order_by('-date_exp').first()

        if not company_latest_exp_date_subscription:
            return ""

        subscription_type = company_latest_exp_date_subscription.plan.membership_type
        subscription_exp_date = company_latest_exp_date_subscription.date_exp

        year = subscription_exp_date.year
        month = subscription_exp_date.month
        day = subscription_exp_date.day

        return_string = f'{subscription_type}_{year}-{month}-{day}'

        # print('U068', return_string)

        return return_string

    except Exception as e:
        logger.error(
            f'ERRORLOG793 company_latest_exp_date_subscription. Error: {e}')
        return ""


def is_valid_queryparam(param):
    # print('8383', param)
    return param != '' and param is not None and param != [''] and param != []


def check_not_unique_num(item, queryset, new_item_num, num):
    if item and item.uf:
        queryset = queryset.exclude(uf=item.uf)
    all_items_list = queryset
    new_item_num = new_item_num

    if new_item_num != None or new_item_num != '':
        num_list = list()
        for list_item in all_items_list:
            num_list.append(getattr(list_item, num))

        # print('4761', num_list)

        if new_item_num in num_list:
            return True
        else:
            return False


def check_not_unique_num_inv(queryset, new_item_num, num, series=None, exclude_uf=None):
    if not new_item_num:
        return False

    if exclude_uf:
        queryset = queryset.exclude(uf=exclude_uf)

    if series:
        queryset = queryset.filter(series__uf=series)

    return queryset.filter(**{num: new_item_num}).exists()


def get_order_by_default():
    """ Docstring """
    return ['1', '1', '1', '1', '1', '1', '1']


def validate_columns_arrayfield_length_min_5(value):

    if len(value) < 5:
        print('3434', value)
        raise ValidationError(
            message=('min_field_array_length_5'), code="invalid")
    # print('3535', value)
    pass


def get_request_language(request, default="ro"):
    if not request:
        return default

    return getattr(request, "LANGUAGE_CODE", default)


def how_many_seconds_until_midnight():
    """Get the number of seconds until midnight."""
    tomorrow = datetime.now() + timedelta(1)
    midnight = datetime(year=tomorrow.year, month=tomorrow.month,
                        day=tomorrow.day, hour=0, minute=0, second=0)
    return (midnight - datetime.now()).seconds


def generate_signed_url(path: str, expires_in: int = None):
    expires_in = expires_in or settings.SIGNED_URL_TTL_SECONDS
    expires = int(time.time()) + expires_in

    payload = f"{path}:{expires}"
    signature = hmac.new(
        settings.ENCRYPTION_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    query = urlencode({
        "expires": expires,
        "signature": signature,
    })

    return f"{path}?{query}"


def verify_signed_url(path: str, expires: int, signature: str) -> bool:
    if int(time.time()) > int(expires):
        return False

    payload = f"{path}:{expires}"
    expected = hmac.new(
        settings.ENCRYPTION_KEY.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)


def generate_signed_url_zip(token: str, expires_in: int = None):
    expires_in = expires_in or settings.SIGNED_URL_TTL_SECONDS
    expires = int(time.time()) + expires_in

    payload = f"image-zip:{token}:{expires}"

    signature = base64.urlsafe_b64encode(
        hmac.new(
            settings.ENCRYPTION_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).digest()
    ).decode().rstrip("=")

    # signature = hmac.new(
    #     settings.ENCRYPTION_KEY.encode(),
    #     payload.encode(),
    #     hashlib.sha256
    # ).hexdigest()

    return f"/api/image-zip-signed/{token}/?expires={expires}&signature={signature}"


def verify_signed_zip(token: str, expires: str, signature: str) -> bool:
    try:
        expires = int(expires)
    except (TypeError, ValueError):
        return False

    if time.time() > expires:
        return False

    payload = f"image-zip:{token}:{expires}"

    expected = base64.urlsafe_b64encode(
        hmac.new(
            settings.ENCRYPTION_KEY.encode(),
            payload.encode(),
            hashlib.sha256
        ).digest()
    ).decode().rstrip("=")

    # expected = hmac.new(
    #     settings.ENCRYPTION_KEY.encode(),
    #     payload.encode(),
    #     hashlib.sha256
    # ).hexdigest()

    print("EXPECTED:", expected)
    print("RECEIVED:", signature)

    return hmac.compare_digest(expected, signature)


def normalize_reg_number(value: str) -> str:
    if not value:
        return ""
    return (
        str(value)
        .upper()
        .replace(" ", "")
        .replace("-", "")
    )


def normalize_excel_datetime(value, tz=None):
    """
    Accepts:
    - pandas.Timestamp
    - datetime
    - string like '1/16/2026 14:23:19'
    Returns:
    - ISO 8601 string with timezone
    """

    if value in ("", None):
        return None

    # pandas Timestamp
    if isinstance(value, pd.Timestamp):
        dt = value.to_pydatetime()

    # python datetime
    elif isinstance(value, datetime):
        dt = value

    # string
    else:
        try:
            dt = pd.to_datetime(value, dayfirst=False).to_pydatetime()
        except Exception:
            return None

    if dt.tzinfo is None:
        dt = make_aware(dt, timezone=tz)

    return dt.isoformat()

###### Start Image, files uploads utils ######


def image_upload_path(instance, filename):
    """
    Decide upload folder based on related object.
    """
    name, ext = os.path.splitext(filename)
    new_name = f"{uuid.uuid4()}{ext}"

    base = "uploads"

    model = instance.__class__.__name__

    if model == "WorkOrderAttachment":
        return f"{base}/work_orders/{instance.work_order.uf}/{new_name}"

    if model == "DriverReportImage":
        return f"{base}/driver_reports/{instance.report.uf}/{new_name}"

    if model == "LoadAttachment":
        return f"{base}/loads/{instance.load.uf}/{new_name}"

    if model == "VehicleAttachment":
        return f"{base}/vehicles/{instance.vehicle.uf}/{new_name}"

    if model == "UserAttachment":
        return f"{base}/users/{instance.user.id}/{new_name}"

    if model == "CompanyAttachment":
        return f"{base}/companies/{instance.company.uf}/{new_name}"

    # GENERIC IMAGEUPLOAD (if still use it / not sure)
    if model == "ImageUpload":
        if instance.company:
            return f"{base}/companies/{instance.company.uf}/{new_name}"

    return f"{base}/misc/{new_name}"

    # # WORK ORDER
    # if hasattr(instance, "work_order") and instance.work_order:
    #     return f"{base}/work_orders_att/{instance.work_order.uf}/{new_name}"

    # # DRIVER REPORT
    # if hasattr(instance, "report") and instance.report:
    #     return f"{base}/driver_reports/{instance.report.uf}/{new_name}"

    # # LOAD
    # if hasattr(instance, "load") and instance.load:
    #     return f"{base}/loads/{instance.load.uf}/{new_name}"

    # # VEHICLE
    # if hasattr(instance, "vehicle") and instance.vehicle:
    #     return f"{base}/vehicles/{instance.vehicle.uf}/{new_name}"

    # # USER
    # if hasattr(instance, "user") and instance.user:
    #     return f"{base}/users/{instance.user.id}/{new_name}"

    # # COMPANY
    # if hasattr(instance, "company") and instance.company:
    #     return f"{base}/companies/{instance.company.uf}/{new_name}"

    # # FALLBACK
    # return f"{base}/misc/{new_name}"

###### End Image, files uploads utils ######
