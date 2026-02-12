from rest_framework.pagination import CursorPagination
from collections import OrderedDict
from rest_framework.response import Response
from rest_framework.pagination import LimitOffsetPagination, PageNumberPagination, CursorPagination


class LimitResultsSetPagination(LimitOffsetPagination):
    default_limit = 20
    offset_query_param = 'offset'
    limit_query_param = 'limit'

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('results', data),
            ('limit', self.limit),
            ('offset', self.offset),
        ]))


class CustomInfiniteCursorPagination(CursorPagination):
    page_size = 12                      # default if frontend sends nothing
    page_size_query_param = "limit"     # frontend can send ?limit=...
    max_page_size = 30                  # HARD CAP (cannot exceed this)
    ordering = "-date_order"            # MUST be deterministic


class CustomInfiniteCursorPaginationLoadInv(CursorPagination):
    page_size = 12
    page_size_query_param = "limit"
    max_page_size = 30
    ordering = "-issued_at"   # ✅ correct field

# class StandardResultsSetPagination(PageNumberPagination):
#     page_size = 15
#     page_size_query_param = 'page_size'
#     max_page_size = 30

#     def get_paginated_response(self, data):
#         return Response(OrderedDict([
#             ('count', self.page.paginator.count),
#             ('results', data),
#             ('num_pages', self.page.paginator.num_pages),
#         ]))
