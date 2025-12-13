import math
from django.conf import settings
from datetime import datetime
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView  # exception_handler
from rest_framework_simplejwt.authentication import JWTAuthentication  # used for FBV
from rest_framework_simplejwt.exceptions import InvalidToken  # used for FBV
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import permissions, status
from rest_framework.permissions import IsAuthenticated

from abb.models import Country, Currency
from abb.serializers import CountrySerializer, CurrencySerializer

DEBUG = settings.DEBUG


def robots_txt(request, *args, **kwargs):
    content = "User-agent: *\nDisallow: /"
    return HttpResponse(content, content_type="text/plain")


class CountryList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CountrySerializer
    queryset = Country.objects.all().order_by('serial_number')

    # @method_decorator(cache_page(60*60*24))
    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)


class CurrencyList(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CurrencySerializer
    queryset = Currency.objects.all().order_by('serial_number')

    # @method_decorator(cache_page(60 * 60 * 24))
    def get(self, request, *args, **kwargs):
        # print('5482', DEBUG)
        return self.list(request, *args, **kwargs)
