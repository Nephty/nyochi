import logging

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView, LogoutView

from . import throttle

log = logging.getLogger("nyochi.auth")


class NyochiLoginView(LoginView):
    """The only way in. Accounts are shared with Shopping and created in the Django admin: there is no signup."""

    template_name = "accounts/login.html"
    authentication_form = AuthenticationForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        self._ip = throttle.client_ip(request)
        self._username = (request.POST.get("username") or "").strip()
        wait = throttle.retry_after("login", self._ip, self._username)
        if wait:
            log.warning("login throttled user=%r ip=%s retry_after=%ss", self._username, self._ip, wait)
            return self.render_to_response(
                self.get_context_data(form=self.get_form(), throttle_error=throttle.wait_message(wait)), status=429,
            )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        throttle.record("login", self._ip, self._username, True)
        log.info("login ok user=%r ip=%s", self._username, self._ip)
        return super().form_valid(form)

    def form_invalid(self, form):
        throttle.record("login", self._ip, self._username, False)
        log.warning("login failed user=%r ip=%s", self._username, self._ip)
        return super().form_invalid(form)
