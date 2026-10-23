from django.urls import path

from .views import StockMovementCreateView

urlpatterns = [
    path("", StockMovementCreateView.as_view(), name="stock-movement-create"),
]
