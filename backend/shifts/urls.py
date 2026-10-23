from django.urls import path

from .views import OpenShiftView

urlpatterns = [
    path("open/", OpenShiftView.as_view(), name="open-shift"),
]
