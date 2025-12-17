from collections import defaultdict
from django.db import transaction
from django.contrib.auth import get_user_model
from drf_writable_nested.serializers import WritableNestedModelSerializer
from drf_writable_nested.mixins import UniqueFieldsMixin, NestedCreateMixin, NestedUpdateMixin
from rest_framework import serializers

from abb.serializers import CurrencySerializer
from att.serializers import ModeTypeSerializer, StatusTypeSerializer
from axx.models import Inv
from dff.serializers.serializers_entry_detail import EntryBasicReadListSerializer
from dff.serializers.serializers_item_inv import ItemInvSerializer
from dff.serializers.serializers_other import CommentSerializer, ContactBasicReadSerializer

import logging
logger = logging.getLogger(__name__)

User = get_user_model()


class QuoteListSerializer(WritableNestedModelSerializer):
    ''' GET List only Quote serializer '''

    bill_to = ContactBasicReadSerializer(allow_null=True)
    mode = ModeTypeSerializer(allow_null=True)
    status = StatusTypeSerializer(allow_null=True)
    currency = CurrencySerializer(allow_null=True)
    iteminv_invs = ItemInvSerializer(many=True)
    inv_comments = CommentSerializer(many=True)
    entry_invs = EntryBasicReadListSerializer(many=True)

    class Meta:
        model = Inv
        fields = ('qn', 'vn', 'date_inv', 'date_due', 'load_detail', 'load_address', 'unload_address', 'load_size', 'is_quote', 'uf',
                  'status', 'bill_to', 'currency', 'mode',
                  'iteminv_invs', 'inv_comments', 'entry_invs'
                  )
