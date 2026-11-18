#!/usr/bin/env bash
# Installation de PharmaGest (Linux / macOS)
# Usage : ./installer.sh          → installation + données de démonstration
#         ./installer.sh --vide   → installation sans données de démonstration
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "▸ Création de l'environnement virtuel .venv"
  python3 -m venv .venv
fi
source .venv/bin/activate

echo "▸ Installation des dépendances"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "▸ Création / mise à jour des tables"
python manage.py migrate

echo "▸ Création des rôles"
python manage.py init_roles

if [ "$1" != "--vide" ]; then
  echo "▸ Chargement des données de démonstration"
  python manage.py donnees_demo
fi

echo "▸ Vérification"
python manage.py check

echo
echo "Installation terminée. Lancez le serveur avec :"
echo "  source .venv/bin/activate && python manage.py runserver"
echo "puis ouvrez http://127.0.0.1:8000/"
