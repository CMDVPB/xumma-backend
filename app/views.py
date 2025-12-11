import smtplib
from datetime import datetime, timedelta
from django.db import IntegrityError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
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

import logging
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


class CustomTokenRefreshView(TokenRefreshView):

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


class CustomTokenVerifyView(TokenVerifyView):

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


class LogoutView(APIView):
    def post(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_204_NO_CONTENT)

        response.delete_cookie(
            'access', domain=settings.AUTH_COOKIE_DOMAIN, path=settings.AUTH_COOKIE_PATH)
        response.delete_cookie(
            'refresh', domain=settings.AUTH_COOKIE_DOMAIN, path=settings.AUTH_COOKIE_PATH)

        # print('A282', response)

        return response
