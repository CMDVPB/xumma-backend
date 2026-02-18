from datetime import datetime, timedelta
from django.db import IntegrityError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, UntypedToken, AccessToken
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from djoser.social.views import ProviderAuthView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status

import logging

from app.models import UserProfile
from app.serializers import UserProfileSerializer
from app.utils import get_all_exchange_rates
logger = logging.getLogger(__name__)


User = get_user_model()


class CustomProviderAuthView(ProviderAuthView):

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        if response.status_code == 201:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            response.set_cookie(
                'access',
                access_token,
                max_age=settings.AUTH_COOKIE_MAX_AGE,
                domain=settings.AUTH_COOKIE_DOMAIN,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,

            )
            response.set_cookie(
                'refresh',
                refresh_token,
                max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE,
                domain=settings.AUTH_COOKIE_DOMAIN,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,

            )

        return response


class CustomTokenObtainPairView(TokenObtainPairView):

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        print('A333',)

        if response.status_code == 200:
            access_token = response.data.get('access')
            refresh_token = response.data.get('refresh')

            response.set_cookie(
                'access',
                access_token,
                max_age=settings.AUTH_COOKIE_MAX_AGE,
                domain=settings.AUTH_COOKIE_DOMAIN,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,

            )
            response.set_cookie(
                'refresh',
                refresh_token,
                max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE,
                domain=settings.AUTH_COOKIE_DOMAIN,
                path=settings.AUTH_COOKIE_PATH,
                secure=settings.AUTH_COOKIE_SECURE,
                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                samesite=settings.AUTH_COOKIE_SAMESITE,

            )

        return response


class CustomCookieTokenRefreshView(TokenRefreshView):

    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh')

        if not refresh_token:
            logger.warning(f"A350 No refresh token. Refresh token is required")
            return Response({'detail': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # logger.warning(f"A352")

            token = RefreshToken(refresh_token)
            user_id = token['user_id']

            request_user = User.objects.get(id=user_id)

            if refresh_token:
                request.data['refresh'] = refresh_token

            response = super().post(request, *args, **kwargs)

            logger.info(
                f"AU2280 CustomTokenRefreshView status_code: {response.status_code}, user_id: {user_id}")

            if response.status_code == 200:
                access_token = response.data.get('access')

                # logger.warning(f"A356")

                response.set_cookie(
                    'access',
                    access_token,
                    max_age=settings.AUTH_COOKIE_MAX_AGE,
                    domain=settings.AUTH_COOKIE_DOMAIN,
                    path=settings.AUTH_COOKIE_PATH,
                    secure=settings.AUTH_COOKIE_SECURE,
                    httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                    samesite=settings.AUTH_COOKIE_SAMESITE,
                )

                ### Below logic is to check if the refresh token is about to expire & if so, generate a new refresh token ###
                try:
                    refresh_token = RefreshToken(refresh_token)
                    exp_timestamp = refresh_token['exp']

                    now = timezone.now()
                    current_timestamp = int(now.timestamp())

                    exp_naive_datetime = datetime.fromtimestamp(exp_timestamp)
                    now_naive_datetime = datetime.fromtimestamp(
                        current_timestamp)
                    time_difference = exp_naive_datetime - now_naive_datetime

                    # print('A368', exp_timestamp)

                    if time_difference < timedelta(days=3):
                        data = response.data
                        if 'access' in data:
                            try:
                                # Decode the access token to get the user information
                                token = AccessToken(data['access'])
                                user_id = token['user_id']
                                user = User.objects.get(id=user_id)

                            except Exception as e:
                                logger.warning(f"Access token invalid: {e}")
                                user = None
                                pass

                        if user is not None:
                            new_refresh_token = RefreshToken.for_user(user)
                            logger.info(
                                f"AU358 New refresh token generated. User: {user}")

                            response.set_cookie(
                                'refresh',
                                str(new_refresh_token),
                                max_age=settings.AUTH_REFRESH_COOKIE_MAX_AGE,
                                domain=settings.AUTH_COOKIE_DOMAIN,
                                path=settings.AUTH_COOKIE_PATH,
                                secure=settings.AUTH_COOKIE_SECURE,
                                httponly=settings.AUTH_COOKIE_HTTP_ONLY,
                                samesite=settings.AUTH_COOKIE_SAMESITE,
                            )

                    else:
                        logger.warning(
                            f'A1100 Refresh token is still valid, user: {request_user}')
                        pass

                except Exception as e:
                    logger.warning(f'E207 Authentication failed:{e}')
                    pass

            return response
        except User.DoesNotExist as e:
            logger.warning(f"A358 User does not exist: {e}")
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        except InvalidToken as e:
            logger.warning(f"A362 Invalid token: {e}")
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        except TokenError as e:
            # Handle general token error (like token expired)
            logger.warning(f"A364 Expired token: {e}")
            return Response({'error': 'Token is expired or invalid', }, status=status.HTTP_400_BAD_REQUEST)


class CustomCookieVerifyView(TokenVerifyView):

    def post(self, request, *args, **kwargs):
        # Extract tokens from cookies
        access_token = request.COOKIES.get('access', None)
        refresh_token = request.COOKIES.get('refresh', None)

        logger.info(
            f'A2200 ACCESS TOKEN: {"Yes" if access_token else "No"} / REFRESH TOKEN: {"Yes" if refresh_token else "No"}')

        # First, try to verify the access token
        if access_token:
            try:
                token = AccessToken(access_token)
                user_id = token['user_id']
                User.objects.get(id=user_id)

                # Manually validate the access token
                UntypedToken(access_token)
                return Response(status=status.HTTP_200_OK)

            except User.DoesNotExist as e:
                logger.warning(f"EV2217 User does not exist: {e}")
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            except InvalidToken as e:
                logger.warning(f"A5289 Access token invalid: {e}")
                # Proceed to check the refresh token
                pass

            except TokenError as e:
                # Handle general token error (like token expired)
                logger.warning(f"A5291 Expired token: {e}")
                # Proceed to check the refresh token
                pass

        # Then, try to verify the refresh token
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                # Access the user ID from the token payload
                user_id = token['user_id']
                User.objects.get(id=user_id)

                logger.warning(
                    f"A2230 There is refresh token. User ID: {user_id}")

                # Manually validate the refresh token
                UntypedToken(refresh_token)
                return Response(status=status.HTTP_200_OK)

            except User.DoesNotExist as e:
                logger.warning(
                    f"AU374 CustomTokenVerifyViewUser does not exist: {e}")
                return Response(status=status.HTTP_401_UNAUTHORIZED)

            except InvalidToken as e:
                logger.warning(f"A5298")
                logger.warning(f"Refresh token invalid: {e}")
                # Return a custom response indicating both tokens are invalid
                return Response({"detail": "Invalid refresh token"},  status=status.HTTP_400_BAD_REQUEST)

            except TokenError as e:
                # Handle general token error (like token expired)
                logger.warning(f"A5304 Expired token: {e}")
                return Response({'error': 'Token is expired or invalid', }, status=status.HTTP_400_BAD_REQUEST)

        # If both tokens are invalid or missing, return a 401 Unauthorized response
        if not access_token and not refresh_token:
            # logger.warning("No tokens provided in the request.")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # If both tokens are invalid or missing, return False
        return Response(status=status.HTTP_401_UNAUTHORIZED)


class LogoutCookieView(APIView):
    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)

        response.delete_cookie(
            'access', domain=settings.AUTH_COOKIE_DOMAIN, path=settings.AUTH_COOKIE_PATH)
        response.delete_cookie(
            'refresh', domain=settings.AUTH_COOKIE_DOMAIN, path=settings.AUTH_COOKIE_PATH)

        # print('A282', response)

        return response


###### START TOKEN / MOBILE APP ######
class CustomTokenVerifyView(TokenVerifyView):

    def post(self, request, *args, **kwargs):

        body_token = request.data.get("token")  # ✅ ADD THIS

        if body_token:
            try:
                UntypedToken(body_token)
                return Response(status=status.HTTP_200_OK)
            except Exception:
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        # fallback to cookies (for web)
        access_token = request.COOKIES.get('access')
        refresh_token = request.COOKIES.get('refresh')

        if access_token:
            try:
                UntypedToken(access_token)
                return Response(status=status.HTTP_200_OK)
            except Exception:
                pass

        if refresh_token:
            try:
                UntypedToken(refresh_token)
                return Response(status=status.HTTP_200_OK)
            except Exception:
                pass

        return Response(status=status.HTTP_401_UNAUTHORIZED)


class CustomTokenRefreshView(TokenRefreshView):

    def post(self, request, *args, **kwargs):

        refresh_token = request.data.get("refresh")

        if not refresh_token:
            logger.warning("No refresh token provided")
            return Response(
                {"detail": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)

            user_id = refresh["user_id"]
            logger.info(f"Refreshing token for user_id={user_id}")

            response = super().post(request, *args, **kwargs)

            if response.status_code != 200:
                logger.warning(f"Refresh failed: {response.data}")
                return response

            # OPTIONAL: Refresh rotation logic
            # Only if enabled ROTATE_REFRESH_TOKENS = True
            try:
                if getattr(refresh, "check_exp", None):
                    refresh.check_exp()

            except Exception:
                pass

            logger.info(f"Token refresh success for user_id={user_id}")

            return response

        except InvalidToken as e:
            logger.warning(f"Invalid refresh token: {str(e)}")
            return Response(
                {"detail": "Invalid refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        except TokenError as e:
            logger.warning(f"Token error: {str(e)}")
            return Response(
                {"detail": "Refresh token expired or invalid"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        except Exception as e:
            logger.exception("Unexpected refresh failure")
            return Response(
                {"detail": "Token refresh failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class LogoutTokenView(APIView):
    def post(self, request):
        try:
            token = RefreshToken(request.data["refresh"])

            # print('2490', token)

            token.blacklist()
            return Response(status=status.HTTP_205_RESET_CONTENT)
        except Exception:
            return Response(status=status.HTTP_400_BAD_REQUEST)

###### END TOKEN / MOBILE APP ######

###### OTHER VIEWS ######


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_exchange_rates_multi_view(request):
    try:
        national_bank = request.GET.get('national_bank')
        print('4888 get_exchange_rates_multi_view', national_bank)

        exchange_rates = get_all_exchange_rates(
            national_bank)
        data = exchange_rates

        # print('4252 get_exchange_rate', data)

        return Response(data, status=200)
    except Exception as e:
        logger.error(f'get_exchange_rates_multi_view. ERROR: {e}')
        return Response(status=400)


class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_profile(self, user):
        profile, _ = UserProfile.objects.get_or_create(user=user)
        return profile

    def get(self, request):
        profile = self.get_profile(request.user)
        serializer = UserProfileSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        profile = request.user.user_profile
        serializer = UserProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
