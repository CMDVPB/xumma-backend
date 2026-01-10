import logging
import json
from django.utils import timezone
from django.contrib.auth.models import Group

from abb.models import ExchangeRate

logger = logging.getLogger(__name__)


def is_user_member_group(user, group_name):
    try:
        group = Group.objects.get(name=group_name)
        return True if group in user.groups.all() else False
    except Exception as e:
        logger.error(f'ERRORLOG441 is_user_member_group. Error: {e}')
        return False


def get_all_exchange_rates(national_bank):
    # print('U498', national_bank)

    try:
        exchange_rates = None
        # print('U378', exchange_rates)

        if exchange_rates is None:
            exchange_rates_qr = None

            exchange_rates_qr = ExchangeRate.objects.values(
                'date', f'metadata_{national_bank}')

            if exchange_rates_qr is None:
                return []

            # print('U384', )

            # values() returns a QuerySet of dictionaries, so we convert it to a list
            exchange_rates_data = list(exchange_rates_qr)

            # Transform the JSON field (metadata_{national_bank}) if needed
            for rate in exchange_rates_data:
                json_metadata = rate.get(f'metadata_{national_bank}')
                if json_metadata:
                    try:
                        # Assuming the field is already a JSON/dict, otherwise parse it
                        rate[f'metadata_{national_bank}'] = json.loads(
                            json_metadata) if isinstance(json_metadata, str) else json_metadata
                    except json.JSONDecodeError:
                        # Handle potential errors in decoding JSON
                        rate[f'metadata_{national_bank}'] = {}

            return exchange_rates_data

        # print('U398', exchange_rates)

        return exchange_rates_data
    except Exception as e:
        logger.error(f'ERRORLOG3519 get_all_exchange_rates. ERROR: {e}')
        return ExchangeRate.objects.none()
