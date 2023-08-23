## GLPI Contrat Tracker - Config

	usage: main.py [-h] [-u GLPI_URL] [-t API_TOKEN] [-s SEUIL_ALERT] [-p SERVEUR_PORT] [-m SERVEUR_SMTP]

	GLPI Contrat Tracker - Config

	options:
	  -h, --help       show this help message and exit
	  -u GLPI_URL      URL de GLPI
	  -t API_TOKEN     Token de l'API
	  -s SEUIL_ALERT   Seuil d'alerte avant de déclancher l'email
	  -p SERVEUR_PORT  Port du serveur email
	  -m SERVEUR_SMTP  Adresse du serveur email
  
exemple : 

    main.py -u https://SiteURL.com/glpi -t USER_API_TOKEN -s 80 -m srvemail.com -p 25