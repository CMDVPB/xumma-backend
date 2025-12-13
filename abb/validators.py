import re
from django.core.exceptions import ValidationError


def validate_columns_arrayfield_length_exactly_20(value):
    if len(value) != 20:
        raise ValidationError(
            message='ArrayField must contain exactly 20 elements.',
            code='invalid'
        )
