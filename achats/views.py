import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import DecimalField, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from stock.services import ErreurStock
from utilisateurs.models import JournalAudit
from utilisateurs.permissions import ADMIN, GESTION, PHARMACIEN, STOCK, a_un_role, role_requis

from .forms import CommandeForm, LigneAchatForm, LigneReceptionFormSet
from .models import CommandeAchat, LigneAchat, ReceptionAchat
from .services import ReceptionDejaEnregistree, annuler_commande, receptionner, valider_commande


# ---------------------------------------------------------------- Commandes

@role_requis(PHARMACIEN, STOCK, GESTION)
def commande_liste(request):
    commandes = CommandeAchat.objects.select_related("fournisseur").annotate(
        total_calc=Sum(
            F("lignes__quantite_commandee") * F("lignes__prix_achat"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    ).order_by("-date_creation")

    q = request.GET.get("q", "").strip()
    if q:
        commandes = commandes.filter(Q(numero__icontains=q) | Q(fournisseur__nom__icontains=q))

    statut = request.GET.get("statut", "")
    if statut in CommandeAchat.Statut.values:
        commandes = commandes.filter(statut=statut)

    page = Paginator(commandes, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(request, "achats/commande_liste.html", {
        "page": page, "q": q, "statut": statut,
        "statuts": CommandeAchat.Statut.choices, "params": params.urlencode(),
    })


@role_requis(PHARMACIEN, STOCK)
def commande_creer(request):
    form = CommandeForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        commande = form.save(commit=False)
        commande.cree_par = request.user
        commande.save()
        JournalAudit.enregistrer(request.user, "CREATION", f"Commande {commande.numero}", str(commande.fournisseur))
        messages.success(request, f"Commande {commande.numero} créée. Ajoutez maintenant les médicaments.")
        return redirect("commande_detail", pk=commande.pk)

    return render(request, "formulaire.html", {
        "form": form, "titre": "Nouvelle commande d'achat", "url_retour": reverse("commande_liste"),
    })


@role_requis(PHARMACIEN, STOCK, GESTION)
def commande_detail(request, pk):
    commande = get_object_or_404(
        CommandeAchat.objects.select_related("fournisseur", "cree_par", "valide_par", "annule_par"), pk=pk
    )
    peut_gerer = a_un_role(request.user, ADMIN, PHARMACIEN, STOCK)

    # Formulaire d'ajout de ligne : seulement en brouillon et pour les rôles autorisés
    form = None
    if commande.est_modifiable and peut_gerer:
        form = LigneAchatForm(request.POST or None, commande=commande)
        if request.method == "POST" and form.is_valid():
            ligne = form.save(commit=False)
            ligne.commande = commande
            ligne.save()
            messages.success(request, f"« {ligne.medicament} » ajouté à la commande.")
            return redirect("commande_detail", pk=pk)
    elif request.method == "POST":
        messages.error(request, "Cette commande ne peut plus être modifiée.")
        return redirect("commande_detail", pk=pk)

    return render(request, "achats/commande_detail.html", {
        "commande": commande,
        "lignes": commande.lignes.select_related("medicament"),
        "receptions": commande.receptions.select_related("recu_par"),
        "total": commande.total,
        "form": form,
        "peut_gerer": peut_gerer,
    })


@role_requis(PHARMACIEN, STOCK)
@require_POST
def ligne_supprimer(request, pk, ligne_pk):
    commande = get_object_or_404(CommandeAchat, pk=pk)
    if not commande.est_modifiable:
        messages.error(request, "Cette commande ne peut plus être modifiée.")
        return redirect("commande_detail", pk=pk)
    ligne = get_object_or_404(LigneAchat, pk=ligne_pk, commande=commande)
    nom = str(ligne.medicament)
    ligne.delete()
    messages.success(request, f"« {nom} » retiré de la commande.")
    return redirect("commande_detail", pk=pk)


@role_requis(PHARMACIEN, STOCK)
@require_POST
def commande_valider(request, pk):
    try:
        commande = valider_commande(pk, request.user)
    except ErreurStock as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"Commande {commande.numero} validée.")
    return redirect("commande_detail", pk=pk)


@role_requis(PHARMACIEN, STOCK)
@require_POST
def commande_annuler(request, pk):
    try:
        commande = annuler_commande(pk, request.user)
    except ErreurStock as e:
        messages.error(request, str(e))
    else:
        messages.warning(request, f"Commande {commande.numero} annulée.")
    return redirect("commande_detail", pk=pk)


# ---------------------------------------------------------------- Réceptions

@role_requis(PHARMACIEN, STOCK)
def reception_creer(request, pk):
    commande = get_object_or_404(CommandeAchat.objects.select_related("fournisseur"), pk=pk)
    if not commande.peut_etre_receptionnee:
        messages.error(request, "Cette commande ne peut pas être réceptionnée.")
        return redirect("commande_detail", pk=pk)

    lignes = [l for l in commande.lignes.select_related("medicament") if l.reste_a_recevoir > 0]

    if request.method == "POST":
        formset = LigneReceptionFormSet(request.POST)
        jeton = request.POST.get("jeton", "")
        note = request.POST.get("note", "").strip()

        if formset.is_valid():
            try:
                reception = receptionner(commande.pk, formset.cleaned_data, request.user, jeton, note)
            except (ReceptionDejaEnregistree, IntegrityError):
                messages.warning(request, "Cette réception a déjà été enregistrée : le double envoi a été bloqué.")
                return redirect("commande_detail", pk=pk)
            except ErreurStock as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"Réception {reception.numero} enregistrée. Le stock a été mis à jour.")
                return redirect("reception_detail", pk=reception.pk)
    else:
        formset = LigneReceptionFormSet(initial=[
            {"ligne_id": l.pk, "quantite": l.reste_a_recevoir} for l in lignes
        ])
        jeton = uuid.uuid4().hex
        note = ""

    return render(request, "achats/reception_form.html", {
        "commande": commande,
        "formset": formset,
        "lignes_formulaires": list(zip(lignes, formset.forms)),
        "jeton": jeton,
        "note": note,
    })


@role_requis(PHARMACIEN, STOCK, GESTION)
def reception_detail(request, pk):
    reception = get_object_or_404(
        ReceptionAchat.objects.select_related("commande__fournisseur", "recu_par"), pk=pk
    )
    return render(request, "achats/reception_detail.html", {
        "reception": reception,
        "lignes": reception.lignes.select_related("ligne_achat__medicament", "lot"),
    })