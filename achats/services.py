from django.db import transaction
from django.db.models import F
from django.utils import timezone

from stock.models import LotStock, MouvementStock
from stock.services import ErreurStock, enregistrer_mouvement
from utilisateurs.models import JournalAudit

from .models import CommandeAchat, LigneAchat, LigneReception, ReceptionAchat


class ReceptionDejaEnregistree(Exception):
    """Le même formulaire a été envoyé deux fois (double clic, bouton Retour...)."""


@transaction.atomic
def valider_commande(commande_id, utilisateur):
    commande = CommandeAchat.objects.select_for_update().get(pk=commande_id)
    if commande.statut != CommandeAchat.Statut.BROUILLON:
        raise ErreurStock("Seule une commande en brouillon peut être validée.")
    if not commande.lignes.exists():
        raise ErreurStock("Ajoutez au moins un médicament avant de valider la commande.")

    commande.statut = CommandeAchat.Statut.COMMANDEE
    commande.date_validation = timezone.now()
    commande.valide_par = utilisateur
    commande.save(update_fields=["statut", "date_validation", "valide_par"])
    JournalAudit.enregistrer(utilisateur, "VALIDATION", f"Commande {commande.numero}", f"Total : {commande.total} Ar")
    return commande


@transaction.atomic
def annuler_commande(commande_id, utilisateur):
    commande = CommandeAchat.objects.select_for_update().get(pk=commande_id)
    if not commande.peut_etre_annulee:
        raise ErreurStock("Cette commande ne peut plus être annulée (elle a déjà été réceptionnée).")

    commande.statut = CommandeAchat.Statut.ANNULEE
    commande.date_annulation = timezone.now()
    commande.annule_par = utilisateur
    commande.save(update_fields=["statut", "date_annulation", "annule_par"])
    JournalAudit.enregistrer(utilisateur, "ANNULATION", f"Commande {commande.numero}")
    return commande


@transaction.atomic
def receptionner(commande_id, lignes_saisies, utilisateur, jeton, note=""):
    """
    Enregistre une réception. Tout réussit ou rien n'est enregistré.
    lignes_saisies : liste de dictionnaires
        {"ligne_id": ..., "quantite": ..., "numero_lot": ..., "date_peremption": ...}
    """
    if not jeton:
        raise ErreurStock("Formulaire invalide : rechargez la page.")

    commande = CommandeAchat.objects.select_for_update().get(pk=commande_id)
    if not commande.peut_etre_receptionnee:
        raise ErreurStock(f"Cette commande ne peut pas être réceptionnée (statut : {commande.get_statut_display()}).")

    if ReceptionAchat.objects.filter(jeton=jeton).exists():
        raise ReceptionDejaEnregistree()

    a_traiter = [s for s in lignes_saisies if s.get("quantite")]
    if not a_traiter:
        raise ErreurStock("Indiquez au moins une quantité reçue.")

    reception = ReceptionAchat.objects.create(
        commande=commande, recu_par=utilisateur, note=note, jeton=jeton
    )

    for saisie in a_traiter:
        quantite = saisie["quantite"]

        # On relit la ligne depuis la base à chaque fois (valeurs à jour)
        try:
            ligne = commande.lignes.select_for_update().select_related("medicament").get(pk=saisie["ligne_id"])
        except LigneAchat.DoesNotExist:
            raise ErreurStock("Ligne de commande introuvable.")

        if quantite > ligne.reste_a_recevoir:
            raise ErreurStock(
                f"{ligne.medicament} : {quantite} saisi(s), mais il ne reste que "
                f"{ligne.reste_a_recevoir} à recevoir."
            )

        numero_lot = saisie["numero_lot"].strip().upper()
        date_peremption = saisie["date_peremption"]

        lot, cree = LotStock.objects.select_for_update().get_or_create(
            medicament=ligne.medicament,
            numero_lot=numero_lot,
            defaults={"date_peremption": date_peremption},
        )
        if not cree and lot.date_peremption != date_peremption:
            raise ErreurStock(
                f"Le lot {numero_lot} de {ligne.medicament} existe déjà avec la date de péremption "
                f"{lot.date_peremption:%d/%m/%Y}. Vérifiez la saisie."
            )

        LotStock.objects.filter(pk=lot.pk).update(quantite_recue=F("quantite_recue") + quantite)

        enregistrer_mouvement(
            lot, MouvementStock.Type.ENTREE_ACHAT, quantite, utilisateur,
            reference=reception.numero, motif=f"Commande {commande.numero}",
        )

        LigneReception.objects.create(
            reception=reception, ligne_achat=ligne, lot=lot,
            quantite=quantite, prix_achat=ligne.prix_achat,
        )
        LigneAchat.objects.filter(pk=ligne.pk).update(quantite_recue=F("quantite_recue") + quantite)

    commande.mettre_a_jour_statut()
    JournalAudit.enregistrer(
        utilisateur, "RECEPTION", f"Réception {reception.numero}",
        f"Commande {commande.numero} — {len(a_traiter)} ligne(s)",
    )
    return reception