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

from parcheggi.models import *
from django.db import models, connections, transaction
from log_servizi.models import ServerVersione
import errors
from servizi.utils import dict_cursor, project
import uuid
import hashlib
import datetime
from django.template.response import TemplateResponse

parcheggi1 = ServerVersione("parcheggi", 1)

@parcheggi1.metodo('Lista')
def lista(request, token):
	try:
		parcheggi = Parcheggio.objects.filter(pubblicato=True)
	except Exception as e:
		raise errors.XMLRPC['XRE_DB']
	out = []
	now = datetime.datetime.now()
	interval = datetime.timedelta(minutes=10)
	for s in parcheggi:
		d = project(
			s,
			'id_parcheggio',
			'nome',
			'posti_totali',
		)
		d['posti_disponibili'] = s.posti_disponibili_non_abbonati
		d['valido'] = (not s.fuori_servizio) and (s.ultimo_aggiornamento + interval > now)
		out.append(d)
	return out
	
def default(request):
	ctx = {}
	ctx['parcheggi'] = Parcheggio.objects.filter(pubblicato=True)
	return TemplateResponse(request, 'parcheggi.html', ctx)
