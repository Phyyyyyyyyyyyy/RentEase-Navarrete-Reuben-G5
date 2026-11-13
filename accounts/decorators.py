from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`.

    Logged-out users go to the login page (via @login_required). Logged-in
    users with the wrong role are sent back to their own dashboard, so typing
    another role's dashboard URL never shows that dashboard.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission to open that page.')
                return redirect(request.user.dashboard_url_name)
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
