from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("stock/", include("inventory.urls")),
    path("facturation/", include("billing.urls")),
    path("caisse/", include("cash.urls")),
]
