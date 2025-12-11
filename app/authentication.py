from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import exceptions


from .models import UserPersonalApiToken


class CustomJWTAuthentication(JWTAuthentication):
    ''' Custom JWT Authentication class to authenticate users using JWT token with cookies'''

    # print('A106',)

    def authenticate(self, request):

        try:
            header = self.get_header(request)

            if header is None:
                raw_token = request.COOKIES.get(settings.AUTH_COOKIE)
            else:
                raw_token = self.get_raw_token(header)

            if raw_token is None:
                return None

            validated_token = self.get_validated_token(raw_token)

            return self.get_user(validated_token), validated_token
        except:
            return None


class PersonalApiTokenAuthentication(BaseAuthentication):
    """
    Authenticate requests using the UserPersonalApiToken model.

    Clients should send:
        Authorization: Api-Key <raw_key>
    """
    keyword = "Api-Key"

    def authenticate(self, request):

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith(self.keyword):
            return None  # DRF will continue to other authenticators

        raw_key = auth_header[len(self.keyword):].strip()
        if not raw_key:
            return None

        # Lookup token
        try:
            token = UserPersonalApiToken.objects.select_related("user").all()
            for t in token:
                if t.api_key == raw_key:  # decrypt & compare
                    if not t.user.is_active:
                        raise exceptions.AuthenticationFailed("User inactive")
                    if not t.is_token_valid():
                        raise exceptions.AuthenticationFailed("Token expired")
                    return (t.user, t)  # user + token
        except UserPersonalApiToken.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key")

        raise exceptions.AuthenticationFailed("Invalid API key")
