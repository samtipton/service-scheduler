from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        protected = (
            request.path.startswith("/schedules/")
            or request.path.startswith("/messages/")
            or request.path.startswith("/account/")
            or request.path.startswith("/groups/")
        )
        if protected and not request.user.is_authenticated:
            # Exclude the login/logout URLs
            if not any(
                request.path.startswith(p)
                for p in ["/accounts/login/", "/accounts/logout/"]
            ):
                # Save the requested URL for redirect after login
                return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        return self.get_response(request)
