from django.contrib.auth import login
from django.shortcuts import redirect, render
from django.views import View

from .forms import RegisterForm


class RegisterView(View):
    template_name = 'accounts/register.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('recipe-list')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {'form': RegisterForm()})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('recipe-list')
        return render(request, self.template_name, {'form': form})
