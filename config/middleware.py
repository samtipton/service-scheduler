from django.http import Http404
from django.views.defaults import page_not_found


class FriendlyNotFoundMiddleware:
    """Show templates/404.html while DEBUG is on.

    Django's debug screen handles a missing URL before process_exception runs.
    Replacing the finished 404 response covers that screen and a view that raises Http404.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code != 404 or getattr(response, "friendly_not_found", False):
            return response
        friendly = page_not_found(request, Http404())
        friendly.friendly_not_found = True
        return friendly
