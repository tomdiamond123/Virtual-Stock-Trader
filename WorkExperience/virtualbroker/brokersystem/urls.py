from django.urls import path
from brokersystem import views
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.SignUp.as_view(), name="signup"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("trade/", views.trade_view, name="trade")
]

urlpatterns += staticfiles_urlpatterns()