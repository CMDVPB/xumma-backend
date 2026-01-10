
import logging
import json
import xmltodict
import xml.etree.ElementTree as ET
from datetime import datetime
from asgiref.sync import async_to_sync
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.cache import cache
from xumma.celery import app
from channels.layers import get_channel_layer
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from abb.models import ExchangeRate
from abb.utils import how_many_seconds_until_midnight
request_session = requests.Session()
retries = Retry(total=3, backoff_factor=5)
adapter = HTTPAdapter(max_retries=retries)
request_session.mount("http://", adapter)

logger = logging.getLogger(__name__)

User = get_user_model()


def _find_dict_in_list(dict_list, key, value):
    """
    Find a dictionary in a list of dictionaries by key and value.

    :param dict_list: List of dictionaries to search.
    :param key: Key to look for in the dictionaries.
    :param value: Value that the key should have.
    :return: The first dictionary that matches the key and value, or None if not found.
    """
    for d in dict_list:
        if key in d and d[key] == value:
            return d
    return None


@app.task()
def get_exchange_rates_task(national_bank, *args, **kwargs):
    ''' Get exchange rates from NBM, NBR or NBU depending on the app_currency (national_bank) parameter '''
    # print('TS508', )

    timezone_today = timezone.now().today()
    timezone_today_without_dashes = timezone_today.strftime('%Y%m%d')

    try:
        metadata_field_name = None
        list_data_for_json = []
        today = datetime.today().strftime("%d.%m.%Y")
        nbr_url = f'https://www.bnr.ro/nbrfxrates.xml?date={today}'
        nbm_url = f'https://www.bnm.md/ro/official_exchange_rates?get_xml=1&date={today}'
        nbu_url = f'https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?date={timezone_today_without_dashes}&json'

        if national_bank == 'nbr':
            url = nbr_url
            metadata_field_name = 'metadata_nbr'
        elif national_bank == 'nbm':
            url = nbm_url
            metadata_field_name = 'metadata_nbm'
        elif national_bank == 'nbu':
            url = nbu_url
            metadata_field_name = 'metadata_nbu'

        response = request_session.get(url, timeout=5)

        if response.status_code == 200:

            if national_bank == 'nbr':
                root = ET.fromstring(response.content)

                # print('6258', )

                # Define the namespace
                namespace = {'ns': 'http://www.bnr.ro/xsd'}

                # Find the Cube element
                cube = root.find('.//ns:Cube', namespace)

                # Extract rates and convert to a dictionary
                rates_dict = {}
                for rate in cube.findall('ns:Rate', namespace):
                    currency = rate.get('currency')
                    value = rate.text
                    rates_dict[currency] = float(value)

                # Print the result

                list_data_for_json = [
                    {'currency_code': 'mdl', 'currency_numeric': '498',
                        'value': rates_dict.get('MDL')},
                    {'currency_code': 'eur', 'currency_numeric': '978',
                        'value': rates_dict.get('EUR')},
                    {'currency_code': 'usd', 'currency_numeric': '840',
                        'value': rates_dict.get('USD')},
                    {'currency_code': 'uah', 'currency_numeric': '980',
                        'value': rates_dict.get('UAH')},
                    {'currency_code': 'rub', 'currency_numeric': '643',
                        'value': rates_dict.get('RUB')},
                    {'currency_code': 'huf', 'currency_numeric': '348',
                     'value': rates_dict.get('HUF')/100},
                    {'currency_code': 'bgn', 'currency_numeric': '100',
                     'value': rates_dict.get('BGN')},
                    {'currency_code': 'try', 'currency_numeric': '949',
                     'value': rates_dict.get('TRY')},
                ]

                # print('6284', list_data_for_json)

            elif national_bank == 'nbm':

                data_dict = xmltodict.parse(response.content)

                currency_data_dict = data_dict['ValCurs']['Valute']

                ron = _find_dict_in_list(currency_data_dict, 'CharCode', 'RON')
                eur = _find_dict_in_list(currency_data_dict, 'CharCode', 'EUR')
                usd = _find_dict_in_list(currency_data_dict, 'CharCode', 'USD')
                uah = _find_dict_in_list(currency_data_dict, 'CharCode', 'UAH')
                rub = _find_dict_in_list(currency_data_dict, 'CharCode', 'RUB')
                huf = _find_dict_in_list(currency_data_dict, 'CharCode', 'HUF')
                bgn = _find_dict_in_list(currency_data_dict, 'CharCode', 'BGN')
                trl = _find_dict_in_list(currency_data_dict, 'CharCode', 'TRY')

                list_data_for_json = [
                    {'currency_code': 'ron',
                        'currency_numeric': ron['NumCode'], 'value': ron['Value']},
                    {'currency_code': 'eur',
                        'currency_numeric': eur['NumCode'], 'value': eur['Value']},
                    {'currency_code': 'usd',
                        'currency_numeric': usd['NumCode'], 'value': usd['Value']},
                    {'currency_code': 'uah',
                        'currency_numeric': uah['NumCode'], 'value': uah['Value']},
                    {'currency_code': 'rub',
                        'currency_numeric': rub['NumCode'], 'value': rub['Value']},
                    {'currency_code': 'huf',
                        'currency_numeric': huf['NumCode'], 'value': float(huf['Value'])/100},
                    {'currency_code': 'try',
                        'currency_numeric': trl['NumCode'], 'value': trl['Value']},
                ]

            elif national_bank == 'nbu':

                # Parse the JSON data into a Python dictionary
                data = response.json()

                # Define the list of currencies you want to extract
                target_currencies = ['RON', 'MDL', 'EUR',
                                     'USD', 'RUB', 'HUF', 'BGN', 'TRY']

                # Create a list to store the exchange rates for target currencies
                list_data_for_json = []

                # Iterate through the data and extract information for target currencies
                for item in data:
                    currency_code = item['cc']
                    if currency_code in target_currencies:
                        # Create an object with the required keys
                        currency_info = {
                            'currency_code': currency_code.lower(),
                            'value': item['rate'],
                            'currency_numeric_code': item['r030']
                        }
                        list_data_for_json.append(currency_info)

                # Print the list of currency objects
                # for currency in list_data_for_json:
                #     print(currency)

                # print('6288', list_data_for_json)

            ### Prepare data in json to store in cache & database ###
            if len(list_data_for_json) > 0:
                json_data = json.dumps(list_data_for_json)

                data = {
                    'date': timezone_today,
                    metadata_field_name: json_data
                }

                cache.set(f'exchange_rates_{national_bank}_{today}', json_data,
                          how_many_seconds_until_midnight())

                # print('5258', cache.get(f'exchange_rates_{app_currency}_{today}'))

                if not ExchangeRate.objects.filter(date=timezone_today).exists():
                    # print('5268',)
                    ExchangeRate.objects.create(**data)
                elif ExchangeRate.objects.filter(date=timezone_today).exists():
                    exchange_rate_instance = ExchangeRate.objects.get(
                        date=timezone_today)

                    setattr(exchange_rate_instance,
                            metadata_field_name, json_data)

                    exchange_rate_instance.save(
                        update_fields=[metadata_field_name])

                return None

    except Exception as e:
        logger.error(f'ERRORLO6571 get_exchange_rates_task. ERROR: {e}')
        return None
