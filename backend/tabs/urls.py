from django.urls import path

from .views import TabCreateView, TabRepayView

urlpatterns = [
    path("", TabCreateView.as_view(), name="tab-create"),
    path("<int:pk>/payments/", TabRepayView.as_view(), name="tab-repay"),
]
