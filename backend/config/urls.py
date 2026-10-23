"""
URL configuration for Bar POS backend.
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health_check(request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok", "service": "bar-pos-api"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health_check, name="health_check"),
    path("api/v1/auth/", include("users.urls")),
    path("api/v1/shifts/", include("shifts.urls")),
    path("api/v1/sales/", include("sales.urls")),
    path("api/v1/stock-movements/", include("stock.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
