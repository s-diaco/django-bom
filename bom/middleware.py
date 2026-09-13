from django.utils import translation

class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            try:
                profile = request.user.bom_profile()
                if profile and profile.language:
                    translation.activate(profile.language)
            except Exception:
                pass

        response = self.get_response(request)
        return response
