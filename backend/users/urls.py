from django.urls import path

from .views import LoginView, MeView, PinLoginView

urlpatterns = [
    path("login/", PinLoginView.as_view(), name="pin-login"),
    path("me/", MeView.as_view(), name="me"),
]
