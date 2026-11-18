@echo off
REM Installation de PharmaGest (Windows)
REM Usage : installer.bat          -> installation + donnees de demonstration
REM         installer.bat --vide   -> installation sans donnees de demonstration
cd /d "%~dp0"

if not exist .venv (
  echo Creation de l'environnement virtuel .venv
  py -m venv .venv || goto :erreur
)
call .venv\Scripts\activate.bat

echo Installation des dependances
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || goto :erreur

echo Creation / mise a jour des tables
python manage.py migrate || goto :erreur

echo Creation des roles
python manage.py init_roles || goto :erreur

if not "%1"=="--vide" (
  echo Chargement des donnees de demonstration
  python manage.py donnees_demo || goto :erreur
)

python manage.py check || goto :erreur
echo.
echo Installation terminee. Lancez le serveur avec :
echo   .venv\Scripts\activate ^&^& python manage.py runserver
echo puis ouvrez http://127.0.0.1:8000/
goto :eof

:erreur
echo.
echo L'installation a echoue : lisez le message ci-dessus.
exit /b 1
