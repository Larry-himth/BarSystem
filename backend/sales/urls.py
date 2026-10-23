from django.urls import path

from .views import SaleCreateView, SaleVoidView

urlpatterns = [
    path("", SaleCreateView.as_view(), name="sale-create"),
    path("<int:pk>/void/", SaleVoidView.as_view(), name="sale-void"),
]
