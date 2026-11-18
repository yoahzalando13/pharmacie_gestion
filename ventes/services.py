from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from medicaments.models import Medicament
from stock.models import LotStock, MouvementStock
from stock.services import ErreurStock, enregistrer_mouvement
from utilisateurs.models import JournalAudit

from .models import MODES_A_VERIFIER, LigneVente, ModePaiement, Paiement, RetourVente, Vente


class VenteDejaEnregistree(Exception):
    """Le même formulaire de caisse a été envoyé deux fois (double clic, rechargement...)."""


def _repartir_fefo(medicament, quantite):
    """
    Choisit les lots selon la méthode FEFO : le lot qui périme en premier sort en premier.
    Renvoie une liste [(lot, quantite)]. Lève ErreurStock si le stock vendable est insuffisant.
    """
    lots = list(
        LotStock.objects.select_for_update()
        .vendables()
        .filter(medicament=medicament)
        .order_by("date_peremption", "pk")
    )
    disponible = sum(l.quantite for l in lots)
    if disponible < quantite:
        raise ErreurStock(
            f"Stock insuffisant pour {medicament} : {disponible} unité(s) vendable(s), {quantite} demandée(s)."
        )
    repartition, reste = [], quantite
    for lot in lots:
        if reste == 0:
            break
        pris = min(lot.quantite, reste)
        repartition.append((lot, pris))
        reste -= pris
    return repartition


@transaction.atomic
def valider_vente(panier, utilisateur, jeton, mode=ModePaiement.ESPECES,
                  montant_recu=None, reference="", client=None):
    """
    Valide une vente et sort le stock dans UNE transaction atomique (§4.8) :
    tout est enregistré, ou rien du tout.

    panier : liste de dictionnaires {"medicament_id": int, "lot_id": int | None, "quantite": int}
             lot_id = None  →  choix automatique des lots en FEFO.
    """
    if not jeton:
        raise ErreurStock("Formulaire de caisse invalide : rechargez la page.")
    if Vente.objects.filter(jeton=jeton).exists():
        raise VenteDejaEnregistree()
    if not panier:
        raise ErreurStock("Le panier est vide.")
    if mode not in ModePaiement.values:
        raise ErreurStock("Mode de paiement inconnu.")

    vente = Vente.objects.create(vendeur=utilisateur, client=client, jeton=jeton)
    total = Decimal("0")

    for article in panier:
        quantite = int(article.get("quantite") or 0)
        if quantite <= 0:                                   # RG03
            raise ErreurStock("Chaque quantité doit être strictement positive.")

        try:
            medicament = Medicament.objects.get(pk=article["medicament_id"])
        except Medicament.DoesNotExist:
            raise ErreurStock("Médicament introuvable.")
        if medicament.statut != Medicament.Statut.ACTIF:
            raise ErreurStock(f"{medicament} est archivé : il ne peut pas être vendu.")

        lot_id = article.get("lot_id")
        if lot_id:
            try:
                lot = LotStock.objects.select_for_update().select_related("medicament").get(
                    pk=lot_id, medicament=medicament
                )
            except LotStock.DoesNotExist:
                raise ErreurStock(f"Lot introuvable pour {medicament}.")
            if lot.est_perime:                              # RG08
                raise ErreurStock(f"Le lot {lot.numero_lot} de {medicament} est périmé : vente refusée.")
            if lot.bloque:                                  # RG08
                raise ErreurStock(f"Le lot {lot.numero_lot} de {medicament} est bloqué : vente refusée.")
            repartition = [(lot, quantite)]
        else:
            repartition = _repartir_fefo(medicament, quantite)

        for lot, qte in repartition:
            # Sortie conditionnelle : refuse le stock négatif même en cas de ventes simultanées (RG06, RG07)
            enregistrer_mouvement(
                lot, MouvementStock.Type.SORTIE_VENTE, qte, utilisateur,
                reference=vente.numero, motif=f"Vente {vente.numero}",
            )
            LigneVente.objects.create(
                vente=vente, medicament=medicament, lot=lot, quantite=qte,
                prix_unitaire=medicament.prix_vente,         # prix figé (RG12)
                cout_unitaire=medicament.prix_achat,
            )
            total += qte * medicament.prix_vente

    vente.total = total
    vente.save(update_fields=["total"])

    # ---- Paiement
    if mode == ModePaiement.ESPECES:
        if montant_recu is None:
            montant_recu = total
        if montant_recu < total:
            raise ErreurStock(f"Montant reçu insuffisant : {montant_recu} Ar pour un total de {total} Ar.")
        statut = Paiement.Statut.CONFIRME
    else:
        # Un paiement électronique n'est confirmé qu'après vérification fiable de son statut (§4.8)
        montant_recu = None
        statut = Paiement.Statut.EN_ATTENTE if mode in MODES_A_VERIFIER else Paiement.Statut.CONFIRME

    Paiement.objects.create(
        vente=vente, mode=mode, montant=total, montant_recu=montant_recu,
        reference=reference.strip(), statut=statut, enregistre_par=utilisateur,
    )

    JournalAudit.enregistrer(
        utilisateur, "VENTE", f"Vente {vente.numero}",
        f"Total : {total} Ar — {vente.lignes.count()} ligne(s) — {ModePaiement(mode).label}",
    )
    return vente


@transaction.atomic
def verifier_paiement(paiement_id, utilisateur, accepte, reference=""):
    paiement = Paiement.objects.select_for_update().select_related("vente").get(pk=paiement_id)
    if paiement.statut != Paiement.Statut.EN_ATTENTE:
        raise ErreurStock("Ce paiement a déjà été traité.")
    if accepte and not (reference or paiement.reference).strip():
        raise ErreurStock("Saisissez la référence de la transaction pour confirmer le paiement.")

    paiement.statut = Paiement.Statut.CONFIRME if accepte else Paiement.Statut.REJETE
    if reference.strip():
        paiement.reference = reference.strip()
    paiement.verifie_par = utilisateur
    paiement.date_verification = timezone.now()
    paiement.save(update_fields=["statut", "reference", "verifie_par", "date_verification"])
    JournalAudit.enregistrer(
        utilisateur, "PAIEMENT_CONFIRME" if accepte else "PAIEMENT_REJETE",
        f"Vente {paiement.vente.numero}", f"{paiement.get_mode_display()} — réf. {paiement.reference or '—'}",
    )
    return paiement


@transaction.atomic
def enregistrer_retour(ligne_id, quantite, motif, remis_en_stock, utilisateur,
                       mode_remboursement=ModePaiement.ESPECES):
    """Retour partiel ou total d'une ligne de vente, par opération compensatoire (§4.9)."""
    ligne = LigneVente.objects.select_for_update().select_related("vente", "lot", "medicament").get(pk=ligne_id)
    vente = ligne.vente

    if vente.statut != Vente.Statut.VALIDEE:
        raise ErreurStock("Un retour n'est possible que sur une vente validée.")
    if not motif or not motif.strip():
        raise ErreurStock("Le motif du retour est obligatoire.")
    quantite = int(quantite or 0)
    if quantite <= 0:
        raise ErreurStock("La quantité retournée doit être strictement positive.")
    if quantite > ligne.quantite_retournable:
        raise ErreurStock(
            f"{ligne.medicament} : {quantite} retour(s) demandé(s), mais seulement "
            f"{ligne.quantite_retournable} unité(s) peuvent encore être retournées."
        )
    if remis_en_stock and (ligne.lot.est_perime or ligne.lot.bloque):
        raise ErreurStock(
            f"Le lot {ligne.lot.numero_lot} est périmé ou bloqué : le produit ne peut pas être remis en stock."
        )

    retour = RetourVente.objects.create(
        vente=vente, ligne=ligne, quantite=quantite, motif=motif.strip(),
        remis_en_stock=remis_en_stock, montant_rembourse=quantite * ligne.prix_unitaire,
        mode_remboursement=mode_remboursement, utilisateur=utilisateur,
    )
    if remis_en_stock:
        enregistrer_mouvement(
            ligne.lot, MouvementStock.Type.RETOUR_CLIENT, quantite, utilisateur,
            reference=retour.numero, motif=f"Retour sur {vente.numero} : {motif.strip()}",
        )

    JournalAudit.enregistrer(
        utilisateur, "RETOUR", f"Retour {retour.numero}",
        f"Vente {vente.numero} — {quantite} × {ligne.medicament} — remboursé {retour.montant_rembourse} Ar"
        f" — {'remis en stock' if remis_en_stock else 'non remis en stock'}",
    )
    return retour


@transaction.atomic
def annuler_vente(vente_id, utilisateur, motif):
    """
    Annulation complète par opération compensatoire : la vente reste dans l'historique
    avec le statut « Annulée », et le stock non encore retourné est réintégré (RG10).
    """
    vente = Vente.objects.select_for_update().get(pk=vente_id)
    if vente.statut != Vente.Statut.VALIDEE:
        raise ErreurStock("Cette vente est déjà annulée.")
    if not motif or not motif.strip():
        raise ErreurStock("Le motif d'annulation est obligatoire.")
    if vente.retours.exists():
        raise ErreurStock("Cette vente a déjà fait l'objet de retours : traitez le reste par des retours.")

    for ligne in vente.lignes.select_related("lot"):
        enregistrer_mouvement(
            ligne.lot, MouvementStock.Type.RETOUR_CLIENT, ligne.quantite, utilisateur,
            reference=vente.numero, motif=f"Annulation de {vente.numero} : {motif.strip()}",
        )

    vente.statut = Vente.Statut.ANNULEE
    vente.date_annulation = timezone.now()
    vente.annule_par = utilisateur
    vente.motif_annulation = motif.strip()
    vente.save(update_fields=["statut", "date_annulation", "annule_par", "motif_annulation"])
    JournalAudit.enregistrer(utilisateur, "ANNULATION", f"Vente {vente.numero}", motif.strip())
    return vente
