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
import uuid
import hashlib
from servizi.utils import dict_cursor, project, populate_form, StyledSelect, BrRadioSelect
from servizi.utils import messaggio, hist_redirect, aggiungi_banda
from datetime import datetime, timedelta
from django import forms
from django.template.response import TemplateResponse
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.http import HttpResponse
from percorso.views import visualizza_percorso
from servizi import infopoint


risorse1 = ServerVersione("risorse", 1)

@risorse1.xmlrpc("risorse.Rivendite")
@risorse1.logger("Rivendite")
def rivendite(
	request,
	token,
	address,
	civic,
	place,
	nnp,
	coord_x,
	coord_y, 
):
	return hashlib.md5(uuid.uuid1().hex).hexdigest()


# coding: utf-8


class RisorseForm(forms.Form):
	address = forms.CharField()

	def set_error(self, fields):
		for f in fields:
			self.fields[f].widget.attrs.update({'class': 'hlform'})

def estrai_risorse(soup):
	rs = soup.findAll('record')
	out = []
	for r in rs:
		out.append({
			'name': r.find('name').string,
			'address': r.address.string,
			'phone': r.phone.string,
			'place': r.place_.string,
			'distance': r.distance.string,
			'nnp': r.nnp.string,
			'dispnumber': r.dispnumber.string,
		})
	return out 	

def trova_risorse(request, punto):
	ctx = {}
	risorse = estrai_risorse(infopoint.find_resources(request, punto, 48))
	aggiungi_banda(risorse)
	ctx['risorse'] = risorse
	ctx['infopoint'] = request.session['infopoint']
	return TemplateResponse(request, 'risorse-dettaglio.html', ctx)

	
def _place_choice(elem):
	loc, place = elem
	if place != loc:
		return (place, loc, "i")
	return (place, loc) 
	
def _validate_address(address):
	af = None
	pf = None
	error_messages = []
	error_fields = []
	correct_output = None
	res = infopoint.geocode_place(None, address, geocoder='infopoint')
	if address == '':
		error_messages.append(_("indirizzo (manca)"))
		error_fields.append("address")
	if res['stato'] == 'Ambiguous':
		error_messages.append(_("indirizzo (molti trovati)"))
		error_fields.append("address")
		af = forms.TypedChoiceField(choices=[(x, x) for x in res['indirizzi']])
	elif res['stato'] == 'OK':
		correct_output = {
			'address': res['address'],
			'streetno': res['streetno'],
			'nnp': res['nnp'],
			'coord_x': res['x'],
			'coord_y': res['y'],
			'place': res['place'],
		}
	else:
		error_messages.append(_("indirizzo (errato)"))
		error_fields.append("address")
	return af, pf, error_messages, error_fields, correct_output


def default(request):
	error_messages = []
	error_fields = []	
	n = datetime.now()
	ctx = {}

	f = populate_form(request, RisorseForm,
		address='',
	)
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		a1, p1, em1, ef1, start = _validate_address(cd['address'])

		error_messages.extend(em1)
		error_fields.extend(ef1)

		if not (a1 is None and p1 is None):
			class CorreggiRisorseForm(RisorseForm):
				if a1 is not None:
					address = a1
	
			f = populate_form(request, CorreggiRisorseForm)
			
		if len(error_fields) > 0:
			f.set_error(error_fields)
		else:		
			return trova_risorse(request, start)

	ctx.update({'form': f, 'errors': error_messages})
	return TemplateResponse(request, 'risorse.html', ctx)


def mappa(request):
	ctx = {}
	ip = request.session['infopoint']
	risorse = estrai_risorse(ip['soup'])
	aggiungi_banda(risorse)
	ctx['risorse'] = risorse
	ctx['infopoint'] = ip
	ctx['mappa'] = True
	return TemplateResponse(request, 'risorse-dettaglio.html', ctx)

def mappacmd(request, cmd):
	ctx = {}
	ip = request.session['infopoint']
	risorse = estrai_risorse(ip['soup'])
	aggiungi_banda(risorse)
	ctx['risorse'] = risorse
	ctx['infopoint'] = ip
	infopoint.prepare_map(request, number=cmd)
	ctx['mappa'] = True
	return TemplateResponse(request, 'risorse-dettaglio.html', ctx)

def mappaimg(request):
	return HttpResponse(infopoint.get_map(request), mimetype="image/gif")

def percorso(request, id):
	ctx = {}
	id = int(id)
	ip = request.session['infopoint']
	risorse = estrai_risorse(ip['soup'])
	return visualizza_percorso(
		request,
		ip['point']['address'],
		ip['point']['place'],
		risorse[id - 1]['address'],
		risorse[id - 1]['place'],
		1,
		0,
	)
	