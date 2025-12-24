import logging
from datetime import datetime, timedelta
from smtplib import SMTPException
from django.utils import timezone
from django.conf import settings
from django.forms.models import model_to_dict
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Exists, OuterRef, Sum, Prefetch, Q, Case, When
from django.db.models.deletion import RestrictedError
from django.views.decorators.cache import cache_page
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, exceptions
from rest_framework.views import APIView
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView, CreateAPIView, \
    RetrieveUpdateDestroyAPIView, DestroyAPIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser  # JSONParser
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from abb.permissions import IsSubscriptionActiveOrReadOnly
from abb.utils import get_user_company
from app.models import Company
from att.models import TargetGroup
from dff.serializers.serializers_company import CompanySerializer
from dff.serializers.serializers_other import TargetGroupSerializer  # used for FBV

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote
request_session = requests.Session()
retries = Retry(total=3, backoff_factor=5)
adapter = HTTPAdapter(max_retries=retries)
request_session.mount("http://", adapter)

logger = logging.getLogger(__name__)

GOOGLE_API_KEY = settings.GOOGLE_MAPS_API_KEY
HERE_ID = settings.HERE_ID
HERE_API_KEY = settings.HERE_API_KEY


class TargetGroupListCreate(ListCreateAPIView):
    serializer_class = TargetGroupSerializer
    permission_classes = [IsAuthenticated, IsSubscriptionActiveOrReadOnly]
    lookup_field = 'uf'
    http_method_names = ['head', 'get', 'post']

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            queryset = TargetGroup.objects.filter(company__id=user_company.id)

            return queryset.distinct().order_by('group_name')
        except Exception as e:
            print('E553')
            return TargetGroup.objects.none()

    def post(self, request,  *args, **kwargs):
        request_obj = request.data.get('group_name', None).lower()
        if not self.get_queryset().filter(group_name__iexact=request_obj).exists():

            return self.create(request, *args, **kwargs)

        else:
            raise exceptions.ValidationError(detail='not_unique')

    def perform_create(self, serializer):
        try:
            user_company = get_user_company(self.request.user)
            serializer.save(company=user_company)
        except Exception as e:
            logger.error(
                f'ERRORLOG241 TargetGroupListCreate. perform_create. Error: {e}')
            serializer.save()


class TargetGroupDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = TargetGroupSerializer
    permission_classes = [IsAuthenticated, IsSubscriptionActiveOrReadOnly]
    http_method_names = ['head', 'get', 'patch', 'delete']
    lookup_field = 'uf'

    def get_queryset(self):
        try:
            user = self.request.user
            user_company = get_user_company(user)
            return TargetGroup.objects.filter(company__id=user_company.id).distinct()
        except Exception as e:
            logger.error(
                f'ERRORLOG519 TargetGroupDetail. get_queryset. Error: {e}')
            return TargetGroup.objects.none()

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        request_obj = request.data.get('group_name', None).lower()
        # print('3897', request_obj)

        if (instance.group_name.lower() == request_obj) or \
                not self.get_queryset().filter(group_name__iexact=request_obj).exists():

            return self.partial_update(request, *args, **kwargs)

        else:
            raise exceptions.ValidationError(detail='not_unique',)


class CompanyDetail(RetrieveUpdateDestroyAPIView):
    serializer_class = CompanySerializer

    def get_queryset(self):
        try:
            queryset = Company.objects.filter(
                user=self.request.user).distinct()

            return queryset
        except Exception as e:
            logger.error(
                f'ERRORLOG357 CompanyDetail. get_queryset. Error: {e}')

            return Company.objects.none()

    def get_object(self):
        try:
            return self.get_queryset().first()
        except:
            raise exceptions.NotFound()

    def delete(self, request, pk, format=None):
        company = self.get_object(pk)
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ContactSuggestionAPIView(APIView):
    def get(self, request):
        query = request.GET.get("query", "")

        # print('6870', query)

        if not query:
            return Response({"error": "missing_query"}, status=status.HTTP_400_BAD_REQUEST)

        suggestions = []
        google_failed = False
        here_failed = False

        ### Google ###
        try:
            payload = {
                "textQuery": query
            }

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": GOOGLE_API_KEY,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location"
            }

            r = request_session.post(
                "https://places.googleapis.com/v1/places:searchText",
                json=payload,
                headers=headers,
                timeout=3
            )

            r.raise_for_status()
            data = r.json()

            # print('6876', data)

            for item in data.get("places", []):
                formatted = item.get("formattedAddress", "") or ""
                location = item.get("location", {}) or {}

                # Split: "Air Cargo Center, 1300 Wien, Austria"
                parts = [p.strip() for p in formatted.split(",")]

                street = parts[0] if len(parts) > 0 else None
                zip_city = parts[1] if len(parts) > 1 else None
                country = parts[2] if len(parts) > 2 else None

                # Further split zip and city
                zip_code, city = None, None
                if zip_city:
                    zc = zip_city.split(" ", 1)
                    if len(zc) == 2:
                        zip_code, city = zc[0], zc[1]
                    else:
                        city = zip_city

                suggestions.append({
                    "id": item.get("id"),
                    "display_name": item.get("displayName", {}).get("text"),
                    "company_name": item.get("displayName", {}).get("text"),
                    "address": {
                        "country_code": country,
                        "city": city,
                        "zip": zip_code,
                        "address": street,      # no house number available from Search
                        "county": None          # Search data does not include county
                    },
                    "lat": float(location.get("latitude")) if location.get("latitude") else None,
                    "lon": float(location.get("longitude")) if location.get("longitude") else None
                })

        except requests.RequestException as e:
            # Log Google failure, but continue to HERE
            print("Google Places API failed:", str(e))
            google_failed = True

        ### HERE ###
        if not suggestions or google_failed:
            try:

                headers = {
                    "Content-Type": "application/json",
                }

                r = request_session.get(
                    f"https://geocode.search.hereapi.com/v1/geocode?q={query}&apiKey={HERE_API_KEY}",
                    headers=headers,
                    timeout=3
                )

                r.raise_for_status()
                data = r.json()

                # print('7560', data)

                for item in data.get("items", []):
                    addr = item.get("address", {})
                    pos = item.get("position", {})

                    suggestions.append({
                        "id": item.get("id"),
                        "display_name": item.get("title") or query,
                        "company_name": item.get("title") or query,
                        "address": {
                            "country_code": (addr.get("countryCode") or "").upper(),
                            "city": addr.get("city"),
                            "zip": addr.get("postalCode"),
                            "address": " ".join(filter(None, [
                                addr.get("street"),
                                addr.get("houseNumber")
                            ])).strip(),
                            "county": addr.get("county"),
                        },
                        "lat": float(pos.get("lat")) if pos.get("lat") else None,
                        "lon": float(pos.get("lng")) if pos.get("lng") else None
                    })

            except requests.RequestException as e:
                print("HERE Geocode API failed:", str(e))
                here_failed = True

        ### Return result or error if both failed ###
        if not suggestions and (google_failed and here_failed):
            return Response({
                "error": "both_apis_failed",
                "details": "both_apis_failed"
            }, status=status.HTTP_502_BAD_GATEWAY)

        return Response(suggestions)
