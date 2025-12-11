from django.contrib.auth.tokens import default_token_generator
from djoser import utils
from djoser.conf import settings
from djoser.email import ActivationEmail, PasswordResetEmail, PasswordChangedConfirmationEmail


class ActivationEmail(ActivationEmail):
    template_name = 'drf/activation.html'

    def get_context_data(self):
        context = super().get_context_data()

        user = context.get("user")
        context["uid"] = utils.encode_uid(user.pk)
        context["token"] = default_token_generator.make_token(user)
        context["url"] = settings.ACTIVATION_URL.format(**context)
        context["lang"] = user.lang
        return context


class PasswordResetEmail(PasswordResetEmail):
    template_name = 'drf/password_reset.html'

    def get_context_data(self):
        context = super().get_context_data()

        user = context.get("user")
        context["uid"] = utils.encode_uid(user.pk)
        context["token"] = default_token_generator.make_token(user)
        context["url"] = settings.PASSWORD_RESET_CONFIRM_URL.format(**context)
        context["lang"] = user.lang
        return context


class PasswordChangedConfirmationEmail(PasswordChangedConfirmationEmail):
    template_name = "drf/password_changed_confirmation.html"

    def get_context_data(self):
        context = super().get_context_data()

        user = context.get("user")
        context["uid"] = utils.encode_uid(user.pk)
        context["token"] = default_token_generator.make_token(user)
        context["url"] = settings.PASSWORD_RESET_CONFIRM_URL.format(**context)
        context["lang"] = user.lang
        return context
