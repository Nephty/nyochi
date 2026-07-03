from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import RegexValidator

_lowercase_only = RegexValidator(
    regex=r'^[a-z]+$',
    message='Username may only contain lowercase letters a–z.',
)


class RegisterForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        validators=[_lowercase_only],
    )
