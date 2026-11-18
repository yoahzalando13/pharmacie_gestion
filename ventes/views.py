import uuid
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from medicaments.models import Medicament
from stock.models import LotStock
from stock.services import ErreurStock
from stock.views import medicaments_avec_stock
from utilisateurs.permissions import ADMIN, CAISSIER, GESTION, PHARMACIEN, a_un_role, role_requis

from .forms import AnnulationForm, RetourForm, ValidationVenteForm
from .models import Paiement, Vente
from .services import (
    VenteDejaEnregistree, annuler_vente, enregistrer_retour, valider_vente, verifier_paiement,
)

CLE_PANIER = "panier_caisse"


# ---------------------------------------------------------------- Panier (stocké en session)

def _panier(request):
    return request.session.get(CLE_PANIER, [])


def _enregistrer_panier(request, panier):
    request.session[CLE_PANIER] = panier
    request.session.modified = True


def _ajouter(request, medicament_id, quantite=1):
    panier = _panier(request)
    for article in panier:
        if article["medicament_id"] == medicament_id and article["lot_id"] is None:
            article["quantite"] += quantite
            break
    else:
        panier.append({"medicament_id": medicament_id, "lot_id": None, "quantite": quantite})
    _enregistrer_panier(request, panier)


def _panier_detaille(request):
    """Le panier avec les objets, les lots vendables proposés (ordre FEFO) et les sous-totaux."""
    lignes, total = [], Decimal("0")
    for index, article in enumerate(_panier(request)):
        medicament = Medicament.objects.filter(pk=article["medicament_id"]).first()
        if medicament is None:
            continue
        lots = list(LotStock.objects.vendables().filter(medicament=medicament).order_by("date_peremption", "pk"))
        disponible = sum(l.quantite for l in lots)
        if article["lot_id"]:
            lot_choisi = next((l for l in lots if l.pk == article["lot_id"]), None)
            disponible_ligne = lot_choisi.quantite if lot_choisi else 0
        else:
            disponible_ligne = disponible
        sous_total = article["quantite"] * medicament.prix_vente
        total += sous_total
        lignes.append({
            "index": index, "medicament": medicament, "lots": lots,
            "lot_id": article["lot_id"], "quantite": article["quantite"],
            "disponible": disponible_ligne, "sous_total": sous_total,
            "insuffisant": article["quantite"] > disponible_ligne,
        })
    return lignes, total


# ---------------------------------------------------------------- Caisse

@role_requis(CAISSIER, PHARMACIEN)
def caisse(request):
    if request.method == "POST":
        action = request.POST.get("action", "")
        panier = _panier(request)

        if action == "ajouter":
            try:
                medicament_id = int(request.POST.get("medicament_id"))
                quantite = max(int(request.POST.get("quantite") or 1), 1)
            except (TypeError, ValueError):
                messages.error(request, "Article invalide.")
            else:
                _ajouter(request, medicament_id, quantite)
            return redirect("caisse")

        if action == "modifier":
            try:
                index = int(request.POST.get("index"))
                quantite = int(request.POST.get("quantite") or 0)
                lot_brut = request.POST.get("lot_id") or ""
                lot_id = int(lot_brut) if lot_brut else None
                article = panier[index]
            except (TypeError, ValueError, IndexError):
                messages.error(request, "Ligne introuvable.")
            else:
                if quantite <= 0:
                    messages.error(request, "La quantité doit être strictement positive (RG03).")
                else:
                    article["quantite"] = quantite
                    article["lot_id"] = lot_id
                    _enregistrer_panier(request, panier)
            return redirect("caisse")

        if action == "retirer":
            try:
                panier.pop(int(request.POST.get("index")))
            except (TypeError, ValueError, IndexError):
                pass
            _enregistrer_panier(request, panier)
            return redirect("caisse")

        if action == "vider":
            _enregistrer_panier(request, [])
            return redirect("caisse")

        if action == "valider":
            form = ValidationVenteForm(request.POST)
            jeton = request.POST.get("jeton", "")
            if form.is_valid():
                try:
                    vente = valider_vente(
                        panier, request.user, jeton,
                        mode=form.cleaned_data["mode"],
                        montant_recu=form.cleaned_data["montant_recu"],
                        reference=form.cleaned_data["reference"],
                        client=form.cleaned_data["client"],
                    )
                except (VenteDejaEnregistree, IntegrityError):
                    messages.warning(request, "Cette vente a déjà été enregistrée : la double validation a été bloquée.")
                    _enregistrer_panier(request, [])
                    return redirect("vente_liste")
                except ErreurStock as e:
                    messages.error(request, str(e))
                else:
                    _enregistrer_panier(request, [])
                    messages.success(request, f"Vente {vente.numero} enregistrée — {vente.total:,.0f} Ar.".replace(",", " "))
                    return redirect("vente_detail", pk=vente.pk)
            lignes, total = _panier_detaille(request)
            return render(request, "ventes/caisse.html", {
                "lignes": lignes, "total": total, "form": form,
                "jeton": uuid.uuid4().hex, "resultats": None, "q": "",
            })

    # ---- Recherche (nom, DCI ou code-barres scanné)
    q = request.GET.get("q", "").strip()
    resultats = None
    if q:
        actifs = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF)
        exact = actifs.filter(code_barres=q).first()
        if exact:
            # Un code-barres scanné ajoute directement l'article au panier
            _ajouter(request, exact.pk, 1)
            messages.info(request, f"« {exact} » ajouté au panier.")
            return redirect("caisse")
        resultats = actifs.filter(Q(nom__icontains=q) | Q(dci__icontains=q)).order_by("nom")[:15]

    lignes, total = _panier_detaille(request)
    return render(request, "ventes/caisse.html", {
        "lignes": lignes, "total": total, "form": ValidationVenteForm(),
        "jeton": uuid.uuid4().hex, "resultats": resultats, "q": q,
    })


# ---------------------------------------------------------------- Historique des ventes

@role_requis(CAISSIER, PHARMACIEN, GESTION)
def vente_liste(request):
    ventes = Vente.objects.select_related("client", "vendeur")

    q = request.GET.get("q", "").strip()
    if q:
        ventes = ventes.filter(Q(numero__icontains=q) | Q(client__nom__icontains=q))
    statut = request.GET.get("statut", "")
    if statut in Vente.Statut.values:
        ventes = ventes.filter(statut=statut)
    du, au = parse_date(request.GET.get("du", "") or ""), parse_date(request.GET.get("au", "") or "")
    if du:
        ventes = ventes.filter(date__date__gte=du)
    if au:
        ventes = ventes.filter(date__date__lte=au)

    page = Paginator(ventes, 20).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "ventes/vente_liste.html", {
        "page": page, "q": q, "statut": statut, "statuts": Vente.Statut.choices,
        "du": request.GET.get("du", ""), "au": request.GET.get("au", ""), "params": params.urlencode(),
    })


@role_requis(CAISSIER, PHARMACIEN, GESTION)
def vente_detail(request, pk):
    vente = get_object_or_404(
        Vente.objects.select_related("client", "vendeur", "annule_par"), pk=pk
    )
    return render(request, "ventes/vente_detail.html", {
        "vente": vente,
        "lignes": vente.lignes.select_related("medicament", "lot"),
        "paiements": vente.paiements.select_related("enregistre_par", "verifie_par"),
        "retours": vente.retours.select_related("ligne__medicament", "utilisateur"),
        "peut_retour": a_un_role(request.user, ADMIN, PHARMACIEN, CAISSIER) and vente.statut == Vente.Statut.VALIDEE,
        "peut_annuler": a_un_role(request.user, ADMIN, PHARMACIEN) and vente.statut == Vente.Statut.VALIDEE
                        and not vente.retours.exists(),
        "peut_verifier": a_un_role(request.user, ADMIN, PHARMACIEN, CAISSIER),
        "form_annulation": AnnulationForm(),
    })


# ---------------------------------------------------------------- Retours, annulations, paiements

@role_requis(PHARMACIEN, CAISSIER)
def retour_creer(request, pk):
    vente = get_object_or_404(Vente, pk=pk)
    if vente.statut != Vente.Statut.VALIDEE:
        messages.error(request, "Un retour n'est possible que sur une vente validée.")
        return redirect("vente_detail", pk=pk)

    form = RetourForm(request.POST or None, vente=vente)
    if not form.fields["ligne"].choices:
        messages.info(request, "Tous les articles de cette vente ont déjà été retournés.")
        return redirect("vente_detail", pk=pk)

    if request.method == "POST" and form.is_valid():
        try:
            retour = enregistrer_retour(
                int(form.cleaned_data["ligne"]), form.cleaned_data["quantite"], form.cleaned_data["motif"],
                form.cleaned_data["remis_en_stock"], request.user, form.cleaned_data["mode_remboursement"],
            )
        except ErreurStock as e:
            form.add_error(None, str(e))
        else:
            messages.success(
                request,
                f"Retour {retour.numero} enregistré — {retour.montant_rembourse:,.0f} Ar à rembourser.".replace(",", " "),
            )
            return redirect("vente_detail", pk=pk)

    return render(request, "formulaire.html", {
        "form": form, "titre": f"Retour sur la vente {vente.numero}",
        "aide": "Le retour est une opération compensatoire : la vente d'origine reste dans l'historique.",
        "url_retour": reverse("vente_detail", args=[pk]),
    })


@role_requis(PHARMACIEN)
@require_POST
def vente_annuler(request, pk):
    form = AnnulationForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Le motif d'annulation est obligatoire.")
        return redirect("vente_detail", pk=pk)
    try:
        vente = annuler_vente(pk, request.user, form.cleaned_data["motif"])
    except ErreurStock as e:
        messages.error(request, str(e))
    else:
        messages.warning(request, f"Vente {vente.numero} annulée. Le stock a été réintégré.")
    return redirect("vente_detail", pk=pk)


@role_requis(PHARMACIEN, CAISSIER)
@require_POST
def paiement_verifier(request, pk):
    paiement = get_object_or_404(Paiement, pk=pk)
    accepte = request.POST.get("decision") == "confirmer"
    try:
        verifier_paiement(pk, request.user, accepte, request.POST.get("reference", ""))
    except ErreurStock as e:
        messages.error(request, str(e))
    else:
        messages.success(request, "Paiement confirmé." if accepte else "Paiement rejeté.")
    return redirect("vente_detail", pk=paiement.vente_id)

