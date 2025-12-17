from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_str


class SlugRelatedGetOrCreateField(serializers.SlugRelatedField):
    """
    A read-write field that represents the target of the relationship
    by a unique 'slug' attribute.
    """

    def to_internal_value(self, data):
        # print('6565', list(data))
        queryset = self.get_queryset()
        try:
            # print('6464', )
            return queryset.get_or_create(**{self.slug_field: data})[0]
        except ObjectDoesNotExist:
            self.fail('does_not_exist', slug_name=self.slug_field,
                      value=smart_str(data))
        except (TypeError, ValueError):
            self.fail('invalid')
