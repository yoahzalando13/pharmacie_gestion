
## 1. Conformité module par module

| Module (cahier des charges) | Avant | Après |
|---|---|---|
| A — Authentification, rôles, journal | Fait | Fait (+ tests de permissions par rôle) |
| B — Médicaments (CRUD, photo, archivage, recherche, tri, pagination) | Fait | Fait, stock réel affiché sur la fiche |
| C — Catégories | Fait | Fait |
| D — Fournisseurs | Fiche faite, historique « Partie 5 » | + historique des commandes, montants commandés et réceptionnés |
| E — Clients | Fiche faite, historique « Partie 6 » | + historique et total des ventes |
| F — Achats (brouillon → commandée → réception partielle/totale, annulation) | Logique écrite, inutilisable (ni tables ni pages) | Opérationnel, + bon de commande et bon de réception PDF |
| G — Stock (lots, FEFO, mouvements, alertes, inventaire) | Modèles seulement, aucune vue | État du stock, fiche par médicament, alertes, mouvements, corrections motivées, blocage de lot, inventaire physique |
| H — Ventes / caisse | Vide | Caisse avec recherche et scan code-barres, choix FEFO ou manuel du lot, paiements (espèces avec rendu de monnaie, mobile money à vérifier), transaction atomique, anti-double validation |
| I — Retours et annulations | Vide | Retours partiels avec ou sans remise en stock, annulation compensatoire ; la vente d'origine est conservée |
| J — Tableau de bord | Indicateurs fictifs (marge moyenne catalogue) | Les 4 indicateurs demandés calculés depuis les données réelles, période sélectionnable, top produits, alertes, CA ≠ encaissements ≠ marge |
| K — PDF ReportLab | Absent | Reçu, facture, bon de commande, bon de réception, rapports de stock, ventes, achats, péremptions |

## 3. Règles de gestion (§5)

| Règle | Où elle est garantie | Test |
|---|---|---|
| RG01 identifiant unique | Clé primaire auto | — |
| RG02 code-barres unique | `unique=True` + vide → NULL | `test_code_barres_unique_rg02` |
| RG03 validation serveur | Formulaires + services | `test_quantite_nulle_ou_negative_refusee` |
| RG04 commande sans effet sur le stock | `achats/services.py` | `test_commande_ne_modifie_pas_le_stock_rg04` |
| RG05 réception une seule fois | Jeton unique de formulaire | `test_reception_de_20_unites_une_seule_fois_rg05` |
| RG06 vente une seule fois | Jeton unique de caisse | `test_vendre_3_unites_diminue_le_stock_de_3_une_seule_fois_rg06` |
| RG07 stock jamais négatif | `UPDATE … WHERE quantite >= n` | `test_stock_jamais_negatif_rg07` |
| RG08 lots périmés/bloqués exclus | `LotStock.vendables()` + contrôle à la vente | `test_vendre_un_lot_perime_refuse_rg08`, `…bloque…` |
| RG09 auteur, date, historique | `MouvementStock`, `JournalAudit` | `test_mouvement_trace_avant_apres` |
| RG10 pas de suppression sans trace | Annulation et retours compensatoires, admin en lecture seule | `test_annulation_compensatoire_rg10` |
| RG11 accès selon le rôle | `@role_requis` sur chaque vue | `test_acces_sans_permission_interdit_rg11` |
| RG12 prix figés | `LigneVente.prix_unitaire` | `test_prix_fige_au_moment_de_la_vente_rg12` |

Résultat : **49 tests, tous réussis** (1 test ignoré sous SQLite, voir ci-dessous).
Visite automatique de toutes les URL avec les 5 rôles : **0 erreur 500**.

## 4. Fichiers ajoutés ou modifiés

- **Nouveaux** : `ventes/` (modèles, services, vues, formulaires, admin, tests), `stock/views.py`,
  `stock/forms.py`, `stock/urls.py`, `rapports/pdf.py`, `rapports/views.py`, `rapports/urls.py`,
  15 templates (achats, stock, ventes, rapports), commandes `donnees_demo`, `sauvegarder`,
  `restaurer`, `pharmacie/outils_tests.py`, `requirements.txt`, `README.md`.
- **Modifiés** : `settings.py`, `pharmacie/urls.py`, `base.html`, `tableau_de_bord.html`,
  `style.css`, `medicaments/models.py` (stock calculé), fiches médicament, fournisseur et client.
- **Non modifiés** : utilisateurs, médicaments, fournisseurs, clients, achats (modèles et services) —
  votre code y était correct.


