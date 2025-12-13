
from django.utils import timezone
from django.db.models.signals import post_save, pre_delete, post_delete
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from djoser.signals import user_registered, user_activated

from abb.constants import INITIAL_VALIDITY_OF_SUBSCRIPTION_DAYS
from abb.utils import get_user_company
from app.models import Company, Subscription, UserSettings
from app.utils import is_user_member_group

import logging
logger = logging.getLogger(__name__)


User = get_user_model()


@receiver(user_registered)
def create_company_add_user_to_company_and_user_to_group_level_signal(user, request, **kwargs):
    # print('S717', user, request.user)

    if user and not request.user.is_authenticated:
        try:
            company, created = Company.objects.get_or_create(
                user__id=user.id)
            # print('S711', company)
            user.company_set.add(company)
            # print('S712', company)
            user.groups.add(Group.objects.get(name='level_manager'))

            # print('S719', company)
        except Exception as e:
            logger.error(
                f'ES119 Error create_company_add_user_to_company_and_user_to_group_level_signal: {e}')
            raise ValueError('Group could not be created')
    else:
        logger.info(
            f'SG1404 create_company_add_user_to_company_and_user_to_group_level_signal: user: {user}, request.user: {request.user}')
        pass


@receiver(user_registered)
def manager_add_new_user_to_company_and_add_user_to_group_level_signal(user, request, **kwargs):

    logger.info(
        f'SG777 manager_add_new_user_to_company user: {user}, request.user: {request.user}')

    if user and request.user.is_authenticated and is_user_member_group(request.user, 'level_manager'):
        try:
            manager_company = request.user.company_set.all().first()
            user.company_set.add(manager_company)
            user.groups.add(Group.objects.get(name='level_dispatcher'))
            print('S767', manager_company)
        except Exception as e:
            print('ES139', e)
            raise ValueError('Group could not be created')

    else:
        pass


@receiver(user_registered)
def create_user_settings_signal(user, request, **kwargs):
    if user and not request.user.is_authenticated:
        UserSettings.objects.create(user=user)


@receiver(user_activated)
def when_user_activated_add_subscription_signal(user, request, **kwargs):
    try:
        logger.info(
            f'SG444 when_user_activated_add_subscription_signal user: {user}, request.user: {request.user}')

        if is_user_member_group(user, 'level_manager'):
            today = timezone.now()
            user_company = get_user_company(user)
            today_plus_initial_validity_of_subscription_days = timezone.now(
            ) + timezone.timedelta(days=INITIAL_VALIDITY_OF_SUBSCRIPTION_DAYS)
            Subscription.objects.create(
                company=user_company, date_start=today, active=True, date_exp=today_plus_initial_validity_of_subscription_days)
        else:
            logger.info(
                f'SG446 when_user_activated_add_subscription_signal, user is not manage, user: {user}')
            pass
    except Exception as e:
        logger.error(f'ES441 when_user_activated_add_subscription_signal {e}')


@receiver(pre_delete, sender=User)
def clear_user_companies_relations_if_user_is_manager_signal(sender, instance, **kwargs):
    try:
        if is_user_member_group(instance, 'level_manager'):
            user_companies = instance.company_set.all()
            # print('S8063', user_companies)
            if user_companies.exists():
                for k in user_companies:
                    # print('S8064')
                    try:
                        for s in k.company_companymemberships.company_membership_subscriptions.all():

                            subscription_obj = Subscription.objects.get(
                                id=s.id)
                            subscription_obj.active = False
                            subscription_obj.save()
                            # print('S8066', subscription_obj)
                    except:
                        pass

            instance.company_set.clear()

        else:
            pass

    except:
        raise ValueError('Company could not be deleted')
