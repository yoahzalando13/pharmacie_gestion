from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import TruncDate
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.dateparse import parse_date

from achats.models import CommandeAchat, LigneReception, ReceptionAchat
from medicaments.models import Medicament
from stock.models import LotStock
from stock.views import medicaments_avec_stock
from utilisateurs.permissions import (
    ADMIN, CAISSIER, GESTION, PHARMACIEN, STOCK, a_un_role, role_requis,
)
from ventes.models import LigneVente, ModePaiement, Paiement, RetourVente, Vente

from . import pdf

MONTANT = DecimalField(max_digits=16, decimal_places=2)
ZERO = Decimal("0")


# ---------------------------------------------------------------- Calculs partagés

def periode(request, jours_defaut=30):
    """Lit ?du=AAAA-MM-JJ&au=AAAA-MM-JJ, ou ?jours=7. Par défaut : les 30 derniers jours."""
    aujourd_hui = timezone.localdate()
    au = parse_date(request.GET.get("au", "") or "") or aujourd_hui
    du = parse_date(request.GET.get("du", "") or "")
    if du is None:
        try:
            jours = max(1, min(int(request.GET.get("jours", jours_defaut)), 366))
        except ValueError:
            jours = jours_defaut
        du = au - timedelta(days=jours - 1)
    if du > au:
        du, au = au, du
    return du, au


def statistiques(du, au):
    """
    Indicateurs de la période. Le chiffre d'affaires, les encaissements et la marge
    sont volontairement distingués (§4.10) : la marge n'est PAS un bénéfice net.
    """
    ventes = Vente.objects.filter(statut=Vente.Statut.VALIDEE, date__date__range=(du, au))
    lignes = LigneVente.objects.filter(vente__in=ventes)
    retours = RetourVente.objects.filter(vente__statut=Vente.Statut.VALIDEE, date__date__range=(du, au))

    total_ventes = ventes.aggregate(t=Sum("total"))["t"] or ZERO
    total_retours = retours.aggregate(t=Sum("montant_rembourse"))["t"] or ZERO
    marge_ventes = lignes.aggregate(
        t=Sum(F("quantite") * (F("prix_unitaire") - F("cout_unitaire")), output_field=MONTANT))["t"] or ZERO
    marge_retours = retours.aggregate(
        t=Sum(F("quantite") * (F("ligne__prix_unitaire") - F("ligne__cout_unitaire")), output_field=MONTANT))["t"] or ZERO
    encaissements = Paiement.objects.filter(
        statut=Paiement.Statut.CONFIRME, date__date__range=(du, au), vente__statut=Vente.Statut.VALIDEE,
    ).aggregate(t=Sum("montant"))["t"] or ZERO

    receptions = ReceptionAchat.objects.filter(date_reception__date__range=(du, au))
    total_achats = LigneReception.objects.filter(reception__in=receptions).aggregate(
        t=Sum(F("quantite") * F("prix_achat"), output_field=MONTANT))["t"] or ZERO

    return {
        "nb_ventes": ventes.count(),
        "chiffre_affaires": total_ventes - total_retours,
        "retours": total_retours,
        "encaissements": encaissements - total_retours,
        "marge": marge_ventes - marge_retours,
        "achats": total_achats,
        "nb_receptions": receptions.count(),
        "en_attente": Paiement.objects.filter(statut=Paiement.Statut.EN_ATTENTE).count(),
    }


def produits_plus_vendus(du, au, limite=10):
    return (
        LigneVente.objects.filter(vente__statut=Vente.Statut.VALIDEE, vente__date__date__range=(du, au))
        .values("medicament__id", "medicament__nom", "medicament__dosage")
        .annotate(qte_vendue=Sum("quantite"),
                  montant=Sum(F("quantite") * F("prix_unitaire"), output_field=MONTANT))
        .order_by("-qte_vendue")[:limite]
    )


def ventes_par_jour(du, au):
    """Liste [{jour, total, pourcentage}] pour un petit histogramme sans JavaScript."""
    donnees = dict(
        Vente.objects.filter(statut=Vente.Statut.VALIDEE, date__date__range=(du, au))
        .annotate(jour=TruncDate("date")).values_list("jour").annotate(t=Sum("total"))
    )
    jours = [du + timedelta(days=i) for i in range((au - du).days + 1)][-31:]
    maximum = max([donnees.get(j, ZERO) for j in jours] + [Decimal("1")])
    return [{"jour": j, "total": donnees.get(j, ZERO),
             "pourcentage": int(donnees.get(j, ZERO) * 100 / maximum)} for j in jours]


# ---------------------------------------------------------------- Tableau de bord

@login_required
def tableau_de_bord(request):
    aujourd_hui = timezone.localdate()
    du, au = periode(request, jours_defaut=7)
    meds = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF)

    ventes_jour = Vente.objects.filter(statut=Vente.Statut.VALIDEE, date__date=aujourd_hui)
    voit_ventes = a_un_role(request.user, ADMIN, PHARMACIEN, CAISSIER, GESTION)
    voit_stock = a_un_role(request.user, ADMIN, PHARMACIEN, STOCK, GESTION, CAISSIER)
    voit_finances = a_un_role(request.user, ADMIN, PHARMACIEN, GESTION)
    voit_achats = a_un_role(request.user, ADMIN, PHARMACIEN, STOCK, GESTION)

    contexte = {
        "du": du, "au": au, "jours": (au - du).days + 1,
        "voit_ventes": voit_ventes, "voit_stock": voit_stock,
        "voit_finances": voit_finances, "voit_achats": voit_achats,
        "kpi": {
            "medicaments_actifs": meds.count(),
            "ventes_jour_montant": ventes_jour.aggregate(t=Sum("total"))["t"] or ZERO,
            "ventes_jour_nombre": ventes_jour.count(),
            "stocks_faibles": meds.filter(stock_vendable_calc__lte=F("seuil_alerte")).count(),
            "ruptures": meds.filter(stock_vendable_calc=0).count(),
            "peremptions_proches": LotStock.objects.proches_peremption().filter(quantite__gt=0).count(),
            "perimes": LotStock.objects.perimes().filter(quantite__gt=0).count(),
        },
        "alertes_stock": meds.filter(stock_vendable_calc__lte=F("seuil_alerte")).order_by("stock_vendable_calc", "nom")[:8],
        "lots_alerte": LotStock.objects.filter(quantite__gt=0).filter(
            Q(date_peremption__lt=aujourd_hui)
            | Q(date_peremption__lte=aujourd_hui + timedelta(days=settings.PEREMPTION_ALERTE_JOURS))
        ).select_related("medicament").order_by("date_peremption")[:8],
        "commandes_en_cours": CommandeAchat.objects.filter(
            statut__in=[CommandeAchat.Statut.COMMANDEE, CommandeAchat.Statut.PARTIELLE]
        ).select_related("fournisseur")[:5],
        "dernieres_ventes": Vente.objects.select_related("client")[:6],
        "roles_utilisateur": list(request.user.groups.values_list("name", flat=True)),
    }
    if voit_finances or voit_ventes:
        contexte["stats"] = statistiques(du, au)
        contexte["top_produits"] = produits_plus_vendus(du, au, 5)
        contexte["histogramme"] = ventes_par_jour(du, au)
    return render(request, "tableau_de_bord.html", contexte)


# ---------------------------------------------------------------- Page des rapports

@role_requis(PHARMACIEN, GESTION)
def rapports(request):
    du, au = periode(request)
    return render(request, "rapports/index.html", {
        "du": du, "au": au,
        "stats": statistiques(du, au),
        "top_produits": produits_plus_vendus(du, au),
        "histogramme": ventes_par_jour(du, au),
        "par_mode": Paiement.objects.filter(
            statut=Paiement.Statut.CONFIRME, date__date__range=(du, au), vente__statut=Vente.Statut.VALIDEE,
        ).values("mode").annotate(total=Sum("montant"), nombre=Count("pk")).order_by("-total"),
        "libelles_modes": dict(ModePaiement.choices),
        "jours_alerte": settings.PEREMPTION_ALERTE_JOURS,
    })


# ---------------------------------------------------------------- Documents PDF

@role_requis(CAISSIER, PHARMACIEN, GESTION)
def pdf_recu(request, pk):
    return pdf.recu_vente(get_object_or_404(Vente.objects.select_related("client", "vendeur"), pk=pk))


@role_requis(CAISSIER, PHARMACIEN, GESTION)
def pdf_facture(request, pk):
    return pdf.facture_vente(get_object_or_404(Vente.objects.select_related("client"), pk=pk))


@role_requis(PHARMACIEN, STOCK, GESTION)
def pdf_bon_commande(request, pk):
    return pdf.bon_commande(get_object_or_404(CommandeAchat.objects.select_related("fournisseur"), pk=pk))


@role_requis(PHARMACIEN, STOCK, GESTION)
def pdf_bon_reception(request, pk):
    return pdf.bon_reception(
        get_object_or_404(ReceptionAchat.objects.select_related("commande__fournisseur", "recu_par"), pk=pk)
    )


@role_requis(PHARMACIEN, STOCK, GESTION)
def pdf_stock(request):
    meds = medicaments_avec_stock().filter(statut=Medicament.Statut.ACTIF).order_by("nom")
    valeur = sum((m.stock_vendable_calc * m.prix_achat for m in meds), ZERO)
    return pdf.rapport_stock(meds, valeur)


@role_requis(PHARMACIEN, GESTION)
def pdf_ventes(request):
    du, au = periode(request)
    ventes = Vente.objects.filter(date__date__range=(du, au)).select_related("client", "vendeur").order_by("date")
    return pdf.rapport_ventes(ventes, du, au, statistiques(du, au))


@role_requis(PHARMACIEN, STOCK, GESTION)
def pdf_achats(request):
    du, au = periode(request)
    receptions = ReceptionAchat.objects.filter(date_reception__date__range=(du, au)).select_related(
        "commande__fournisseur").order_by("date_reception")
    return pdf.rapport_achats(receptions, du, au, statistiques(du, au)["achats"])


@role_requis(PHARMACIEN, STOCK, GESTION)
def pdf_peremptions(request):
    limite = timezone.localdate() + timedelta(days=settings.PEREMPTION_ALERTE_JOURS)
    lots = LotStock.objects.filter(quantite__gt=0, date_peremption__lte=limite).select_related(
        "medicament").order_by("date_peremption")
    return pdf.rapport_peremptions(lots, settings.PEREMPTION_ALERTE_JOURS)
