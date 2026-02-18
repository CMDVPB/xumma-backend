import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from http.cookies import SimpleCookie
from django.contrib.auth.models import AnonymousUser
from asgiref.sync import sync_to_async
from urllib.parse import parse_qs
import logging
logger = logging.getLogger(__name__)

SECRET_KEY = settings.SECRET_KEY
User = get_user_model()


class CookieAuthMiddleware:
    """
    Custom middleware to authenticate WebSocket connections using cookies.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        headers = dict(scope['headers'])

        query_params = parse_qs(scope["query_string"].decode())
        token = query_params.get("token")

        print('CookieAuthMiddleware 1100:', token)

        # ---- 1. Try query token (mobile clients) ----
        if token:
            payload = self.decode_jwt(token[0])

            if payload and 'user_id' in payload:
                scope['user'] = await self.get_user(payload['user_id'])
                logger.info(
                    f'WS1100 Query token auth OK → {payload["user_id"]}')
                return await self.app(scope, receive, send)

            else:
                scope['user'] = AnonymousUser()

            logger.info('WS1100 Query token invalid')

        # ---- 2. Try cookies (web clients) ----
        if b'cookie' in headers:
            try:
                # Parse the cookies
                cookies = SimpleCookie(headers[b'cookie'].decode('utf-8'))
                # Authenticate using access or refresh tokens
                scope['user'] = await self.authenticate_user(cookies)
            except Exception as e:
                logger.error(f'MW1040 Error parsing cookies: {e}')
                scope['user'] = AnonymousUser()

        return await self.app(scope, receive, send)

    async def authenticate_user(self, cookies):
        """
        Authenticate the user using access or refresh tokens.
        """
        # Try to authenticate with access token
        if 'access' in cookies:
            access_token = cookies['access'].value
            payload = self.decode_jwt(access_token)
            if payload and 'user_id' in payload:
                user_id = payload['user_id']

                logger.info(f'WS1120 access token valid, user ID: {user_id}')

                return await self.get_user(user_id)

        # If access token is missing or invalid, try to authenticate with refresh token
        if 'refresh' in cookies:
            refresh_token = cookies['refresh'].value
            payload = self.decode_jwt(refresh_token)
            if payload and 'user_id' in payload:
                user_id = payload['user_id']

                logger.info(f'WS1130 refresh token valid, user ID: {user_id}')

                return await self.get_user(user_id)

        print('No valid access or refresh token found')
        return AnonymousUser()

    @staticmethod
    def decode_jwt(token):
        """
        Decode a JWT token to extract the payload.
        """
        try:
            return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            logger.info(f'WS1145 Token expired')
            return None
        except jwt.InvalidTokenError:
            logger.info(f'WS1145 Invalid token')
            return None

    @sync_to_async
    def get_user(self, user_id):
        """
        Fetch the user object from the database.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return AnonymousUser()
