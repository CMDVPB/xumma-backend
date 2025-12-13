
from django.utils import timezone
from django.contrib.auth.models import Group

import logging
logger = logging.getLogger(__name__)


def is_user_member_group(user, group_name):
    try:
        group = Group.objects.get(name=group_name)
        return True if group in user.groups.all() else False
    except Exception as e:
        logger.error(f'ERRORLOG441 is_user_member_group. Error: {e}')
        return False
