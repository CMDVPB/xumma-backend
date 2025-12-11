from django.core.exceptions import DisallowedHost
from django.http import JsonResponse

import logging
logger = logging.getLogger(__name__)


class CustomHandleInvalidHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except DisallowedHost:
            return self.handle_invalid_host(request)

    async def __acall__(self, request):
        try:
            return await self.get_response(request)
        except DisallowedHost:
            return self.handle_invalid_host(request)

    def handle_invalid_host(self, request):
        logger.error(
            f"EM2200 Invalid Host Header: {request.get_host()} | "
            f"IP: {request.META.get('REMOTE_ADDR')} | "
            f"User-Agent: {request.META.get('HTTP_USER_AGENT')}"
        )
        return JsonResponse(
            {"error": "Invalid Host Header"},
            status=400
        )
