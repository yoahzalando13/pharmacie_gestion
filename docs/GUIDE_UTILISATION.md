# PharmaGest — Guide d'utilisation

Ce guide décrit les tâches courantes, rôle par rôle. Les noms entre **gras** sont ceux des menus et des boutons de l'application.

**Sommaire** : [1. Se connecter](#1-se-connecter) · [2. Repères](#2-repères-dans-linterface) · [3. Médicaments](#3-médicaments-et-catégories) · [4. Fournisseurs et clients](#4-fournisseurs-et-clients) · [5. Achats](#5-approvisionner--commandes-et-réceptions) · [6. Stock](#6-suivre-le-stock) · [7. Caisse](#7-vendre-en-caisse) · [8. Retours](#8-retours-annulations-et-paiements-à-vérifier) · [9. Tableau de bord et rapports](#9-tableau-de-bord-et-rapports) · [10. Administration](#10-administration) · [11. Visite guidée](#11-visite-guidée-avec-les-données-de-démonstration) · [12. Questions fréquentes](#12-questions-fréquentes)

---

## 1. Se connecter

1. Ouvrez l'adresse de l'application (en local : http://127.0.0.1:8000/).
2. Saisissez votre **nom d'utilisateur** et votre **mot de passe**, puis **Se connecter**.
3. Vous arrivez sur le **Tableau de bord**. Le menu ne montre que les pages autorisées pour votre rôle.

Pour changer votre mot de passe : menu de votre nom (en haut à droite) → **Changer mon mot de passe**. Pour quitter : même menu → **Déconnexion**.

Chaque connexion, réussie ou non, est inscrite au journal d'audit.

## 2. Repères dans l'interface

| Élément | Où | Rôle |
|---|---|---|
| Menu principal | Barre du haut | Tableau de bord, Médicaments, Fournisseurs, Clients, Achats, Stock, Ventes, Rapports, Utilisateurs (selon le rôle) |
| Messages | Sous le menu | Vert : action réussie · Orange : avertissement · Rouge : action refusée, avec la raison |
| Filtres | Haut des listes | Recherche, catégorie, statut, tri, période ; **Filtrer** ou la loupe pour appliquer |
| Pastilles colorées | Listes et fiches | État d'un élément : actif, archivé, rupture, périmé, en attente… |
| Pagination | Bas des listes | 15 à 25 lignes par page |

**Ce que fait chaque rôle**

| Rôle | Tâches principales |
|---|---|
| Administrateur | Comptes et rôles, journal d'audit, suppressions ; accès à toutes les pages |
| Pharmacien responsable | Catalogue, achats, stock (dont blocage de lot), caisse, annulation de vente, rapports |
| Gestionnaire de stock | Fournisseurs, commandes, réceptions, corrections, inventaire |
| Caissier | Caisse, clients, retours, vérification des paiements mobile money |
| Responsable de gestion | Consultation : tableau de bord, stock, ventes, achats, rapports et PDF |

## 3. Médicaments et catégories

*Pharmacien responsable (création, modification) — tous les rôles en consultation.*

**Ajouter un médicament** : **Médicaments** → **Ajouter**.

1. Renseignez le nom commercial, la DCI, la forme, le dosage, le laboratoire.
2. Choisissez une **catégorie** dans la liste, ou tapez-en une nouvelle dans *Ou créer une nouvelle catégorie* (pas les deux).
3. Scannez ou saisissez le **code-barres** (facultatif, mais unique).
4. Indiquez le **prix d'achat** et le **prix de vente** (le prix de vente ne peut pas être inférieur au prix d'achat) et le **seuil d'alerte**.
5. Ajoutez une **photo** : JPEG, PNG ou WEBP, 2 Mo au plus.
6. **Enregistrer**.

Le stock ne se saisit pas ici : il apparaît après une réception de commande (section 5).

**Rechercher** : par nom, DCI ou code-barres, avec filtres par catégorie et statut, et tri.

**Modifier** : fiche du médicament → **Modifier**. Changer le prix de vente ne modifie pas les ventes déjà enregistrées.

**Archiver** : fiche → **Archiver**. Un médicament archivé reste dans l'historique mais ne peut plus être vendu ni commandé. **Réactiver** pour l'annuler.

**Supprimer** (administrateur) : si le médicament a déjà un historique (lots, ventes, commandes), il est archivé au lieu d'être supprimé.

**Catégories** : **Médicaments** → **Catégories**. Une catégorie utilisée par un médicament ne peut pas être supprimée.

## 4. Fournisseurs et clients

**Fournisseurs** (*Pharmacien, Gestionnaire de stock*) : **Fournisseurs** → **Ajouter** : nom (unique), téléphone (ex. `034 12 345 67`), e-mail, contact, NIF/STAT, adresse. La fiche affiche l'historique des commandes, le montant commandé et le montant réellement reçu.

**Clients** (*Pharmacien, Caissier*) : **Clients** → **Ajouter** : nom, téléphone, e-mail, adresse. La recherche trouve un numéro avec ou sans espaces. La fiche affiche les achats du client et leur total.

Un fournisseur ou un client qui a un historique est **désactivé** au lieu d'être supprimé.

## 5. Approvisionner : commandes et réceptions

*Pharmacien responsable, Gestionnaire de stock.*

### Passer une commande

1. **Achats** → **Nouvelle commande** → choisissez le fournisseur.
2. Sur la fiche de la commande (statut **Brouillon**), ajoutez chaque médicament : **Médicament**, **Quantité**, **Prix d'achat unitaire**, **Ajouter**. La corbeille retire une ligne.
3. **Valider la commande** : le statut passe à **Commandée**. Les lignes ne sont plus modifiables.
4. **Bon de commande** produit le PDF à envoyer au fournisseur.

Une commande ne change pas le stock : seule la réception le fait.

### Réceptionner une livraison

1. Fiche de la commande → **Réceptionner**.
2. Pour chaque ligne livrée, saisissez la **Quantité reçue**, le **N° de lot** et la **Date de péremption** inscrits sur les boîtes. Laissez 0 pour une ligne non livrée.
3. **Valider la réception**.

Le stock augmente aussitôt, lot par lot. La commande passe à **Partiellement réceptionnée** s'il reste des quantités à recevoir (réceptionnez à nouveau à la prochaine livraison), sinon à **Entièrement réceptionnée**. Le **Bon de réception** est disponible en PDF.

Si vous envoyez le formulaire deux fois (double clic, retour arrière), la deuxième réception est refusée.

**Annuler une commande** : possible tant que rien n'a été reçu (bouton **Annuler**).

## 6. Suivre le stock

**État du stock** (**Stock** → **État du stock**) : pour chaque médicament actif, le stock total et le stock **vendable** (hors lots périmés ou bloqués). Filtres : en rupture, stock faible (sous le seuil), stock correct.

**Fiche de stock d'un médicament** : cliquez sur un médicament pour voir ses lots (ordre de péremption) et ses 30 derniers mouvements.

**Alertes** (**Stock** → **Alertes**) : ruptures, stocks sous le seuil, lots périmés, lots qui périment dans les 90 jours, lots bloqués.

**Mouvements** (**Stock** → **Mouvements**) : historique de toutes les entrées et sorties, avec auteur, date, stock avant et après, référence (commande, vente, retour, inventaire). Ces lignes ne se modifient jamais.

**Corriger un lot** (casse, perte, produit périmé à détruire, erreur de comptage) : fiche de stock → **Corriger** sur la ligne du lot → type de correction, quantité, **motif obligatoire**.

**Bloquer un lot** (*Pharmacien*) — rappel du fabricant, doute sur la qualité : fiche de stock → bouton de blocage du lot, avec un motif. Un lot bloqué n'est plus jamais proposé à la vente ; le même bouton le débloque.

**Inventaire physique** (**Stock** → **Inventaire physique**) :

1. Filtrez éventuellement par catégorie.
2. Saisissez la quantité comptée pour chaque lot vérifié ; laissez vide les lots non comptés.
3. **Enregistrer l'inventaire** : chaque écart crée une correction tracée, avec une référence `INV-…`.

## 7. Vendre en caisse

*Caissier, Pharmacien responsable* : **Ventes** → **Caisse**.

1. **Ajouter des articles** : scannez le code-barres (l'article entre directement dans le panier) ou tapez un nom ou une DCI, puis choisissez la quantité et cliquez sur le chariot.
2. **Vérifier le panier** : modifiez une quantité, ou choisissez un lot précis. Par défaut, *Automatique (FEFO)* sort d'abord le lot qui périme le plus tôt. Une ligne en rouge signale un stock insuffisant.
3. **Encaisser** : choisissez le client (facultatif) et le **mode de paiement**.
   - *Espèces* : saisissez le montant reçu pour obtenir le rendu de monnaie (vide = montant exact).
   - *Mobile money, carte, chèque* : saisissez la référence de la transaction si vous l'avez ; le paiement restera **en attente** jusqu'à sa vérification (section 8).
4. **Confirmer la vente**, puis confirmez le total affiché.
5. Sur la fiche de la vente : **Reçu** (ticket) ou **Facture** en PDF.

Tout est enregistré d'un seul bloc : si un article manque au dernier moment, aucune partie de la vente n'est enregistrée et un message explique pourquoi. Un double clic ne crée pas deux ventes. Les lots périmés ou bloqués ne sont jamais vendus.

**Vider** retire tous les articles du panier.

## 8. Retours, annulations et paiements à vérifier

**Retour produit** (*Caissier, Pharmacien*) : **Ventes** → **Historique des ventes** → ouvrez la vente → **Retour produit**.

1. Choisissez l'article, la quantité retournée (au plus ce qui n'a pas déjà été retourné), le **motif** et le mode de remboursement.
2. Cochez **Remettre en stock** seulement si le produit est intact ; c'est refusé pour un lot périmé ou bloqué.
3. Le montant à rembourser s'affiche. La vente d'origine reste inchangée dans l'historique.

**Annuler une vente** (*Pharmacien*) : fiche de la vente → motif → **Annuler la vente**. Tout le stock est réintégré et la vente reste visible avec le statut *Annulée*. Une vente qui a déjà des retours ne s'annule pas : traitez le reste par des retours.

**Vérifier un paiement mobile money** : fiche de la vente, bloc *Paiements* → saisissez la référence vérifiée sur le relevé de l'opérateur → **Paiement reçu**, ou **Rejeter**. Le tableau de bord indique le nombre de paiements à vérifier.

## 9. Tableau de bord et rapports

**Tableau de bord** (page d'accueil) :

- 4 indicateurs : médicaments actifs, ventes du jour, stocks faibles (dont ruptures), péremptions proches (et lots périmés encore en stock) ;
- activité de la période (aujourd'hui, 7 jours, 30 jours ou dates libres) : nombre de ventes, chiffre d'affaires, encaissements confirmés, marge brute, achats réceptionnés ;
- ventes par jour, produits les plus vendus, alertes, commandes à réceptionner, dernières ventes.

*Chiffre d'affaires*, *encaissements* et *marge* sont distincts : le chiffre d'affaires compte les ventes validées moins les retours ; les encaissements ne comptent que les paiements confirmés ; la marge (prix de vente − prix d'achat) n'est pas un bénéfice net.

**Rapports** (*Pharmacien, Responsable de gestion*) : choisissez la période (**Du**, **au**), puis téléchargez :

| Document | Contenu |
|---|---|
| Rapport des ventes de la période | Indicateurs de la période (CA, encaissements, marge) et liste des ventes |
| Rapport des achats de la période | Réceptions de la période avec commande, fournisseur et montant |
| Rapport de stock (état actuel) | Stock total et vendable par médicament, valeur du stock |
| Produits périmés ou expirant sous 90 jours | Lots à retirer ou à écouler |

## 10. Administration

*Administrateur.*

**Créer un compte** : **Utilisateurs** → **Créer un utilisateur** → identifiant, nom, mot de passe (deux fois), **rôles** à cocher (un employé peut en cumuler plusieurs).

**Modifier un compte** : nom, coordonnées, rôles, compte actif. Vous ne pouvez pas retirer vos propres rôles ni désactiver votre propre compte.

**Désactiver** un employé qui quitte l'officine : son historique est conservé, il ne peut plus se connecter.

**Réinitialiser un mot de passe** : depuis la liste des utilisateurs ; communiquez-le en personne et demandez à l'employé de le changer.

**Journal d'audit** (menu de votre nom → **Journal d'audit**) : qui a fait quoi et quand, avec recherche (utilisateur, objet), filtre par action et par période.

**Sauvegarde** : voir le manuel d'installation, section 7.

## 11. Visite guidée avec les données de démonstration

Après `python manage.py donnees_demo`, mot de passe `Demo-PharmaGest-2026` pour tous les comptes :

1. **`gestion`** : le tableau de bord montre des ventes sur 20 jours, des stocks faibles, un lot proche de la péremption et un lot périmé. **Rapports** → téléchargez les quatre PDF.
2. **`stock`** : **Achats** → la commande en brouillon → **Valider la commande** → **Réceptionner** avec un n° de lot et une date de péremption. Vérifiez la hausse du stock dans **Stock** → **Mouvements**.
3. **`caissier`** : **Caisse** → tapez `3400930000001` (Doliprane) → quantité 2 → *Espèces*, reçu `10000` → **Confirmer la vente** → **Reçu**. Cherchez ensuite *Bétadine* : son seul lot est bloqué, elle apparaît en rupture et ne peut pas être vendue.
4. **`caissier`** : ouvrez la vente payée par carte → **Paiement reçu** avec une référence.
5. **`pharmacien`** : ouvrez une vente → **Annuler la vente** avec un motif ; le stock est réintégré.
6. **`admin_demo`** : **Journal d'audit** retrace toutes ces actions.

## 12. Questions fréquentes

**« Accès interdit »** : votre rôle ne permet pas cette page. Demandez à l'administrateur de vous attribuer le rôle nécessaire.

**Le stock d'un médicament est à 0 alors qu'il reste des boîtes** : ses lots sont peut-être périmés ou bloqués. Regardez sa fiche de stock : le *stock total* compte toutes les boîtes, le *stock vendable* seulement celles qui peuvent être vendues.

**Je me suis trompé de quantité à la réception** : faites une correction de stock sur le lot concerné, avec le motif « erreur de réception ». La réception elle-même n'est pas modifiable, pour garder la trace.

**Un client rapporte un produit** : utilisez **Retour produit**, jamais l'annulation, sauf si toute la vente était une erreur.

**Le prix a changé** : modifiez la fiche du médicament. Les ventes passées gardent leur prix.
