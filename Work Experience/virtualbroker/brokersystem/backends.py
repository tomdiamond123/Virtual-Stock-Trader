# yourapp/backends.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get("email") or username
        if not email:
            return None
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None
        return user if user.check_password(password) and self.user_can_authenticate(user) else None
