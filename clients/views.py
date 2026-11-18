from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q, Sum, Value
from django.db.models.functions import Replace
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from utilisateurs.models import JournalAudit
from utilisateurs.permissions import CAISSIER, GESTION, PHARMACIEN, role_requis

from .forms import ClientForm
from .models import Client


@role_requis(PHARMACIEN, CAISSIER, GESTION)
def client_liste(request):
    clients = Client.objects.annotate(
        tel_compact=Replace("telephone", Value(" "), Value(""))
    )

    q = request.GET.get("q", "").strip()
    if q:
        clients = clients.filter(
            Q(nom__icontains=q) | Q(tel_compact__icontains=q.replace(" ", ""))
        )

    etat = request.GET.get("etat", "actifs")
    if etat == "actifs":
        clients = clients.filter(actif=True)
    elif etat == "inactifs":
        clients = clients.filter(actif=False)

    page = Paginator(clients, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "clients/client_liste.html", {
        "page": page, "q": q, "etat": etat, "params": params.urlencode(),
    })


@role_requis(PHARMACIEN, CAISSIER, GESTION)
def client_detail(request, pk):
    client = get_object_or_404(Client.objects.select_related("cree_par"), pk=pk)
    ventes = client.ventes.all()
    return render(request, "clients/client_detail.html", {
        "c": client,
        "ventes": ventes[:20],
        "total_ventes": ventes.filter(statut="VALIDEE").aggregate(t=Sum("total"))["t"] or 0,
    })


@role_requis(PHARMACIEN, CAISSIER)
def client_creer(request):
    form = ClientForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        client = form.save(commit=False)
        client.cree_par = request.user
        client.save()
        JournalAudit.enregistrer(request.user, "CREATION", f"Client #{client.pk}", client.nom)
        messages.success(request, f"Client « {client.nom} » ajouté.")
        return redirect("client_detail", pk=client.pk)

    return render(request, "formulaire.html", {
        "form": form, "titre": "Ajouter un client", "url_retour": reverse("client_liste"),
    })


@role_requis(PHARMACIEN, CAISSIER)
def client_modifier(request, pk):
    client = get_object_or_404(Client, pk=pk)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        champs = ", ".join(form.changed_data) or "aucun"
        JournalAudit.enregistrer(request.user, "MODIFICATION", f"Client #{pk}", f"Champs modifiés : {champs}")
        messages.success(request, f"Client « {client.nom} » modifié.")
        return redirect("client_detail", pk=pk)

    return render(request, "formulaire.html", {
        "form": form, "titre": f"Modifier « {client.nom} »",
        "url_retour": reverse("client_detail", args=[pk]),
    })


@role_requis(PHARMACIEN)
@require_POST
def client_basculer_actif(request, pk):
    client = get_object_or_404(Client, pk=pk)
    client.actif = not client.actif
    client.save(update_fields=["actif"])
    action = "ACTIVATION" if client.actif else "DESACTIVATION"
    JournalAudit.enregistrer(request.user, action, f"Client #{pk}", client.nom)
    etat = "réactivé" if client.actif else "désactivé"
    messages.success(request, f"Client « {client.nom} » {etat}.")
    return redirect("client_detail", pk=pk)


@role_requis()   # administrateur uniquement
def client_supprimer(request, pk):
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST":
        nom = client.nom
        try:
            client.delete()
        except ProtectedError:
            client.actif = False
            client.save(update_fields=["actif"])
            JournalAudit.enregistrer(request.user, "DESACTIVATION", f"Client #{pk}", "Suppression refusée : historique existant")
            messages.warning(request, f"« {nom} » possède des ventes : il a été désactivé au lieu d'être supprimé.")
            return redirect("client_detail", pk=pk)

        JournalAudit.enregistrer(request.user, "SUPPRESSION", f"Client #{pk}", nom)
        messages.success(request, f"Client « {nom} » supprimé.")
        return redirect("client_liste")

    return render(request, "confirmer_suppression.html", {
        "titre": f"Supprimer le client « {client.nom} » ?",
        "message": "S'il possède déjà des ventes, il sera désactivé au lieu d'être supprimé.",
        "url_retour": reverse("client_detail", args=[pk]),
    })