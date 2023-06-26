import os
import numpy as np
import json
import requests
from hashlib import sha256
from time import sleep, time

from docx import Document
from PyPDF2 import PdfFileReader
from PIL import Image
from cv2 import VideoCapture
from py_compile import compile

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class Utilitaires:
    def __init__(self, dossier: str, database: str, api_key: str):
        self.dossier = dossier
        self.database = database
        self.api_key = api_key

    # Afficher un message d'erreur personnalisé pour une meilleure traçabilité des erreurs
    @staticmethod
    def error_message(err_type: str, file_name: str, message: str) -> None:
        rel_file_path = os.path.relpath(file_name)
        print(f"{err_type} sur {rel_file_path}: {message}")

    # Envoyer une alerte avec le message donnéC
    def alerte(self, message: str) -> None:
        print(f"Alerte de sécurité : {message}. L'administrateur a été notifié.")

    # Initialiser la base de données des extensions de fichiers sensibles
    def initialiser_file_extensions_bdd(self) -> list[str]:
        try:
            with open(self.database, "r") as f:
                return [line.lstrip(".") for line in f.read().splitlines()]
        except IOError as e:
            self.error_message("Erreur d'entrée/sortie lors de l'initialisation de la base de données", self.database, e)
            return []

    # Charger tous les fichiers du système à partir du dossier spécifié
    def charger_fichier_systeme(self) -> list[str]:
        try:
            return list(filter(
                lambda f: os.path.isfile(os.path.join(self.dossier, f)) and f != self.database,
                os.listdir(self.dossier)
            ))
        except OSError as e:
            self.error_message("Erreur lors de la récupération des fichiers du système", self.dossier, e)
            return []

    # Détection de comportements suspects
    # - Méthode pour obtenir la taille d'un fichier
    @staticmethod
    def get_file_size(file_path: str) -> int:
        try:
            return os.path.getsize(file_path)
        except OSError as e:
            return -1

    # - Méthode pour vérifier les changements significatifs de taille de fichier
    @staticmethod
    def check_file_size(file_path: str, old_sizes: dict, size_threshold: int) -> bool:
        current_size = Utilitaires.get_file_size(file_path)
        old_size = old_sizes.get(file_path, current_size)
        old_sizes[file_path] = current_size  # Mise à jour de l'ancienne taille
        return abs(current_size - old_size) > size_threshold

    # Méthode pour obtenir le hash SHA-256 d'un fichier
    @staticmethod
    def get_file_hash(file_path: str) -> str:
        # Calculez le hash SHA-256 du fichier pour l'envoyer à VirusTotal
        hash_sha256 = sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except IOError as e:
            return None


class VerificationFichier:
    def __init__(self, file: str, api_key: str):
        self.file = file
        self.api_key = api_key

    # Vérifier si l'extension du fichier donné est dans la base de données
    def verifier_extension(self, extensions):
        _, file_extension = os.path.splitext(self.file)
        file_extension = file_extension[1:]
        return file_extension in extensions

    # Vérifier si le fichier donné peut s'ouvrir
    def verifier_ouverture_fichier(self) -> bool:
        extensions_connues = {
            'docx': Document,
            'pdf': PdfFileReader,
            'jpeg': Image.open,
            'jpg': Image.open,
            'png': Image.open,
            'txt': None,
            'csv': None,
            'xlsx': None,
            'pptx': None,
            'mp3': VideoCapture,
            'mp4': VideoCapture,
            'avi': VideoCapture,
            'gif': Image.open,
            'html': None,
            'xml': None,
            'json': json.load,
            'py': compile,
            'cpp': None,
            'java': None,
            'php': None,
            'c': None
        }
        
        _, extension = os.path.splitext(self.file)
        extension = extension[1:]

        if extension.lower() not in extensions_connues:
            return False

        verifier = extensions_connues[extension.lower()]

        if verifier is None:
            return True

        try:
            if extension.lower() in ['txt', 'csv', 'html', 'xml', 'c', 'cpp', 'java', 'php']:
                with open(self.file, 'r') as f:
                    f.read(1)
            else:
                verifier(self.file)
            return True
        except Exception:
            return False
    
    # Calculer l'entropie d'un fichier avec la formule de l'entropie de Shannon :   H(X) = -Σ [P(x) log2 P(x)]
    def calc_entropie(self) -> float:
        try:
            with open(self.file, 'rb') as f:
                data = np.frombuffer(f.read(), dtype=np.uint8)
            if not data.size:
                return 0
            counts = np.bincount(data)
            # Calculez la probabilité d'occurrence
            probabilities = counts / data.size
            # Remplacez les valeurs de probabilité nulles par un très petit nombre pour éviter la division par zéro
            probabilities[probabilities == 0] = 1e-10
            # Calculez l'entropie
            return -np.sum(probabilities * np.log2(probabilities))
        except Exception as e:
            #print(f"Erreur lors du calcul de l'entropie pour {self.file} : {e}")
            return None

    # Analyser la réputation des fichiers avec VirusTotal
    # - Méthode pour obtenir le hash du fichier
    def get_file_hash(self) -> str:
        return Utilitaires.get_file_hash(self.file)

    # - Vérifier la réputation du fichier en utilisant l'API de VirusTotal
    def check_virustotal(self) -> bool:
        file_id = self.get_file_hash(self.file)
        url = f"https://www.virustotal.com/api/v3/files/{file_id}"
        headers = {"x-apikey": self.api_key, "accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=1000)
        except requests.exceptions.RequestException as e:
            #print(f"Erreur lors de l'appel à l'API de VirusTotal : {e}")
            return False

        if response.status_code == 200:
            json_response = response.json()
            return json_response['data']['attributes']['last_analysis_stats']['malicious'] > 0
        return False


class SurveillanceFichier(FileSystemEventHandler):
    def __init__(self, dossier, extensions, detection):
        super().__init__()
        self.dossier = dossier
        self.extensions = extensions
        self.detection = detection

    def on_created(self, event):
        try:
            if not event.is_directory:
                fichier_path = event.src_path
                fichier_name = os.path.basename(fichier_path)
                if event.event_type == 'created':
                    print(f"Nouveau fichier créé : {fichier_name}")
                self.detection.analyser_fichier_unique(fichier_path, self.extensions)
        except Exception as e:
            self.detection.error_message("Erreur lors de la création du fichier", fichier_name, str(e))

    def on_modified(self, event):
        try:
            if not event.is_directory:
                fichier_path = event.src_path
                fichier_name = os.path.basename(fichier_path)
                print(f"Fichier modifié : {fichier_name}")
                self.detection.analyser_fichier_unique(fichier_path, self.extensions)
        except Exception as e:
            self.detection.error_message("Erreur lors de la modification du fichier", fichier_name, str(e))

    def on_deleted(self, event):
        try:
            if not event.is_directory:
                fichier_path = event.src_path
                fichier_name = os.path.basename(fichier_path)
                print(f"Fichier supprimé ou déplacé hors du répertoire surveillé: {fichier_name}")
        except Exception as e:
            self.detection.error_message("Erreur lors de la suppression du fichier", fichier_name, str(e))

    def on_moved(self, event):
        try:
            if not event.is_directory:
                fichier_path = event.src_path
                fichier_name = os.path.basename(fichier_path)
                dest_path_relative = os.path.relpath(
                    fichier_path, self.dossier)
                print(f"Fichier déplacé du répertoire surveillé vers : {dest_path_relative}")
                self.detection.analyser_fichier_unique(fichier_path, self.extensions)
        except Exception as e:
            self.detection.error_message("Erreur lors du déplacement du fichier", fichier_name, str(e))
    
    def on_encrypted(self, file_path: str):
        size_threshold = 1000  # Taille de seuil en octets pour détecter une modification significative de la taille du fichier
        check_duration = 5  # Durée en secondes pendant laquelle vérifier le fichier
        check_interval = 1  # Intervalle en secondes entre chaque vérification

        start_time = time()
        size_changed = False

        while time() - start_time < check_duration:
            if self.detection.check_file_size(file_path, self.detection.old_sizes, size_threshold):
                size_changed = True

            # Si l'entropie du fichier est élevée et que sa taille a changé, on peut supposer qu'il est en cours de chiffrement
            if size_changed and self.detection.calc_entropie(file_path) > 7:
                return True

            sleep(check_interval)

        return False
    
 
class RansomwareDetection(Utilitaires, VerificationFichier):
    def __init__(self, dossier: str, database: str, api_key: str):
        super().__init__(dossier, database, api_key)
        self.dossier = dossier
        self.database = database
        self.file = ""
        self.old_sizes = {} # Suivre les changements de taille de fichier entre les appels à analyser_fichier_unique()

    # Analyser un seul fichier dans le système
    def analyser_fichier_unique(self, file: str, extensions: list[str]) -> bool:
        file_name = os.path.basename(file)
        self.file = file  # Définir le fichier à analyser
        anomalies = []  # Liste pour stocker les anomalies détectées

        # Vérifier l'extension
        if not self.verifier_extension(extensions):
            anomalies.append(f"L'extension du fichier {file_name} ne figure pas dans la base de données de référence.")

        # Vérifier si le fichier peut être ouvert
        if not self.verifier_ouverture_fichier():
            anomalies.append(f"Le fichier {file_name} ne peut pas être ouvert. Il est possible qu'il soit chiffré.")

        # Vérifier l'entropie du fichier
        if not self.file:
            return False  # Ignorer si le fichier est vide
        entropie = self.calc_entropie()
        if entropie is not None and entropie > 7:
            anomalies.append(f"Le fichier {file_name} a une haute entropie ({entropie}). Il est possible qu'il soit chiffré.")

        # Vérifier les changements significatifs de taille de fichier
        # La taille de fichier doit changer de plus de 1000 octets = 1 ko pour déclencher une alerte
        size_threshold = 1000
        if Utilitaires.check_file_size(self.file, self.old_sizes, size_threshold):
            anomalies.append(f"La taille du fichier {file_name} a changé de manière significative.")

        # Vérifier la réputation du fichier
        if self.check_virustotal():
            anomalies.append(f"Le fichier {file_name} est identifié comme malveillant par VirusTotal.")

        # Afficher les anomalies détectées
        if anomalies:
            for anomalie in anomalies:
                self.alerte(f"Anomalie détectée : {anomalie}")
        else:
            print(f"******* Le fichier {file_name} est probablement sécurisé ********")

        return len(anomalies) > 0

    # Surveiller en temps réel le système pour détecter toute activité suspecte (version optimise)
    def surveiller2(self, frequence: int, stop: int, extensions: list[str]) -> None:
        # Ensemble des fichiers analysés lors de la dernière itération
        fichiers_precedents = set()
        for compteur in range(stop):
            print(
                f"\n-------- Etape de détection n°{compteur + 1} ----------------")
            try:
                # Mettre à jour la liste des fichiers système à chaque itération
                fichiers_actuels = set(self.charger_fichier_systeme())
                # Trouver les nouveaux fichiers ajoutés
                nouveaux_fichiers = fichiers_actuels - fichiers_precedents
                for fichier in nouveaux_fichiers:
                    fichier_path = os.path.join(self.dossier, fichier)
                    self.analyser_fichier_unique(fichier_path, extensions)
                # Mise à jour de l'ensemble des fichiers précédents
                fichiers_precedents = fichiers_actuels
                sleep(frequence)
            except Exception as e:
                self.alerte(f"Erreur système : échec lors de l'accès au journal du système. Détails de l'erreur : {e}")

    # Surveiller les modifications du système de fichiers avec Watchdog
    def surveiller_watchdog(self, extensions):
        event_handler = SurveillanceFichier(self.dossier, extensions, self)
        observer = Observer()
        observer.schedule(event_handler, self.dossier, recursive=True)

        # demander la durée de surveillance à l'utilisateur
        duree_surveillance = int(input("Entrez la durée de surveillance en secondes : "))

        observer.start()
        try:
            # suspendre l'exécution pendant la durée spécifiée
            sleep(duree_surveillance)

            # Appeler on_encrypted pour chaque fichier après la surveillance
            fichiers_systeme = self.charger_fichier_systeme()
            for fichier in fichiers_systeme:
                fichier_path = os.path.join(self.dossier, fichier)
                self.on_encrypted(fichier_path)

        except KeyboardInterrupt:
            observer.stop()
        observer.stop()  # arrêter l'observateur après la durée spécifiée
        observer.join()


# Test
def main():
    def demander_choix(message: str, choix_valides: list[str]) -> str:
        while True:
            choix = input(message).lower()
            if choix in choix_valides:
                return choix
            else:
                print(f"Choisissez une option valide parmi {', '.join(choix_valides)}")

    try:
        # Charger les données à partir du fichier JSON
        with open("./src/config.json", "r") as f:
            config_data = json.load(f)
            dossier = config_data["dossier"]
            database = config_data["database"]
            api_key = config_data["API_KEY"]

        # Initialiser la base de données
        utilitaires = Utilitaires(dossier, database, api_key)
        extensions = utilitaires.initialiser_file_extensions_bdd()

        while True:  # Boucle infinie pour redemander en cas de mauvaise saisie
            mode = demander_choix("""Choisissez le mode d'opération :
                                  \n\t'1' pour une surveillance en temps réel (itérative)
                                  \n\t'2' pour analyser un seul fichier
                                  \n\t'3' pour annuler et quitter le programme
                                  \n\t'4' pour une surveillance en temps réel avec Watchdog (événementielle)
                                  \nVotre choix : """, ['1', '2', '3', '4'])

            detection = RansomwareDetection(dossier, database, api_key)

            if mode == '1':
                while demander_choix("Voulez-vous commencer/continuer la surveillance en temps réel ? (O/N) : ", ['o', 'n']) == 'o':
                    try:
                        # Demander le nombre d'itérations et la fréquence
                        nb_iterations = int(input("Combien de cycles de surveillance voulez-vous exécuter ? : "))
                        frequence = int(input(
                            "Quelle doit être l'intervalle (en secondes) entre chaque cycle de surveillance ? : "))
                    except ValueError:
                        print("Veuillez entrer un nombre entier valide.")
                        continue
                    # Démarrer la surveillance avec les paramètres spécifiés
                    detection.surveiller2(frequence, nb_iterations, extensions)

                print("Surveillance en temps réel arrêtée.")

            elif mode == '2':
                first_time = True
                while demander_choix("Voulez-vous commencer l'analyse d'un fichier ? (O/N) : " if first_time else "Voulez-vous analyser un autre fichier ? (O/N) : ", ['o', 'n']) == 'o':
                    first_time = False
                    # Afficher tous les fichiers dans le dossier
                    fichiers_systeme = utilitaires.charger_fichier_systeme()
                    print("Voici tous les fichiers dans le dossier spécifié :")
                    for i, fichier in enumerate(fichiers_systeme, 1):
                        print(f"{i}. {fichier}")
                    # Demander à l'utilisateur de choisir un fichier à analyser
                    fichier_choisi = None
                    while fichier_choisi is None:
                        try:
                            fichier_choisi = int(input(
                                "Entrez le numéro correspondant au fichier que vous souhaitez analyser : ")) - 1
                            if fichier_choisi < 0 or fichier_choisi >= len(fichiers_systeme):
                                raise ValueError
                        except ValueError:
                            print(
                                "Veuillez entrer un numéro valide correspondant à un fichier.")
                            fichier_choisi = None
                    fichier_path = os.path.join(
                        dossier, fichiers_systeme[fichier_choisi])
                    # Analyser le fichier choisi
                    detection.analyser_fichier_unique(fichier_path, extensions)

                print("Analyse de fichier terminée.")

            elif mode == '4':
                while demander_choix("Voulez-vous commencer/continuer la surveillance en temps réel avec Watchdog ? (O/N) : ", ['o', 'n']) == 'o':
                    # Démarrer la surveillance avec Watchdog
                    detection.surveiller_watchdog(extensions)
                print("Surveillance en temps réel avec Watchdog arrêtée.")

            elif mode == '3':
                if demander_choix("Êtes-vous sûr de vouloir quitter le programme ? (O/N) : ", ['o', 'n']) == 'o':
                    print("Vous avez choisi de quitter le programme. Au revoir.")
                    exit()
                else:
                    print("Retour au menu de sélection du mode d'opération.")

            else:
                print("Le mode choisi n'est pas reconnu. Veuillez réessayer.")

    except KeyboardInterrupt:
        print("\nInterruption du programme par l'utilisateur.")


if __name__ == "__main__":
    main()
