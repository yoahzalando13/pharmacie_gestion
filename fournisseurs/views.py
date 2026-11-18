from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import DecimalField, F, ProtectedError, Q, Sum, Value
from django.db.models.functions import Replace
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from achats.models import LigneAchat, LigneReception
from utilisateurs.models import JournalAudit
from utilisateurs.permissions import GESTION, PHARMACIEN, STOCK, role_requis

from .forms import FournisseurForm
from .models import Fournisseur


@role_requis(PHARMACIEN, STOCK, GESTION)
def fournisseur_liste(request):
    # On crée une version du téléphone sans espaces pour que
    # "0341234567" trouve aussi "034 12 345 67"
    fournisseurs = Fournisseur.objects.annotate(
        tel_compact=Replace("telephone", Value(" "), Value(""))
    )

    q = request.GET.get("q", "").strip()
    if q:
        fournisseurs = fournisseurs.filter(
            Q(nom__icontains=q)
            | Q(contact_principal__icontains=q)
            | Q(tel_compact__icontains=q.replace(" ", ""))
        )

    etat = request.GET.get("etat", "actifs")
    if etat == "actifs":
        fournisseurs = fournisseurs.filter(actif=True)
    elif etat == "inactifs":
        fournisseurs = fournisseurs.filter(actif=False)

    page = Paginator(fournisseurs, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "fournisseurs/fournisseur_liste.html", {
        "page": page, "q": q, "etat": etat, "params": params.urlencode(),
    })


@role_requis(PHARMACIEN, STOCK, GESTION)
def fournisseur_detail(request, pk):
    fournisseur = get_object_or_404(Fournisseur.objects.select_related("cree_par"), pk=pk)
    montant = DecimalField(max_digits=16, decimal_places=2)
    commandes = fournisseur.commandes.annotate(
        total_calc=Sum(F("lignes__quantite_commandee") * F("lignes__prix_achat"), output_field=montant)
    ).order_by("-date_creation")
    montant_commande = LigneAchat.objects.filter(commande__fournisseur=fournisseur).exclude(
        commande__statut__in=["BROUILLON", "ANNULEE"]
    ).aggregate(t=Sum(F("quantite_commandee") * F("prix_achat"), output_field=montant))["t"] or 0
    montant_recu = LigneReception.objects.filter(reception__commande__fournisseur=fournisseur).aggregate(
        t=Sum(F("quantite") * F("prix_achat"), output_field=montant)
    )["t"] or 0
    return render(request, "fournisseurs/fournisseur_detail.html", {
        "f": fournisseur, "commandes": commandes[:20],
        "montant_commande": montant_commande, "montant_recu": montant_recu,
    })


@role_requis(PHARMACIEN, STOCK)
def fournisseur_creer(request):
    form = FournisseurForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        fournisseur = form.save(commit=False)
        fournisseur.cree_par = request.user
        fournisseur.save()
        JournalAudit.enregistrer(request.user, "CREATION", f"Fournisseur #{fournisseur.pk}", fournisseur.nom)
        messages.success(request, f"Fournisseur « {fournisseur} » ajouté.")
        return redirect("fournisseur_detail", pk=fournisseur.pk)

    return render(request, "formulaire.html", {
        "form": form, "titre": "Ajouter un fournisseur", "url_retour": reverse("fournisseur_liste"),
    })


@role_requis(PHARMACIEN, STOCK)
def fournisseur_modifier(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    form = FournisseurForm(request.POST or None, instance=fournisseur)
    if request.method == "POST" and form.is_valid():
        form.save()
        champs = ", ".join(form.changed_data) or "aucun"
        JournalAudit.enregistrer(request.user, "MODIFICATION", f"Fournisseur #{pk}", f"Champs modifiés : {champs}")
        messages.success(request, f"Fournisseur « {fournisseur} » modifié.")
        return redirect("fournisseur_detail", pk=pk)

    return render(request, "formulaire.html", {
        "form": form, "titre": f"Modifier « {fournisseur} »",
        "url_retour": reverse("fournisseur_detail", args=[pk]),
    })


@role_requis(PHARMACIEN, STOCK)
@require_POST
def fournisseur_basculer_actif(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    fournisseur.actif = not fournisseur.actif
    fournisseur.save(update_fields=["actif"])
    action = "ACTIVATION" if fournisseur.actif else "DESACTIVATION"
    JournalAudit.enregistrer(request.user, action, f"Fournisseur #{pk}", fournisseur.nom)
    etat = "réactivé" if fournisseur.actif else "désactivé"
    messages.success(request, f"Fournisseur « {fournisseur} » {etat}.")
    return redirect("fournisseur_detail", pk=pk)


@role_requis()   # administrateur uniquement
def fournisseur_supprimer(request, pk):
    fournisseur = get_object_or_404(Fournisseur, pk=pk)
    if request.method == "POST":
        nom = fournisseur.nom
        try:
            fournisseur.delete()
        except ProtectedError:
            fournisseur.actif = False
            fournisseur.save(update_fields=["actif"])
            JournalAudit.enregistrer(request.user, "DESACTIVATION", f"Fournisseur #{pk}", "Suppression refusée : historique existant")
            messages.warning(request, f"« {nom} » possède des achats : il a été désactivé au lieu d'être supprimé.")
            return redirect("fournisseur_detail", pk=pk)

        JournalAudit.enregistrer(request.user, "SUPPRESSION", f"Fournisseur #{pk}", nom)
        messages.success(request, f"Fournisseur « {nom} » supprimé.")
        return redirect("fournisseur_liste")

    return render(request, "confirmer_suppression.html", {
        "titre": f"Supprimer le fournisseur « {fournisseur} » ?",
        "message": "S'il possède déjà des achats, il sera désactivé au lieu d'être supprimé.",
        "url_retour": reverse("fournisseur_detail", args=[pk]),
    })