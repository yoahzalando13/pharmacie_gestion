from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from rapports.views import tableau_de_bord

urlpatterns = [
    path("", tableau_de_bord, name="tableau_de_bord"),
    path("admin/", admin.site.urls),
    path("compte/", include("utilisateurs.urls")),
    path("medicaments/", include("medicaments.urls")),
    path("fournisseurs/", include("fournisseurs.urls")),
    path("clients/", include("clients.urls")),
    path("achats/", include("achats.urls")),
    path("stock/", include("stock.urls")),
    path("ventes/", include("ventes.urls")),
    path("rapports/", include("rapports.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
