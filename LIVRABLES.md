# PharmaGest — Index des livrables

pour un vue de tableau fait (crtl + shift + v)

Chaque livrable demandé, et où le trouver dans le projet.

| # | Livrable | Où | Contenu |
|---|---|---|---|
| 1 | Code source complet du projet Django | Tout le dossier ; applications `utilisateurs/`, `medicaments/`, `fournisseurs/`, `clients/`, `achats/`, `stock/`, `ventes/`, `rapports/` ; configuration `pharmacie/` | Modèles, vues, formulaires, services métier, URL, administration Django, commandes de gestion |
| 2 | Base de données et migrations | `db.sqlite3` ; `*/migrations/` (9 fichiers) | Base SQLite. `python manage.py migrate` la met à jour (voir le manuel, §3) ; `installer.sh` / `installer.bat` construit une base complète avec les données de démonstration |
| 3 | Modèles et relations | `*/models.py` ; [Dossier de conception §4 à §6](docs/DOSSIER_CONCEPTION.md#4-modèle-conceptuel-de-données-mcd) ; diagramme de classes | 16 modèles métier, clés étrangères, contraintes d'unicité, politique de suppression |
| 4 | Pages HTML, CSS et Bootstrap | `templates/` (30 gabarits) ; `static/css/style.css` | Gabarit commun `base.html`, Bootstrap 5.3, thème blanc et vert, mise en page adaptée au mobile et à l'impression |
| 5 | Formulaires CRUD avec photos | `medicaments/forms.py`, `medicaments/views.py` ; `fournisseurs/`, `clients/`, `utilisateurs/` ; `templates/formulaire.html` | Créer, lire, modifier, archiver ou supprimer les médicaments (photo JPEG / PNG / WEBP, 2 Mo maximum, contrôlée), catégories, fournisseurs, clients, utilisateurs |
| 6 | Modules d'achats, de ventes et de stock | `achats/`, `ventes/`, `stock/` (`services.py` pour les règles métier) | Commande → validation → réception par lot ; caisse avec scan, FEFO, paiements, retours, annulation ; lots, mouvements tracés, alertes, corrections, inventaire, blocage |
| 7 | Gestion des utilisateurs et des permissions | `utilisateurs/` (`permissions.py`, `views.py`, `signals.py`) ; commande `init_roles` | 5 rôles, décorateur `@role_requis` sur chaque vue, comptes, réinitialisation de mot de passe, journal d'audit des connexions et opérations sensibles |
| 8 | Rapports PDF et tableau de bord | `rapports/pdf.py`, `rapports/views.py` ; `templates/tableau_de_bord.html`, `templates/rapports/index.html` | 8 documents PDF (reçu, facture, bon de commande, bon de réception, rapports de ventes, d'achats, de stock et de péremptions) ; tableau de bord avec indicateurs, période, histogramme, top produits, alertes |
| 9 | Jeu de données fictives | `utilisateurs/management/commands/donnees_demo.py` | 5 comptes (un par rôle), 8 médicaments, 2 fournisseurs, 2 clients, 3 commandes, 13 ventes sur 20 jours, retour, annulation, lots périmé, proche de la péremption et bloqué |
| 10 | Tests automatisés | `*/tests.py`, `pharmacie/outils_tests.py` | 68 tests : modèles, formulaires, photos, permissions par rôle, achats, stock, ventes, retours, PDF, règles RG02 à RG12. Lancer : `python manage.py test` |
| 11 | Manuel d'installation et de configuration | [docs/MANUEL_INSTALLATION.md](docs/MANUEL_INSTALLATION.md) ; `installer.sh`, `installer.bat` | Prérequis, installation scriptée ou pas à pas, configuration, tests, sauvegarde, mise en production, dépannage |
| 12 | Guide d'utilisation | [docs/GUIDE_UTILISATION.md](docs/GUIDE_UTILISATION.md) | Tâches par rôle, de la connexion aux rapports, visite guidée avec les données de démonstration, questions fréquentes |
| 13 | Dossier de conception (MCD, MLD, UML) | [docs/DOSSIER_CONCEPTION.md](docs/DOSSIER_CONCEPTION.md) ; `docs/diagrammes/` (PNG, SVG et sources) | Règles de gestion, MCD Merise, MLD et passage MCD → MLD, dictionnaire des données, 4 diagrammes de cas d'utilisation, diagramme de classes, 2 diagrammes de séquence, 2 diagrammes d'états, diagramme de composants |

## Démarrage en trois commandes

```bash
./installer.sh                          # Windows : installer.bat
source .venv/bin/activate               # Windows : .venv\Scripts\activate
python manage.py runserver              # puis http://127.0.0.1:8000/
```

Comptes de démonstration : `admin_demo`, `pharmacien`, `stock`, `caissier`, `gestion` — mot de passe `Demo-PharmaGest-2026`.
