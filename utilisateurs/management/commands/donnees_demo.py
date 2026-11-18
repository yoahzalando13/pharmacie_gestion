import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from achats.models import CommandeAchat, LigneAchat
from achats.services import receptionner, valider_commande
from clients.models import Client
from fournisseurs.models import Fournisseur
from medicaments.models import Categorie, Medicament
from stock.models import LotStock, MouvementStock
from stock.services import basculer_blocage, enregistrer_mouvement
from utilisateurs.models import Utilisateur
from utilisateurs.permissions import ADMIN, CAISSIER, GESTION, PHARMACIEN, STOCK
from ventes.models import ModePaiement, Paiement, Vente
from ventes.services import annuler_vente, enregistrer_retour, valider_vente, verifier_paiement

# Ventes réparties sur les 20 derniers jours pour alimenter les graphiques :
# (jours dans le passé, mode de paiement, [(index du médicament, quantité), ...])
VENTES_PASSEES = [
    (1, ModePaiement.ESPECES, [(0, 2), (7, 1)]),
    (2, ModePaiement.ESPECES, [(2, 1)]),
    (3, ModePaiement.MOBILE_MONEY, [(0, 4), (5, 1)]),
    (5, ModePaiement.ESPECES, [(3, 2)]),
    (6, ModePaiement.ESPECES, [(1, 2), (7, 2)]),
    (8, ModePaiement.ESPECES, [(0, 3)]),
    (10, ModePaiement.CARTE, [(2, 3), (5, 1)]),
    (13, ModePaiement.ESPECES, [(3, 1), (0, 2)]),
    (16, ModePaiement.ESPECES, [(7, 1)]),
    (20, ModePaiement.ESPECES, [(1, 3)]),
]

MOT_DE_PASSE = "Demo-PharmaGest-2026"

COMPTES = [
    ("admin_demo", "Aina", "Rakoto", ADMIN),
    ("pharmacien", "Hery", "Randria", PHARMACIEN),
    ("stock", "Fara", "Rabe", STOCK),
    ("caissier", "Miora", "Andria", CAISSIER),
    ("gestion", "Tiana", "Razafy", GESTION),
]

MEDICAMENTS = [
    # nom, dci, catégorie, forme, dosage, labo, code-barres, achat, vente, seuil
    ("Doliprane", "Paracétamol", "Antalgiques", "COMPRIME", "500 mg", "Sanofi", "3400930000001", 1500, 2500, 20),
    ("Efferalgan", "Paracétamol", "Antalgiques", "COMPRIME", "1 g", "UPSA", "3400930000002", 2200, 3500, 15),
    ("Ibuprofène Biogaran", "Ibuprofène", "Anti-inflammatoires", "COMPRIME", "400 mg", "Biogaran", "3400930000003", 1800, 3000, 15),
    ("Amoxicilline", "Amoxicilline", "Antibiotiques", "GELULE", "500 mg", "Sandoz", "3400930000004", 4000, 6500, 10),
    ("Vitamine C Upsa", "Acide ascorbique", "Vitamines", "COMPRIME", "1 g", "UPSA", "3400930000005", 3000, 4800, 10),
    ("Bétadine", "Povidone iodée", "Antiseptiques", "AUTRE", "10 %", "Meda", "3400930000006", 5500, 8500, 5),
    ("Toplexil", "Oxomémazine", "Antitussifs", "SIROP", "150 ml", "Sanofi", "3400930000007", 6000, 9500, 5),
    ("Smecta", "Diosmectite", "Gastro-entérologie", "AUTRE", "3 g", "Ipsen", "3400930000008", 4500, 7000, 8),
]


class Command(BaseCommand):
    help = "Crée un jeu de données fictives complet (rôles, comptes, médicaments, achats, stock, ventes) pour les tests."

    def handle(self, *args, **options):
        if Utilisateur.objects.filter(username="pharmacien").exists():
            self.stdout.write(self.style.WARNING("Les données de démonstration existent déjà : rien n'a été modifié."))
            return

        call_command("init_roles", stdout=self.stdout)
        with transaction.atomic():
            self._creer()

        self.stdout.write(self.style.SUCCESS("\nDonnées de démonstration créées."))
        self.stdout.write(f"Comptes (mot de passe commun : {MOT_DE_PASSE}) :")
        for username, prenom, nom, role in COMPTES:
            self.stdout.write(f"  • {username:<12} {role}")
        self.stdout.write(self.style.WARNING("Changez ou supprimez ces comptes avant toute utilisation réelle."))

    def _creer(self):
        aujourd_hui = timezone.localdate()

        comptes = {}
        for username, prenom, nom, role in COMPTES:
            u = Utilisateur.objects.create_user(username, password=MOT_DE_PASSE, first_name=prenom, last_name=nom)
            u.groups.add(Group.objects.get(name=role))
            comptes[role] = u
        pharmacien, caissier = comptes[PHARMACIEN], comptes[CAISSIER]

        meds = []
        for nom, dci, cat, forme, dosage, labo, code, achat, vente, seuil in MEDICAMENTS:
            categorie, _ = Categorie.objects.get_or_create(nom=cat)
            meds.append(Medicament.objects.create(
                nom=nom, dci=dci, categorie=categorie, forme=forme, dosage=dosage, laboratoire=labo,
                code_barres=code, prix_achat=Decimal(achat), prix_vente=Decimal(vente),
                seuil_alerte=seuil, cree_par=pharmacien,
            ))

        f1 = Fournisseur.objects.create(
            nom="Pharmad Distribution", telephone="020 22 000 01", email="commandes@pharmad.example",
            contact_principal="M. Rasolo", adresse="Antananarivo", cree_par=comptes[STOCK],
        )
        Fournisseur.objects.create(
            nom="Medi-Import Madagascar", telephone="034 00 000 02", contact_principal="Mme Ravelo",
            adresse="Toamasina", cree_par=comptes[STOCK],
        )
        client = Client.objects.create(nom="Rasoa Hanta", telephone="032 00 000 03", cree_par=caissier)
        Client.objects.create(nom="Clinique Les Lilas", telephone="020 22 000 04", cree_par=caissier)

        # ---- Une commande reçue en totalité, une commande reçue partiellement
        quantites = [60, 40, 30, 25, 8, 12, 4, 20]
        commande = CommandeAchat.objects.create(fournisseur=f1, cree_par=comptes[STOCK], note="Réassort mensuel")
        for m, q in zip(meds, quantites):
            LigneAchat.objects.create(commande=commande, medicament=m, quantite_commandee=q, prix_achat=m.prix_achat)
        valider_commande(commande.pk, pharmacien)
        lignes = []
        for i, ligne in enumerate(commande.lignes.select_related("medicament")):
            # Un lot proche de la péremption pour illustrer les alertes
            jours = 45 if i == 1 else 400 + 30 * i
            lignes.append({
                "ligne_id": ligne.pk, "quantite": ligne.quantite_commandee,
                "numero_lot": f"L{aujourd_hui:%y}{i + 1:03d}A",
                "date_peremption": aujourd_hui + timedelta(days=jours),
            })
        receptionner(commande.pk, lignes, comptes[STOCK], uuid.uuid4().hex, "Livraison complète")

        commande2 = CommandeAchat.objects.create(fournisseur=f1, cree_par=comptes[STOCK])
        LigneAchat.objects.create(commande=commande2, medicament=meds[0], quantite_commandee=50, prix_achat=meds[0].prix_achat)
        LigneAchat.objects.create(commande=commande2, medicament=meds[3], quantite_commandee=20, prix_achat=meds[3].prix_achat)
        valider_commande(commande2.pk, pharmacien)
        l0 = commande2.lignes.get(medicament=meds[0])
        receptionner(commande2.pk, [{
            "ligne_id": l0.pk, "quantite": 30, "numero_lot": f"L{aujourd_hui:%y}101B",
            "date_peremption": aujourd_hui + timedelta(days=700),
        }], comptes[STOCK], uuid.uuid4().hex, "Livraison partielle")

        # ---- Un lot déjà périmé (stock initial historique) pour tester le refus de vente
        lot_perime = LotStock.objects.create(
            medicament=meds[4], numero_lot="ANCIEN-01", date_peremption=aujourd_hui - timedelta(days=10),
        )
        enregistrer_mouvement(lot_perime, MouvementStock.Type.CORRECTION_PLUS, 5, pharmacien,
                              motif="Stock initial avant mise en service")

        # ---- Quelques ventes
        valider_vente([{"medicament_id": meds[0].pk, "lot_id": None, "quantite": 3},
                       {"medicament_id": meds[2].pk, "lot_id": None, "quantite": 2}],
                      caissier, uuid.uuid4().hex, mode=ModePaiement.ESPECES, montant_recu=Decimal("15000"))
        valider_vente([{"medicament_id": meds[3].pk, "lot_id": None, "quantite": 1}],
                      caissier, uuid.uuid4().hex, mode=ModePaiement.MOBILE_MONEY, reference="MVOLA-123456",
                      client=client)
        valider_vente([{"medicament_id": meds[1].pk, "lot_id": None, "quantite": 4}],
                      pharmacien, uuid.uuid4().hex)

        # ---- Historique : ventes antidatées sur les 20 derniers jours
        maintenant = timezone.now()
        ventes_passees = []
        for jours, mode, articles in VENTES_PASSEES:
            vente = valider_vente(
                [{"medicament_id": meds[i].pk, "lot_id": None, "quantite": q} for i, q in articles],
                caissier, uuid.uuid4().hex, mode=mode,
                reference="MVOLA-DEMO-%03d" % jours if mode == ModePaiement.MOBILE_MONEY else "",
            )
            moment = maintenant - timedelta(days=jours, hours=jours % 5)
            Vente.objects.filter(pk=vente.pk).update(date=moment)
            Paiement.objects.filter(vente=vente).update(date=moment)
            ventes_passees.append(vente)

        # Un paiement mobile money vérifié, un retour remis en stock, une vente annulée
        paiement_mm = ventes_passees[2].paiements.get()
        verifier_paiement(paiement_mm.pk, caissier, True, "MVOLA-DEMO-003")
        enregistrer_retour(ventes_passees[3].lignes.first().pk, 1, "Erreur de dosage signalée par le client",
                           True, caissier)
        annuler_vente(ventes_passees[7].pk, pharmacien, "Erreur de saisie à la caisse (démonstration)")

        # ---- Un lot bloqué (rappel fabricant) : le médicament apparaît en rupture
        lot_rappel = LotStock.objects.filter(medicament=meds[5], quantite__gt=0).first()
        if lot_rappel:
            basculer_blocage(lot_rappel.pk, pharmacien, "Rappel du fabricant (démonstration)")

        # ---- Une commande en brouillon, prête à être validée
        brouillon = CommandeAchat.objects.create(fournisseur=f1, cree_par=comptes[STOCK], note="À valider")
        for m in (meds[4], meds[6]):
            LigneAchat.objects.create(commande=brouillon, medicament=m, quantite_commandee=30, prix_achat=m.prix_achat)
