# coding: utf-8

#
#    Copyright 2013-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli and Damiano Morosi
#
#    This file is part of Roma mobile.
#
#    Roma mobile is free software: you can redistribute it
#    and/or modify it under the terms of the GNU General Public License as
#    published by the Free Software Foundation, version 2.
#
#    Roma mobile is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
#    or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
#    for more details.
#
#    You should have received a copy of the GNU General Public License along with
#    Roma mobile. If not, see http://www.gnu.org/licenses/.
#

from models import *
from django.db import models, connections, transaction
from log_servizi.models import ServerVersione
import errors
from servizi.utils import dict_cursor
import uuid
import hashlib
from django.contrib.auth import login, authenticate
from backends import ServiziBackend
from models import *
from datetime import date, time, datetime, timedelta

"""
Come dovrà essere realizzata l'autenticazione dei webservice.


1. Operazioni preliminari

Creare una classe derivata da User, per esempio ServiziUser, con un campo secret.
Creare, inoltre, un backend di autenticazione che accetta il secret come unico parametro:
cerca l'intermediario con tale id e lo restituisce come utente loggato (metodo authenticate).

Bisognerà modificare il client xml-rpc in modo che i metodi abbiano a disposizione l'oggetto request.


2. Accesso dell'utente

Il metodo accedi effettuerà l'autenticazione e il login  dell'utente, attraverso l'id intermediario.

A questo punto django crea una sessione (request.session) con una chiave, che costituisce
il token di autenticazione che il metodo accedi dovrà restituire all'utente:
	token = request.session.session_key


3. Uso dei servizi web

Ogni servizio web dovrà verificare che il token di autenticazione corrisponda a una sessione valida.
A tal fine dovrà sostituire la sessione request.session con la sessione avente per chiave il token:
	from django.contrib.sessions.backends.db import SessionStore     # oppure un altro backend 
	request.session = SessionStore(session_key=token)

Infine dalla sessione dobbiamo ricavare (e verificare) l'utente:
	from django.contrib.auth import get_user
	utente = get_user(request)
"""


autenticazione1 = ServerVersione("autenticazione", 1)

@autenticazione1.xmlrpc("autenticazione.Accedi", require_token=False)
@autenticazione1.logger("accedi")
def accedi(request, secret, id_utente):
	# old: return hashlib.md5(uuid.uuid1().hex).hexdigest()
	u = authenticate(secret=secret)
	if u is None:
		return ''
	login(request, u)
	token = request.session.session_key
	request.session.set_expiry(3600) # 1 ora
	LogAutenticazioneServizi(
		orario=datetime.now(),
		user=u,
		token=token,
		id_utente_interno=id_utente,
	).save()
	return token

