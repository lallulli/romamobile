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
from servizi.utils import dict_cursor, project, messaggio, hist_redirect
import uuid
import hashlib
import datetime
from django.template.response import TemplateResponse
from servizi.models import Lingua, LinguaPreferita
from django.utils import translation
from django.utils.translation import ugettext as _

lingue1 = ServerVersione("lingue", 1)

@lingue1.xmlrpc("lingue.getLingua", require_token=False)
@lingue1.logger("getLingua")
def get_lingua(request, id_utente):
	try:
		l = LinguaUtente.objects.get(id_utente=id_utente)
	except LinguaUtente.DoesNotExist:
		return ''
	except Exception as e:
		raise errors.XMLRPC['XRE_DB']
	return l.lingua

@lingue1.xmlrpc("lingue.setLingua", require_token=False)
@lingue1.logger("setLingua")
def set_lingua(request, id_utente, lingua):
	try:
		l = LinguaUtente.objects.get(id_utente=id_utente)
		l.lingua = lingua
		l.save()
	except LinguaUtente.DoesNotExist:
		LinguaUtente(
			id_utente=id_utente,
			lingua=lingua
		).save()
	except Exception as e:
		raise errors.XMLRPC['XRE_DB']
	return 'OK'

def default(request):
	ctx = {}
	ctx['lingue'] = Lingua.objects.all()
	return TemplateResponse(request, 'lingua.html', ctx)

def set(request, c):
	try:
		l = Lingua.objects.get(codice=c)
		translation.activate(c)
		request.session['lingua'] = l
		if request.user.is_authenticated():
			try:
				lp = LinguaPreferita.objects.get(utente=request.user)
				lp.lingua = l
				lp.save()
			except LinguaPreferita.DoesNotExist:
				LinguaPreferita(utente=request.user, lingua=l).save()		
		return hist_redirect(request, '/', msg=_(u"Lingua impostata"))
	except Lingua.DoesNotExist:
		return messaggio(request, _(u"La lingua non esiste"))