from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from medicaments.models import Categorie, Medicament
from utilisateurs.permissions import CAISSIER, GESTION, PHARMACIEN, STOCK, role_requis

from .forms import BlocageForm, CorrectionForm
from .models import LotStock, MouvementStock
from .services import ErreurStock, basculer_blocage, corriger_stock, enregistrer_inventaire


def filtre_vendable(prefixe="lots__"):
    """Condition « lot vendable » utilisable dans une agrégation."""
    return Q(**{
        f"{prefixe}quantite__gt": 0,
        f"{prefixe}bloque": False,
        f"{prefixe}date_peremption__gte": timezone.localdate(),
    })


def medicaments_avec_stock():
    """Médicaments annotés avec leur stock total et leur stock vendable (calculés depuis les lots)."""
    zero = Value(0, output_field=IntegerField())
    return Medicament.objects.select_related("categorie").annotate(
        stock_total_calc=Coalesce(Sum("lots__quantite"), zero),
        stock_vendable_calc=Coalesce(Sum("lots__quantite", filter=filtre_vendable()), zero),
    )


def _params(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


# ---------------------------------------------------------------- État du stock

@role_requis(PHARMACIEN, STOCK, CAISSIER, GESTION)
def stock_liste(request):
    medicaments = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF)

    q = request.GET.get("q", "").strip()
    if q:
        medicaments = medicaments.filter(Q(nom__icontains=q) | Q(dci__icontains=q) | Q(code_barres=q))

    categorie_id = request.GET.get("categorie", "")
    if categorie_id.isdigit():
        medicaments = medicaments.filter(categorie_id=categorie_id)

    etat = request.GET.get("etat", "")
    if etat == "rupture":
        medicaments = medicaments.filter(stock_vendable_calc=0)
    elif etat == "faible":
        medicaments = medicaments.filter(stock_vendable_calc__gt=0, stock_vendable_calc__lte=F("seuil_alerte"))
    elif etat == "ok":
        medicaments = medicaments.filter(stock_vendable_calc__gt=F("seuil_alerte"))

    medicaments = medicaments.order_by("nom")
    page = Paginator(medicaments, 20).get_page(request.GET.get("page"))
    return render(request, "stock/stock_liste.html", {
        "page": page, "q": q, "etat": etat, "categorie_id": categorie_id,
        "categories": Categorie.objects.all(), "params": _params(request),
    })


@role_requis(PHARMACIEN, STOCK, CAISSIER, GESTION)
def stock_medicament(request, pk):
    medicament = get_object_or_404(Medicament.objects.select_related("categorie"), pk=pk)
    lots = medicament.lots.all().order_by("date_peremption", "pk")
    mouvements = MouvementStock.objects.filter(lot__medicament=medicament).select_related("lot", "utilisateur")[:30]
    return render(request, "stock/stock_medicament.html", {
        "m": medicament, "lots": lots, "mouvements": mouvements,
    })


@role_requis(PHARMACIEN, STOCK, GESTION)
def alertes(request):
    aujourd_hui = timezone.localdate()
    meds = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF)
    return render(request, "stock/alertes.html", {
        "ruptures": meds.filter(stock_vendable_calc=0).order_by("nom"),
        "faibles": meds.filter(stock_vendable_calc__gt=0, stock_vendable_calc__lte=F("seuil_alerte")).order_by("stock_vendable_calc"),
        "perimes": LotStock.objects.perimes().filter(quantite__gt=0).select_related("medicament"),
        "proches": LotStock.objects.proches_peremption().filter(quantite__gt=0).select_related("medicament"),
        "bloques": LotStock.objects.filter(bloque=True, quantite__gt=0).select_related("medicament"),
        "aujourd_hui": aujourd_hui,
    })


# ---------------------------------------------------------------- Mouvements

@role_requis(PHARMACIEN, STOCK, GESTION)
def mouvement_liste(request):
    mouvements = MouvementStock.objects.select_related("lot__medicament", "utilisateur")

    q = request.GET.get("q", "").strip()
    if q:
        mouvements = mouvements.filter(
            Q(lot__medicament__nom__icontains=q) | Q(lot__numero_lot__icontains=q) | Q(reference__icontains=q)
        )
    type_mvt = request.GET.get("type", "")
    if type_mvt in MouvementStock.Type.values:
        mouvements = mouvements.filter(type=type_mvt)
    du, au = parse_date(request.GET.get("du", "") or ""), parse_date(request.GET.get("au", "") or "")
    if du:
        mouvements = mouvements.filter(date__date__gte=du)
    if au:
        mouvements = mouvements.filter(date__date__lte=au)

    page = Paginator(mouvements, 25).get_page(request.GET.get("page"))
    return render(request, "stock/mouvement_liste.html", {
        "page": page, "q": q, "type": type_mvt, "types": MouvementStock.Type.choices,
        "du": request.GET.get("du", ""), "au": request.GET.get("au", ""), "params": _params(request),
    })


# ---------------------------------------------------------------- Corrections, blocage, inventaire

@role_requis(PHARMACIEN, STOCK)
def correction_creer(request, lot_pk):
    lot = get_object_or_404(LotStock.objects.select_related("medicament"), pk=lot_pk)
    form = CorrectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            corriger_stock(lot.pk, form.cleaned_data["type"], form.cleaned_data["quantite"],
                           form.cleaned_data["motif"], request.user)
        except ErreurStock as e:
            form.add_error(None, str(e))
        else:
            messages.success(request, f"Correction enregistrée sur le lot {lot.numero_lot}.")
            return redirect("stock_medicament", pk=lot.medicament_id)

    return render(request, "formulaire.html", {
        "form": form,
        "titre": f"Corriger le stock — {lot.medicament}, lot {lot.numero_lot}",
        "aide": f"Quantité actuelle du lot : {lot.quantite}. Chaque correction est tracée dans l'historique des mouvements.",
        "url_retour": reverse("stock_medicament", args=[lot.medicament_id]),
    })


@role_requis(PHARMACIEN)
@require_POST
def lot_basculer_blocage(request, lot_pk):
    lot = get_object_or_404(LotStock, pk=lot_pk)
    form = BlocageForm(request.POST)
    form.is_valid()
    try:
        lot = basculer_blocage(lot.pk, request.user, form.cleaned_data.get("motif", ""))
    except ErreurStock as e:
        messages.error(request, str(e))
    else:
        messages.success(request, f"Lot {lot.numero_lot} {'bloqué' if lot.bloque else 'débloqué'}.")
    return redirect("stock_medicament", pk=lot.medicament_id)


@role_requis(PHARMACIEN, STOCK)
def inventaire(request):
    lots = LotStock.objects.select_related("medicament").filter(
        Q(quantite__gt=0) | Q(date_creation__date__gte=timezone.localdate())
    ).order_by("medicament__nom", "date_peremption")
    categorie_id = request.GET.get("categorie", "")
    if categorie_id.isdigit():
        lots = lots.filter(medicament__categorie_id=categorie_id)

    if request.method == "POST":
        comptages = {}
        erreurs = False
        for lot in lots:
            valeur = request.POST.get(f"lot_{lot.pk}", "").strip()
            if valeur == "":
                continue
            try:
                comptages[lot.pk] = int(valeur)
            except ValueError:
                erreurs = True
        if erreurs:
            messages.error(request, "Certaines quantités ne sont pas des nombres entiers.")
        elif not comptages:
            messages.warning(request, "Aucune quantité comptée n'a été saisie.")
        else:
            reference = f"INV-{timezone.localtime():%Y%m%d-%H%M}"
            try:
                mouvements = enregistrer_inventaire(
                    comptages, request.POST.get("motif", "").strip() or "Inventaire physique",
                    request.user, reference,
                )
            except ErreurStock as e:
                messages.error(request, str(e))
            else:
                messages.success(request, f"Inventaire {reference} enregistré : {len(mouvements)} écart(s) corrigé(s).")
                return redirect("mouvement_liste")

    return render(request, "stock/inventaire.html", {
        "lots": lots, "categories": Categorie.objects.all(), "categorie_id": categorie_id,
    })
