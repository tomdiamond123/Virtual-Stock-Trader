from django import forms
from .models import CustomUser
from django.contrib.auth import authenticate, get_user_model

class CustomUserCreationForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ( 'email', 'first_name', 'last_name', 'password')
        widgets = {
            'password': forms.PasswordInput(),
        }
    def save(self, commit=True):
        user = super().save(commit=False)
        raw_password = self.cleaned_data['password']
        user.set_password(raw_password)
        if commit:
            user.save()
        return user
