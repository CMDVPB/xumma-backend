from django.utils import translation

class ForceEnglishForApiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/api/"):
            translation.activate("en")
            request.LANGUAGE_CODE = "en"
        response = self.get_response(request)
        return response