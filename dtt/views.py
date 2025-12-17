import smtplib
from datetime import datetime, timedelta
from django.db import IntegrityError
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView, CreateAPIView, DestroyAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions, status, exceptions
from rest_framework.decorators import authentication_classes, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from app.models import SMTPSettings, UserSettings
from app.serializers import UserSettingsSerializer


import logging
logger = logging.getLogger(__name__)


User = get_user_model()


class UserSettingsView(RetrieveUpdateDestroyAPIView):
    serializer_class = UserSettingsSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['head', 'get', 'patch']

    def get_object(self):
        # Always return settings for the currently logged-in user
        settings, _ = UserSettings.objects.get_or_create(
            user=self.request.user)
        return settings

    def patch(self, request, *args, **kwargs):
        print('5749', request.data)
        return self.partial_update(request, *args, **kwargs)


### SMTP Settings ###
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_smtp_connection_view(request):
    """
    Test the SMTP connection using the provided settings by the user.
    """

    try:
        email = request.data.get('email')
        password = request.data.get('password')
        # username = request.data.get('username')
        host = request.data.get('server')
        port = request.data.get('port')
        encryption_type = request.data.get('encryptionType')

        use_tls = True if encryption_type == 'tls' else False
        timeout = 2

        print('V578', email, password, host, port,
              encryption_type, use_tls, timeout)

        # return Response({'error': 'SMTP connection failed', 'details': 'SMTP connection is disabled'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Connect to the SMTP server
            if use_tls:
                server = smtplib.SMTP(host, port, timeout=timeout)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(host, port)

            # Login with provided credentials
            server.login(email, password)
            server.quit()
            return Response({"success": True, "message": "Connection successful!"}, status=status.HTTP_200_OK)

        except smtplib.SMTPException as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print('EV504', e)
        return Response({'error': 'SMTP connection failed', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST', 'DELETE'])
@permission_classes([IsAuthenticated])
def get_post_delete_user_smtp_settings(request):
    """
    Get, create,  update, delete SMTP settings for the logged-in user.
    """

    try:
        if request.method == 'GET':
            data_to_send = []
            qs_smpt_setting = SMTPSettings.objects.filter(user=request.user)

            if qs_smpt_setting.count() != 0:
                data_to_send = [
                    {'email': smtp_setting.email, 'replyToEmail': smtp_setting.reply_to_email,
                        'defaultFromName': smtp_setting.default_from_name,
                        'server': smtp_setting.server, 'port': smtp_setting.port,
                        'encryptionType': smtp_setting.encryption_type,
                     'uf': smtp_setting.uf} for smtp_setting in qs_smpt_setting]

                # print('6558', data_to_send)

            return Response(data_to_send, status=status.HTTP_200_OK)
        elif request.method == 'POST':
            user = request.user
            email = request.data.get('email')
            password = request.data.get('password')
            username = request.data.get('username')
            reply_to_email = request.data.get('replyToEmail')
            default_from_name = request.data.get('defaultFromName')
            server = request.data.get('server')
            port = request.data.get('port')
            encryption_type = request.data.get('encryptionType')

            # print('6550', user, request.data)

            smtp_setting, created = SMTPSettings.objects.update_or_create(user=user, defaults={
                'user': user, 'server': server, 'port': port, 'email': email,
                'username': username, 'key': password, 'reply_to_email': reply_to_email, 'default_from_name': default_from_name,
                'encryption_type': encryption_type})

            status_201_or_200 = status.HTTP_201_CREATED if created else status.HTTP_200_OK

            return Response({'email': smtp_setting.email, 'replyToEmail': smtp_setting.reply_to_email,
                             'defaultFromName': smtp_setting.default_from_name, 'uf': smtp_setting.uf}, status=status_201_or_200)
        elif request.method == 'DELETE':
            smtp_setting = SMTPSettings.objects.get(user=request.user)
            smtp_setting.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        else:
            return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    # Handle database integrity issues, such as unique constraint violations
    except IntegrityError as e:
        return Response({'error': 'Database error', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # Handle validation errors, such as missing or invalid data
    except ValidationError as e:
        return Response({'error': 'Invalid data', 'details': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    except SMTPSettings.DoesNotExist:
        print('EV531')
        return Response(status=status.HTTP_404_NOT_FOUND)

    # Catch any other unexpected exceptions
    except Exception as e:
        print('EV579', e)
        return Response({'error': 'Something went wrong', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
