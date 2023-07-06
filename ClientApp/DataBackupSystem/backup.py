import os
import shutil
import datetime
import requests
import re
import uuid
import filecmp
from dotenv import load_dotenv
from ..load_vars import get_values

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))


def full_backup(backup_dir):
    backup_dir = os.path.join(backup_dir, f"backup")

    # Utiliser la fonction get_values pour obtenir les chemins des fichiers
    dossier_paths = get_values("DOSSIERS")

    # Copier chaque fichier dans le répertoire de sauvegarde
    for path in dossier_paths:
        if os.path.isfile(path):
            shutil.copy2(path, backup_dir)
            print(f"Fichier sauvegardé : {path}")
        else:
            print(f"Erreur : Le chemin spécifié n'est pas un fichier valide : {path}")

    print(f"Sauvegarde complète effectuée : {backup_dir}")


def get_last_backup(backup_dir):
    last_backups = [f for f in os.listdir(backup_dir) if f.startswith("backup")]
    if last_backups:
        last_backups.sort(reverse=True)
        return os.path.join(backup_dir, last_backups[0])
    else:
        return None


def partial_backup(backup_dir):
    last_backup = get_last_backup(backup_dir)
    dossier_paths = get_values("DOSSIERS")

    if last_backup is None:
        print("Erreur: Aucune sauvegarde n'a été trouvé ! Veuillez démarrer une sauvegarde complète de la machine ou "
              "bien contactez votre administrateur.")
        return

    # Comparer les fichiers du dernier backup avec les fichiers dans dossier_paths
    for dossier_path in dossier_paths:
        full_dossier_path = os.path.join(last_backup, os.path.basename(dossier_path))

        # Si le fichier n'existe pas dans last_backup
        if not os.path.exists(full_dossier_path):
            print(f"Dossier manquant dans la sauvegarde : {dossier_path}")
            shutil.copytree(dossier_path, full_dossier_path)  # Copier le contenu du dossier dans le dernier backup
        # S'il existe
        else:
            # Vérifier si les fichiers dans le dossier sont différents
            if not filecmp.cmpfiles(dossier_path, full_dossier_path, shallow=False):
                # Mettre à jour les fichiers du dernier backup avec les nouveaux fichiers
                shutil.rmtree(full_dossier_path)  # Supprimer le dossier existant
                shutil.copytree(dossier_path, full_dossier_path)  # Copier les nouveaux fichiers vers le dernier backup

    print("Backtup partielle effectuée avec succès.")



def send_directory_files(directory, url):
    # Créer une archive du répertoire
    base_name = os.path.basename(directory)
    timestamp = datetime.datetime.now().strftime("%d%m%Y%H%M%S")
    archive_name = f"{base_name + timestamp}.zip"
    shutil.make_archive(base_name, 'zip', directory)

    # Envoyer l'archive via sendfile
    with open(directory, 'rb') as f:
        files = {'files': (archive_name, f, 'application/zip')}
        response = requests.post(url, params={"machineAddress": ':'.join(re.findall('..', '%012x' % uuid.getnode())),
                                              "date": datetime.datetime.now()}, files=files,
                                 headers={"Authorization": f"Bearer {os.environ.get('ACCESS_TOKEN')}"})

        # Traiter la réponse du serveur si nécessaire
        if response.status_code == 201:
            print("Répertoire envoyé avec succès !")
        else:
            print("Une erreur est survenue lors de l'envoi !")
            print("Raison : " + response.text)


