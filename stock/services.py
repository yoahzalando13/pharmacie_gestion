from django.db import transaction
from django.db.models import F

from .models import LotStock, MouvementStock


class ErreurStock(Exception):
    """Erreur métier : quantité invalide, stock insuffisant, opération interdite..."""


@transaction.atomic
def enregistrer_mouvement(lot, type_mouvement, quantite, utilisateur, reference="", motif=""):
    """
    SEUL point d'entrée autorisé pour modifier la quantité d'un lot.
    - modifie le lot de façon atomique ;
    - refuse un stock négatif (RG07) ;
    - crée le mouvement traçable (RG09).
    """
    if quantite is None or quantite <= 0:
        raise ErreurStock("La quantité doit être strictement positive.")

    entree = type_mouvement in MouvementStock.TYPES_ENTREE

    if entree:
        LotStock.objects.filter(pk=lot.pk).update(quantite=F("quantite") + quantite)
    else:
        # Mise à jour CONDITIONNELLE : la base ne modifie la ligne que si le stock suffit.
        # Même si deux caissiers valident en même temps, un seul réussit.
        modifies = LotStock.objects.filter(pk=lot.pk, quantite__gte=quantite).update(
            quantite=F("quantite") - quantite
        )
        if modifies == 0:
            lot.refresh_from_db(fields=["quantite"])
            raise ErreurStock(
                f"Stock insuffisant pour le lot {lot.numero_lot} : "
                f"{lot.quantite} disponible(s), {quantite} demandé(s)."
            )

    lot.refresh_from_db(fields=["quantite"])
    stock_apres = lot.quantite
    stock_avant = stock_apres - quantite if entree else stock_apres + quantite

    return MouvementStock.objects.create(
        lot=lot,
        type=type_mouvement,
        quantite=quantite,
        stock_avant=stock_avant,
        stock_apres=stock_apres,
        reference=reference,
        motif=motif,
        utilisateur=utilisateur,
    )

TYPES_CORRECTION = {
    MouvementStock.Type.CORRECTION_PLUS,
    MouvementStock.Type.CORRECTION_MOINS,
    MouvementStock.Type.SORTIE_PERTE,
}


@transaction.atomic
def corriger_stock(lot_id, type_mouvement, quantite, motif, utilisateur):
    """Correction d'inventaire, perte, casse ou destruction d'un lot périmé (motif obligatoire)."""
    if type_mouvement not in TYPES_CORRECTION:
        raise ErreurStock("Type de correction non autorisé.")
    if not motif or not motif.strip():
        raise ErreurStock("Le motif est obligatoire pour une correction de stock.")
    lot = LotStock.objects.select_for_update().get(pk=lot_id)
    mouvement = enregistrer_mouvement(lot, type_mouvement, quantite, utilisateur, motif=motif.strip())
    from utilisateurs.models import JournalAudit
    JournalAudit.enregistrer(
        utilisateur, "CORRECTION_STOCK", f"Lot {lot.numero_lot}",
        f"{mouvement.get_type_display()} : {quantite} — {lot.medicament} — {motif.strip()}",
    )
    return mouvement


@transaction.atomic
def enregistrer_inventaire(comptages, motif, utilisateur, reference=""):
    """
    Inventaire physique : comptages = {lot_id: quantite_comptee}.
    Chaque écart crée une correction (+ ou −) traçable. Renvoie la liste des mouvements créés.
    """
    mouvements = []
    for lot_id, compte in comptages.items():
        if compte is None:
            continue
        if compte < 0:
            raise ErreurStock("Une quantité comptée ne peut pas être négative.")
        lot = LotStock.objects.select_for_update().get(pk=lot_id)
        ecart = compte - lot.quantite
        if ecart == 0:
            continue
        type_mvt = MouvementStock.Type.CORRECTION_PLUS if ecart > 0 else MouvementStock.Type.CORRECTION_MOINS
        mouvements.append(
            enregistrer_mouvement(
                lot, type_mvt, abs(ecart), utilisateur,
                reference=reference, motif=motif or "Inventaire physique",
            )
        )
    from utilisateurs.models import JournalAudit
    JournalAudit.enregistrer(
        utilisateur, "INVENTAIRE", reference or "Inventaire physique",
        f"{len(comptages)} lot(s) compté(s), {len(mouvements)} écart(s) corrigé(s)",
    )
    return mouvements


@transaction.atomic
def basculer_blocage(lot_id, utilisateur, motif=""):
    """Bloque un lot (rappel, doute qualité...) ou le débloque. Un lot bloqué n'est jamais vendu (RG08)."""
    lot = LotStock.objects.select_for_update().get(pk=lot_id)
    if not lot.bloque and not motif.strip():
        raise ErreurStock("Indiquez le motif du blocage.")
    lot.bloque = not lot.bloque
    lot.motif_blocage = motif.strip() if lot.bloque else ""
    lot.save(update_fields=["bloque", "motif_blocage"])
    from utilisateurs.models import JournalAudit
    JournalAudit.enregistrer(
        utilisateur, "BLOCAGE_LOT" if lot.bloque else "DEBLOCAGE_LOT",
        f"Lot {lot.numero_lot}", f"{lot.medicament} {('— ' + lot.motif_blocage) if lot.bloque else ''}",
    )
    return lot
