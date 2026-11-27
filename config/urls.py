import posixpath

from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.views.static import serve

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('properties.urls')),
    path('', include('payments.urls')),
]

PRIVATE_MEDIA_DIRS = {'payment_proofs'}


def serve_public_media(request, path):
    """Serve uploads in development, except private folders such as payment receipts.

    Receipts are only reachable through payments:proof, which checks who is asking.
    The path is normalized first, so tricks like `x/../payment_proofs/a.png`,
    backslashes, or different letter case (Windows ignores case) can't reach them.
    """
    clean = posixpath.normpath(path.replace('\\', '/')).lstrip('/')
    if clean.split('/')[0].lower() in PRIVATE_MEDIA_DIRS:
        raise Http404('Not found')
    return serve(request, clean, document_root=settings.MEDIA_ROOT)


if settings.DEBUG:
    urlpatterns += [re_path(rf'^{settings.MEDIA_URL.lstrip("/")}(?P<path>.*)$', serve_public_media)]
