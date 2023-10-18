import requests
import yaml
import logging
import json
import html_to_json
import smtplib
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.message import EmailMessage
import argparse
import os

parser = argparse.ArgumentParser(description='GLPI Contrat Tracker - Config')
parser.add_argument('-u', dest='glpi_url',
                    help="URL de GLPI")
parser.add_argument('-t', dest='api_token',
                    help="Token de l'API")
parser.add_argument('-s', dest='seuil_alert', type=int,
                    help="Seuil d'alerte avant de déclancher l'email")
parser.add_argument('-p', dest='serveur_port', type=int, default=25,
                    help="Port du serveur email")
parser.add_argument('-m', dest='serveur_smtp',
                    help="Adresse du serveur email")
parser.add_argument('-d', dest='email_dest',
                    help="Adresse email à qui envoyer l'alerte")
parser.add_argument('--sav', dest='email_dest_sav',
                    help="Adresse email à qui envoyer l'alerte lors d'erreurs")
args = parser.parse_args()

# Formatage des messages pour la fonction logging
FORMAT_DEBUG = '%(asctime)s - %(levelname)s - %(message)s'
FORMAT_INFO = '%(levelname)s - %(message)s'
logging.basicConfig(format=FORMAT_INFO, level=logging.INFO)


##
# Récupération du fichier de config yaml

def getConfig():
    with open("config.yaml", "r") as f:
        return yaml.load(f, Loader=yaml.FullLoader)
    # Conversion de la config YAML en tableau


##
# Stockage du tableau config dans une variable
config = getConfig()


##
# Connexion à GLPI
def login():
    logging.info("Connexion à GLPI...")
    logging.info("Utilisation d'un Token existant...")
    # Récupération du token généré par le login depuis le fichier session.token
    session_token = getToken()

    # Test d'utilisation du token avec la function getMyProfiles() (qui retourne les différents profils de l'utilisateur, ex: super-admin, technicien etc)
    # Si le token est expiré, il retourne la valeur suivante, il faut donc le réinitialiser
    getprofiles = getMyProfiles(session_token)
    if getprofiles:
        if 'ERROR_SESSION_TOKEN_INVALID' in getprofiles:
            logging.info('Le Token a expiré !')
            logging.info("Génération d'un nouveau Token ...")
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"user_token {args.api_token}"
            }
            try:
                response = json.loads(
                    requests.get(url=args.glpi_url + config['api_url'] + config['endpoints']['getinitSession'],
                                 headers=headers).content)
                # stockage du token généré dans le fichier session.token
                with open("session.token", "w") as f:
                    f.write(response['session_token'])
                    f.close()
                    # renvoi, après l'execution de la fonction, le token
                return True,response['session_token']
            except:
                # Si une erreur est rencontré pendant le login, ex erreur token API, alors le programme coupe.
                logging.warning('ERROR: Connexion echouee !')
                os.remove("session.token")
                return False, {'Error': 'Erreur de connexion à GLPI !'}

        # S'il n'y a pas d'erreur, le token est toujours valide, on le renvoi
        else:
            if session_token:
                return True, session_token
    else:
        return False, {'Error': 'Erreur de connexion à GLPI !'}


##
##
# Récupération du session token pour éviter d'en générer à chaque execution du programme
def getToken():
    try:
        f = open("session.token", "r")
        return f.read()
    except:
        return False


##
# Récupération de tous les profils de l'utilisateur avec la clé API renseignée
def getMyProfiles(session_token):
    headers = {
        "Content-Type": "application/json",
        "Session-Token": f"{session_token}"
    }
    try:
        return json.loads(requests.get(url=args.glpi_url + config['api_url'] + config['endpoints']['getMyProfiles'],
                                       headers=headers).content)
    except:
        return False
        logging.error('ERROR: Impossible de récupérer les profils')


##

##
# Passage du compte connecté, sur l'entité racine. Afin de récupérer l'ensemble des entités clients
# Argument : session_token (récupéré via le login)
def setRootEntity(session_token):
    # Préparation des headers HTTP requis
    headers = {
        "Content-Type": "application/json",
        "Session-Token": f"{session_token}"
    }
    try:
        response = requests.post(url=args.glpi_url + config['api_url'] + config['endpoints']['changeActiveEntities'],
                                 json={"entities_id": 0, "is_recursive": True}, headers=headers).content
        if response:
            logging.info("Changement d'entité effectué avec succès")
            return True
    except:
        logging.error("ERROR: Impossible de changer d'entitée")


##


##
# Changement de profil de l'utilisateur actif sur le profile_id choisi (Nom renseigné dans le config.yaml PROFIL_CONSULTATION_BUDGET)
def changeActiveProfiles(session_token, profile_id):
    headers = {
        "Content-Type": "application/json",
        "Session-Token": f"{session_token}"
    }
    try:
        response = requests.post(url=agrs.glpi_url + config['api_url'] + config['endpoints']['changeActiveProfile'],
                                 json={"profiles_id": profile_id}, headers=headers).content
        if response:
            logging.info('Changement effectué avec succès')
            return True
    except:
        logging.error('ERROR: Impossible de changer de profil')


##

##
# Parsing de la page html affichant le total utilisé sur le budget afin de récupérer la valeur et la comparer avec le total du contrat
# Attention, cette fonction n'utilise pas l'API directe, elle peut donc échouer si la page est modifiée dans une MàJ de GLPI
def getCurrentBudget(session_token, budget_id):
    # utilisation des cookies, on ne passe pas par l'API
    cookies = {
        f"{config['cookie_glpi']}": f"{session_token}"
    }
    # Assignation du token de la session dans les cookies de la requete
    response = requests.get(
        f"{args.glpi_url}/ajax/common.tabs.php?_target=/glpi/front/budget.form.php&_itemtype=Budget&_glpi_tab=Budget$1&id={budget_id}&withtemplate=&formoptions=data-track-changes^%^3Dtrue",
        cookies=cookies).text
    # valeur par défaut du budget
    total_spent_on_budget = 0
    total_remaining_on_budget = 0
    loop_total_spent_budget = False
    loop_total_remaining_budget = False
    # Parsing du HTML pour récupérer la valeur
    for tr in html_to_json.convert(response)["div"][0]["table"][0]["tr"]:
        if 'td' in tr:
            for td in tr['td']:
                if 'numeric' in td['_attributes']['class']:
                    total_spent_on_budget = td['_value']

    # retourne la valeur du budget
    return total_spent_on_budget


##
# Récupération de tous les bugdets
def getBudgets(session_token):
    headers = {
        "Content-Type": "application/json",
        "Session-Token": f"{session_token}"
    }

    # Passage dans l'entitée racine, afin de récupérer tous les budgets et non pas uniquement celui de l'entitée dans laquelle on se trouve
    setRootEntity(session_token)
    try:
        response = json.loads(requests.get(url=args.glpi_url + config['api_url'] + config['endpoints']['getBudget'],
                                           headers=headers).content)
        # Si lors de la requete, l'utilisateur (api_token) n'est pas en administrateur, ou avec les droits necessaires pour consulter la partie 'Budget'
        # la requete retourne une erreur de droit, switch automatique sur le profil "Super-Admin" de l'utilisateur
        if 'ERROR_RIGHT_MISSING' in response:
            logging.warning(f"ERROR: {response[1]}")
            logging.info("Tentative de changement de profil....")
            user_profiles = getMyProfiles(session_token)
            for profile in user_profiles['myprofiles']:
                if config['PROFIL_CONSULTATION_BUDGET'] in profile['name']:
                    if changeActiveProfiles(session_token, profile['id']):
                        # Une fois le profil changé, on relance la demande de budget
                        response = json.loads(
                            requests.get(url=args.glpi_url + config['api_url'] + config['endpoints']['getBudget'],
                                         headers=headers).content)

        entity_data = []
        # On stocke ensuite les données voulues dans un tableau.
        # Chaque entitée est créée dans une nouvelle entrée du tableau
        for budget in response:

            entity_tmp = {}
            entity_tmp['budget_id'] = budget['id']
            entity_tmp['entity_id'] = budget['entities_id']
            for link in budget['links']:
                # On parcoure les liens associés à l'entité,
                # Si l'un d'entre eux contient "Entity", on récupère les informations comme le Nom de l'entité.
                if link['rel'] == "Entity":
                    entity_tmp['name'] = json.loads(requests.get(url=link['href'], headers=headers).content)['name']

            entity_tmp['total_budget_allowed'] = float(budget['value'])
            # Récupération du budget utilisé
            entity_tmp['total_budget_spent'] = float(getCurrentBudget(session_token, entity_tmp['budget_id']))
            # Calcul du pourcentage utilisé
            entity_tmp['budget_alerte'] = round((args.seuil_alert * float(budget['value'])) / 100, 2)
            # Calcul du budget restant
            entity_tmp['total_remaining_budget'] = entity_tmp['total_budget_allowed'] - entity_tmp['total_budget_spent']
            # ajout des données au tableau principal
            entity_data.append(entity_tmp)

        return True, entity_data


    except:
        logging.warning('ERROR: Impossible de récupérer les budgets !')
        return False, {'Error': 'Erreur lors de la récupération des budgets'}


##

##
# Fonction de "debug" - affiche le contenu du tableau budget dans la console
def displayBudget(budget):
    logging.info('#############################################')
    logging.info(f"ID Budget : {budget['budget_id']}")
    logging.info(f"Entité : {budget['name']}")
    logging.info(f"Destinataire(s) alerte : {args.email_dest}")
    logging.info(f"Total contrat d'heures : {budget['total_budget_allowed']}h")
    logging.info(f"Total utilisé : {budget['total_budget_spent']}h")
    logging.info(f"Total restant : {budget['total_remaining_budget']}h")
    logging.info(f"Pourcentage utilisé : {round((budget['total_budget_spent'] * 100) / budget['total_budget_allowed'],2)}%")
    logging.info('#############################################')

##
# Fonction d'envoi d'email si le pourcentage utilisé est arrivé au seuil ou le dépasse
def alertEmail(content):
    msg = EmailMessage()
    msg['From'] = args.email_dest
    msg['To'] = args.email_dest  # ", ".join(receivers)
    msg['Subject'] = f"[Alerte Budgets] - Contrat Heures GLPI"  # Titre de l'email
    # Contenu de l'email, en html
    html_content = f"""
    <html>
      <head></head>
      <body>
        {content}
      </body>
    </html>
    """
    msg.set_content(html_content, subtype='html')
    logging.info(f"Envoi d'email à {args.email_dest}....")
    try:
        with smtplib.SMTP(args.serveur_smtp, args.serveur_port) as server:
            server.send_message(msg)
            logging.info('Envoi réussi!')
    except:
        logging.info("Erreur d'envoi d'email, vérifiez le serveur smtp")


##
# Fonction d'envoi d'email lors d'erreurs
def errorEmail(dest, errors):
    if not dest == None:
        msg = EmailMessage()
        msg['From'] = dest #config['email_errors']
        msg['To'] = dest #config['email_errors']  # ", ".join(receivers)
        msg['Subject'] = f"[GLPI_CT][Erreur] - Contrat Heures GLPI"  # Titre de l'email
        # Contenu de l'email, en html
        html_content = f"""
            <html>
              <head></head>
              <body>
                <p>{errors}</p>
              </body>
            </html>
            """
        msg.set_content(html_content, subtype='html')
        logging.info(f"Envoi d'email à {dest}....")
        try:
            with smtplib.SMTP(args.serveur_smtp, args.serveur_port) as server:
                server.send_message(msg)
                logging.info('Envoi réussi!')
        except:
            logging.info("Erreur d'envoi d'email, vérifiez le serveur smtp")
    else:
        logging.info("Erreur d'envoi d'email, pas de destinataire")



# -------------------------------------------------------------#
# Point d'entrée du programme
# -------------------------------------------------------------#

# Lance la récupération des budget, via le session.token généré par la fonction login()
logging.info('#-------------------------------------------------------#')
logging.info('#---------------- GLPI Contract Tracker ----------------#')
logging.info('#-------------------------------------------------------#')
email_content = """"""

if not args.glpi_url or not args.api_token or not args.seuil_alert:
    logging.info("Erreur, lien de GLPI, Token ou seuil d'alerte manquant")
    parser.print_help()
    exit()
elif not args.serveur_smtp or not args.serveur_port or not args.email_dest:
    logging.info("Erreur: La configuration email n'est pas complète")
    parser.print_help()
    exit()
else:
    login_status, session_token = login()

    if login_status:
        getBudgets_statut, budgets = getBudgets(session_token)

        # Si la récupération des budgets a fonctionnée,
        # alors on les parcours pour vérifier le seuil, s'il est atteint, on expédie l'email d'alerte
        if getBudgets_statut:
            for budget in budgets:
                if budget['total_budget_allowed'] > 0:
                    displayBudget(budget)

                    if ((budget['total_budget_spent'] * 100) / budget['total_budget_allowed']) >= args.seuil_alert:
                        email_content += f"""
                                <p>Le contrat d'heures pour le client <a href="{args.glpi_url}/front/budget.form.php?id={budget['budget_id']}">{budget['name']}</a> est utilisé à {round((budget['total_budget_spent'] * 100) / budget['total_budget_allowed'],2)}%<br/>
                                Le total d'heures du contrat est de : {budget['total_budget_allowed']}h<br/>
                                Le total d'heures utilisés est de : {budget['total_budget_spent']}h<br/>
                                Le total d'heures restantes est de : {budget['total_remaining_budget']}h</p>
                            """


                else:
                    logging.info(f"Le contrat [{budget['name']}] est n'est pas défini. Il est configuré avec 0h")
        else:
            errorEmail(args.email_dest_sav, budgets['Error'])
    else:
        errorEmail(args.email_dest_sav, session_token['Error'])

alertEmail(email_content)