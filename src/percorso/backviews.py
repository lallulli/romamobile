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
from paline.geomath import wgs84_to_gbfe, gbfe_to_wgs84
from servizi.utils import dict_cursor, project, datetime2mysql, group_required
from datetime import datetime, timedelta, time, date
from jsonrpc import jsonrpc_method
from copy import copy
import rpyc
import cPickle as pickle
import views
from paline import tratto
from pprint import pprint
import urlparse


@jsonrpc_method('percorso_cerca', safe=True)
def percorso_cerca(
	request,
	indirizzo_partenza,
	indirizzo_arrivo,
	opzioni,
	orario,
	lang,
	offset
):
	try:
		orario = datetime.strptime(orario, '%d/%m/%Y %H:%M')
	except Exception:
		return {
			'errore-data': True,
		}

	return views.cerca(
		request, 
		'',
		indirizzo_partenza,
		indirizzo_arrivo,
		opzioni,
		orario.strftime('%Y-%m-%d %H:%M:%S'),
		lang,
		offset
	)


@jsonrpc_method('urldecode', safe=True)
def urldecode(request, urlparams):
	d = urlparse.parse_qs(urlparams)
	return dict([(k, d[k][0]) for k in d])

@jsonrpc_method('percorso_get_params', safe=True)
def percorso_get_params(request):
	infopoint = request.session['infopoint']
	return {
		'route': views.infopoint_to_get_params(infopoint),
		'to': views.infopoint_to_get_params(infopoint, da=False),
	}

@jsonrpc_method('percorso_email', safe=True)
def percorso_email(request, address):
	views.calcola_percorso_mail(request, address)
	return 'OK'


@jsonrpc_method('percorso_posizione_attuale', safe=True)
def percorso_posizione_attuale(request, lon, lat):
	"""
	Aggiorna la posizione attuale sul percorso precedentemente calcolato

	lon, lat: coordinate del punto corrente

	Restituisce un dizionario con i seguenti elementi:
	- distanza: distanza del punto corrente dal percorso, in metri
	- punto_su_percorso: proiezione del punto sul percorso, coordinate (lon, lat)
	- su_percorso: True iff il punto è considerato sul percorso (i.e. distanza <= 200)
	- indice_percorso: indice dell'elemento corrente del percorso (sequenza di nodi e archi)
	- info: informazioni sul tratto corrente, secondo il formato di info_posizione_corrente in paline/tratto.py
	- refresh: intervallo di aggiornamento suggerito, in secondi
	"""
	tr = request.session['percorso-trattoroot']
	posizione = tr.piu_vicino(wgs84_to_gbfe(lon, lat))
	distanza, indici, progressiva, lunghezza, piede_perp = posizione
	opzioni = {}
	indicazioni_icona = tratto.PercorsoIndicazioniIcona()
	tratto.formatta_percorso(tr, 'indicazioni_icona', indicazioni_icona, opzioni, posizione)
	indice_percorso = indicazioni_icona.posizione_corrente
	info = indicazioni_icona.indicazioni[indice_percorso]['tratto']['info_posizione_corrente']
	refresh = 30
	if 'fermate_rimanenti' in info:
		f = info['fermate_rimanenti']
		refresh = 60
		if f <= 4:
			refresh = [15, 20, 30, 40][f - 1]
	return {
		'distanza': distanza,
		'punto_su_percorso': gbfe_to_wgs84(*piede_perp),
		'su_percorso': distanza <= 200,
		'indice_percorso': indice_percorso,
		'info': info,
		'refresh': refresh,
	}