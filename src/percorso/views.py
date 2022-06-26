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
import risorse.models
import paline.models
from django.db import models, connections, transaction
from log_servizi.models import ServerVersione
import errors
from time import sleep
from servizi.utils import dict_cursor, project, populate_form, StyledSelect, BrRadioSelect
from servizi.utils import	ricapitalizza, template_to_mail
from servizi.utils import messaggio, hist_redirect, group_excluded, richiedi_conferma
from servizi.utils import modifica_url_con_storia_link, apply_ric, giorni_settimana
from servizi.utils import prossima_data, dateandtime2datetime, datetime2mysql, getdef, setdef
from servizi.models import RicercaRecente, UtenteGenerico
from mercury.models import Mercury
import string
import uuid
import hashlib
from datetime import datetime, date, time, timedelta
from django import forms
from django.contrib.gis.geos import Point
from django.template.response import TemplateResponse
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from django.utils.encoding import force_unicode
from django.utils.safestring import SafeString, SafeUnicode
from django.utils import translation
from django.http import HttpResponse
from django.core.cache import cache
from carpooling.models import get_vincoli
from servizi import infopoint
import settings
from copy import deepcopy, copy
import cPickle as pickle
from paline import mapstraction, gmaps, tratto
from paline import models as palinemodels
from pprint import pprint
from parcheggi import models as parcheggi
import re
import urllib, urllib2
from hashlib import md5
import traceback
from servizi.views import sostituisci_preferiti
import requests

percorso1 = ServerVersione("percorso", 1)
percorso2 = ServerVersione("percorso", 2)

def safe_string_to_unicode(s):
	if type(s) == SafeString or type(s) == SafeUnicode:
		return unicode(s)
	return s

def infopoint_to_cp(request, address):
	address = sostituisci_preferiti(request, address)
	return infopoint.geocode_place(request, address)
	
def infopoint_address_to_string(add):
	address = add['address']
	place = add['place']
	if address.startswith('fermata:'):
		return address
	return "%s, %s" % (address, place)

def inizializza_linee_escluse(linee_escluse=None):
	if linee_escluse is None:
		linee_escluse = {}
		for l in paline.models.LineaSospesa.objects.all():
			linee_escluse[l.id_linea] = l.id_linea.upper()

	return linee_escluse


def cerca(
	request, 
	token,
	indirizzo_partenza,
	indirizzo_arrivo,
	opzioni,
	orario,
	lang,
	offset=0,
):
	"""
	Cerca percorso

	Se indirizzo_arrivo è una lista invece di una stringa, cerca il percorso verso destinazioni multiple
	e restituisce un sommario con le distanze dei punti
	"""

	translation.activate(lang)
	out = {}

	punti = []
	start = infopoint_to_cp(request, indirizzo_partenza)
	punti.append(start)

	if isinstance(indirizzo_arrivo, list):
		cerca_punti = True
		for i in indirizzo_arrivo:
			stop = infopoint_to_cp(request, i)
			if stop['stato'] != 'OK':
				out['errore-arrivo'] = stop
				break
			else:
				punti.append(stop)
	else:
		cerca_punti = False
		stop = infopoint_to_cp(request, indirizzo_arrivo)
		punti.append(stop)
		if stop['stato'] != 'OK':
			out['errore-arrivo'] = stop
	
	if start['stato'] != 'OK':
		out['errore-partenza'] = start
	
	try:
		orario = datetime.strptime(orario, "%Y-%m-%d %H:%M:%S") + timedelta(seconds=offset)
	except Exception:
		out['errore-data'] = True
		
	carpooling = getdef(opzioni, 'carpooling', False)
	quando = getdef(opzioni, 'quando', 2)

	# Begin compatibilità
	if 'fc' in opzioni:
		opzioni['ferro'] = opzioni['fc']
	if 'bici' in opzioni and opzioni['bici']:
		opzioni['mezzo'] = 3
	if 'rev' in opzioni and opzioni['rev']:
		quando = 3

	# End compatibilità
	
	if len(out) == 0:
		request.session['infopoint'] = {
			'punti': punti,
			'piedi': opzioni['piedi'],
			'bus': opzioni['bus'],
			'metro': opzioni['metro'],
			'ferro': opzioni['ferro'],
			'teletrasporto': getdef(opzioni, 'teletrasporto', False),
			'mezzo': opzioni['mezzo'],
			'max_distanza_bici': float(opzioni['max_distanza_bici']),
			'max_distanza': getdef(opzioni, 'max_distanza', 50000),
			'num_ris': getdef(opzioni, 'num_ris', 10),
			'dt': orario,
			'linee_escluse': opzioni['linee_escluse'] if 'linee_escluse' in opzioni else inizializza_linee_escluse(),
			'carpooling': carpooling,
			'carpooling_vincoli': get_vincoli(request.user) if carpooling == 2 else None,
			'tipi_ris': getdef(opzioni, 'tipi_ris', []),
			'quando': quando,
			'parcheggi_scambio': getdef(opzioni, 'parcheggi_scambio', True),
			'parcheggi_autorimesse': getdef(opzioni, 'parcheggi_autorimesse', True),
			'ztl': getdef(opzioni, 'ztl', []),
			'versione': getdef(opzioni, 'versione', 2),
			'hl': lang,
			'cerca_punti': cerca_punti,
			'bici_sul_tpl': getdef(opzioni, 'bici_sul_tpl', False),
		}
		return calcola_percorso_dinamico(request, True)

	return out


def cerca1(
	request,
	token,
	indirizzo_partenza,
	indirizzo_arrivo,
	opzioni,
	orario,
	lang,
	offset=0,
):
	opzioni['versione'] = 1
	return cerca(request, token, indirizzo_partenza, indirizzo_arrivo, opzioni, orario, lang, offset)


# Registrazione ws XML-RPC
percorso1.xmlrpc("percorso.Cerca", cost=15)(percorso1.logger("Cerca")(cerca1))
percorso2.xmlrpc("percorso.Cerca", cost=15)(percorso1.logger("Cerca")(cerca))


def infopoint_normalize(infopoint):
	"""
	Set missing infopoint properties to their default values
	"""
	setdef(infopoint, 'mezzo', 1)
	setdef(infopoint, 'piedi', 1)
	setdef(infopoint, 'bus', True)
	setdef(infopoint, 'metro', True)
	setdef(infopoint, 'ferro', True)
	setdef(infopoint, 'teletrasporto', False)
	setdef(infopoint, 'max_distanza_bici', 5000)
	setdef(infopoint, 'carpooling', False)
	setdef(infopoint, 'data', datetime.now())
	setdef(infopoint, 'quando', 0)
	setdef(infopoint, 'linee_escluse', [])
	setdef(infopoint, 'carpooling_vincoli', None)
	setdef(infopoint, 'ztl', [])
	setdef(infopoint, 'tipi_ris', [])


def infopoint_to_get_params(infopoint, da=True):
	params = {
		'bus': 1 if infopoint['bus'] else 0,
		'metro': 1 if infopoint['metro'] else 0,
		'ferro': 1 if infopoint['ferro'] else 0,
		'mezzo': infopoint['mezzo'],
		'piedi': infopoint['piedi'],
		#'carpooling':infopoint['carpooling'],
		'quando': infopoint['quando'],
		'dt': datetime2mysql(infopoint['dt']),
		'max_distanza_bici': infopoint['max_distanza_bici'] / 1000.0,
		'a': infopoint_address_to_string(infopoint['punti'][1]).encode('utf8'),
		'cp': 1,
		'tipi_ris': ','.join([str(x) for x in infopoint['tipi_ris']]),
		'linee_escluse': ','.join(["%s:%s" % (k, infopoint['linee_escluse'][k]) for k in infopoint['linee_escluse']]) if len(infopoint['linee_escluse']) > 0 else '-',
		'ztl': ','.join(infopoint['ztl']) if 'ztl' in infopoint else '',
		'bici_sul_tpl': 1 if getdef(infopoint, 'bici_sul_tpl', False) else 0,
		'hl': getdef(infopoint, 'hl', 'it'),
	}
	if da:
		params['da'] = infopoint_address_to_string(infopoint['punti'][0]).encode('utf8')
	return urllib.urlencode(params)


def _get_percorso(percorso):
	banda = -1
	numero = -1
	passi = []
	for p in percorso.findAll('description'):
		if p.get('hot_x') is not None:
			banda += 1
			numero += 1
			if banda == 3: banda = 1
			passo = {
				'banda': banda,
				'numero': numero,
				'indicazioni': [],
			}
			passi.append(passo)
			mappa = True
		else:
			mappa = False
		passo['indicazioni'].append({'indicazione': p.text, 'mappa': mappa})
		stopcode = p.get('stopcode')
		if stopcode is not None:
			try:
				palina = paline.models.Palina.objects.by_date().get(id_palina=int(stopcode))
				passo['palina'] = palina
				number_of_lines = int(p.get('lines_descr_items'))
				linee = set()
				for i in range(0, number_of_lines):
					linee.add(p.get('line_descr_%d' % i))
				arrivi = []
				resp = palina.getVeicoli(linee)['veicoli']
				mostra_palina = True				
				for r in resp:
					l = r['linea']
					if l in linee:
						r['mostra_palina'] = mostra_palina
						mostra_palina = False
						ta = int(r['tempo_attesa'])
						if ta == '-1':
							r['tempo_attesa'] = -1
						else:
							r['tempo_attesa'] = ta / 60
						arrivi.append(r)
						linee.remove(l)
				passo['arrivi'] = arrivi
			except paline.models.Palina.DoesNotExist:
				pass		
	return passi


def info_linee_escluse(linee_escluse):
	return [{'id_linea': k, 'nome': linee_escluse[k]} for k in linee_escluse]


class AggiungiPuntoForm(forms.Form):
	address = forms.CharField(widget=forms.TextInput(attrs={'size':'20'}))


def infopoint_to_cache_key(infopoint):
	ck = copy(infopoint)
	dt = infopoint['dt']
	dt = datetime(dt.year, dt.month, dt.day, dt.hour, dt.hour, dt.minute)
	ck['dt'] = dt
	if 'data' in ck:
		del ck['data']
	if 'percorso_auto_salvato' in ck:
		del ck['percorso_auto_salvato']
	return md5(pickle.dumps(ck)).hexdigest()


def calcola_percorso_dinamico(request, webservice=False, ctx=None):
	if ctx is None:
		ctx = {}
	infopoint = request.session['infopoint']
	ctx['infopoint'] = infopoint
	punti = infopoint['punti']
	for p in punti:
		RicercaRecente.update(request, p['ricerca'], p['indirizzo'])

	if not 'hl' in infopoint:
		infopoint['hl'] = request.lingua.codice
	infopoint['start'] = punti[0]
	infopoint['stop'] = punti[-1]
	ctx['mappa_statica'] = not re.search("Android|iPhone", request.META['HTTP_USER_AGENT'])
	ctx['carpooling'] = getdef(infopoint, 'carpooling', False)
	infopoint_normalize(infopoint)

	mezzo = getdef(infopoint, 'mezzo', 1)
	if mezzo == 2:
		tipi_ris = []
		if infopoint['parcheggi_scambio']:
			tipi_ris.append(parcheggi.PARCHEGGI)
		if infopoint['parcheggi_autorimesse']:
			tipi_ris.append(parcheggi.AUTORIMESSE)
		infopoint['tipi_ris'] = tipi_ris
	if mezzo == 4:
		infopoint['tipi_ris'] = [risorse.models.CAR_SHARING]

	if getdef(infopoint, 'cerca_punti', False):
		out = Mercury.sync_any_static(settings.MERCURY_WEB, 'cerca_percorso', infopoint, by_queue=True)
		return out

	t1 = datetime.now()
	ck = infopoint_to_cache_key(infopoint)
	tr = cache.get(ck)
	att = 0

	while att < 8 and tr == 'WAIT':
		att += 1
		sleep(2)
		tr = cache.get(ck)
	if tr == 'WAIT':
		if webservice:
			raise Exception("Service temporarily unavailable")
		else:
			return messaggio(request, _("Il servizio temporaneamente non &egrave; disponibile, riprova pi&ugrave; tardi."))
	if tr is None:
		cache.set(ck, 'WAIT', 60)
		trs = Mercury.sync_any_static(settings.MERCURY_WEB, 'cerca_percorso', infopoint, by_queue=True)
		t2 = datetime.now()
		ctx['tempo_calcolo'] = str(t2 - t1)
		tr = trs['percorso']
		infopoint['percorso_auto_salvato'] = trs['percorso_auto_salvato']
		cache.set(ck, tr, 60)
	request.session['percorso-trattoroot'] = tr
	return formatta_calcola_percorso(request, webservice, ctx, tr)


def formatta_calcola_percorso(request, webservice, ctx, tr, opzioni=None, mail=None):
	infopoint = request.session['infopoint']
	punti = infopoint['punti']
	versione = getdef(infopoint, 'versione', 2)
	if opzioni is None:
		opzioni = {}
	opzioni['versione'] = versione
	data = infopoint['dt']
	ctx['linee_escluse'] = info_linee_escluse(infopoint['linee_escluse'])
	if webservice:
		opzioni['espandi_tutto'] = True
	stat = tratto.PercorsoStat()
	tratto.formatta_percorso(tr, 'stat', stat, opzioni)
	ctx['stat'] = stat
	indicazioni_icona = tratto.PercorsoIndicazioniIcona()
	#tr.stampa()
	tratto.formatta_percorso(tr, 'indicazioni_icona', indicazioni_icona, opzioni)
	ctx['indicazioni_icona'] = indicazioni_icona.indicazioni
	# pprint(indicazioni_icona.indicazioni)
	ctx['numero_ultimo_nodo'] = indicazioni_icona.numero_nodi - 1
	ctx['tempo_reale'] = data < datetime.now() + timedelta(hours=1)
	
	if webservice:
		mappa = gmaps.Map()
		tratto.formatta_percorso(tr, 'mappa', mappa, {})
		mappa = mappa.serialize()
		return {
			'indicazioni': indicazioni_icona.indicazioni,
			'mappa': mappa,
			'stat': stat.__dict__,
			'linee_escluse': ctx['linee_escluse'],
			'bounding_box': tr.get_bounding_box_wgs84(),
		}
	dest_point = Point(punti[-1]['x'], punti[-1]['y'], srid=3004)
	ctx['ad_geom'] = dest_point
	ctx['params'] = infopoint_to_get_params(infopoint)
	indicazioni_icona.mark_safe()

	mezzo = infopoint['mezzo']
	carpooling = infopoint['carpooling']

	auto = mezzo == 0 #TODO
	ctx['auto'] = auto
	if auto and carpooling:
		if not 'indice' in ctx:
			for i in range(len(punti) - 1):
				punti[i]['indice'] = i + 1
				ctx['form'] = AggiungiPuntoForm()
		else:
			for i in range(len(punti) - 1):
				if 'indice' in punti[i]:
					del punti[i]['indice']			
			indice = ctx['indice']
			punti[indice - 1]['indice'] = indice
		mappa = gmaps.Map()
		tratto.formatta_percorso(tr, 'mappa', mappa, {})
		ctx['mappa'] = mark_safe(mappa.render())
		return TemplateResponse(request, 'offri-passaggio.html', ctx)

	carpooling_trovato = False
	if carpooling:
		for i in indicazioni_icona.indicazioni:
			if 'tratto' in i:
				if i['tratto']['mezzo'] == 'CP':
					carpooling_trovato = True
					break
	ctx['carpooling_trovato'] = carpooling_trovato
	"""
	palinemodels.PercorsoSalvato(
		utente_generico=UtenteGenerico.update(request),
		percorso=tr,
		opzioni=trs['opzioni'],
		punti=infopoint['punti'],
	).save()
	"""

	if not 'form' in ctx:
		f = populate_form(request, OpzioniAvanzateForm,
			av_quando=infopoint['quando'] if 'quando' in infopoint else 2,
			av_piedi=infopoint['piedi'],
			av_bus=infopoint['bus'],
			av_metro=infopoint['metro'],
			av_ferro=infopoint['ferro'],
			av_wd=data.weekday(),
			av_bici_sul_tpl=getdef(infopoint, 'bici_sul_tpl', False),
			av_max_distanza_bici=infopoint['max_distanza_bici'] / 1000,
			av_hour="%d" % data.hour,
			av_minute="%d" % ((data.minute / 10) * 10),
			av_parcheggi_scambio=infopoint['parcheggi_scambio'],
			av_parcheggi_autorimesse=infopoint['parcheggi_autorimesse'],
		)
		ctx['form'] = f

	ctx['opzioni_tpl'] = mezzo in [1, 2, 3, 4]
	ctx['opzioni_bnr'] = mezzo == 3
	ctx['opzioni_pnr'] = mezzo == 2
	ctx['modo'] = mezzo

	if mail is not None:
		ctx['params'] = infopoint_to_get_params(infopoint)
		template_to_mail(mail, 'percorso-mail.txt', ctx, True)
	else:
		return TemplateResponse(request, 'percorso-dinamico.html', ctx)


def mappa_dinamico(request):
	ctx = {}
	tr = request.session['percorso-trattoroot']
	mappa = gmaps.Map()
	tratto.formatta_percorso(tr, 'mappa', mappa, {})
	ctx['mappa'] = mark_safe(mappa.render())
	ctx['percorso'] = True
	return TemplateResponse(request, 'map-fullscreen.html', ctx)


def mappa_statica_dinamico(request, zoom=None, center_x=None, center_y=None):
	ctx = {}
	tr = request.session['percorso-trattoroot']
	mappa = gmaps.Map()
	tratto.formatta_percorso(tr, 'mappa', mappa, {})
	ret = mappa.render_static(zoom, center_y, center_x)
	ctx['mappa'] = ret['map']
	ctx['zoom'] = ret['zoom']
	if ret['zoom'] < 19:
		ctx['zoom_up'] = int(ret['zoom']) + 1
	if ret['zoom'] > 9:
		ctx['zoom_down'] = int(ret['zoom']) - 1
	ctx['center_x'] = ret['center_x']
	ctx['center_y'] = ret['center_y']
	ctx['up'] = "%f" % (float(ret['center_y']) + float(ret['shift_v']))
	ctx['down'] = "%f" % (float(ret['center_y']) - float(ret['shift_v']))
	ctx['left'] = "%f" % (float(ret['center_x']) - float(ret['shift_h']))
	ctx['right'] = "%f" % (float(ret['center_x']) + float(ret['shift_h']))
	return calcola_percorso_espandi(request, ctx=ctx)


def aggiorna_posizione(request, id_palina):
	p = palinemodels.Palina.objects.by_date().get(id_palina=id_palina)
	infopoint = request.session['infopoint']
	infopoint['punti'][0] = {
		'address': 'fermata:%s' % id_palina,
		'palina': id_palina,
		'place': 'Roma',
		'indirizzo': "%s (%s)" % (p.nome_ricapitalizzato(), p.id_palina),
		'ricerca': 'fermata:%s' % id_palina,		
	}
	if infopoint['mezzo'] == 3:
		infopoint['mezzo'] = 1
	infopoint['dt'] = datetime.now()
	return calcola_percorso_dinamico(request)


def modo(request, m):
	request.session['infopoint']['mezzo'] = int(m)
	request.session['infopoint']['tipi_ris'] = []
	return calcola_percorso_dinamico(request)


def avanzate(request):
	ctx = {}
	infopoint = request.session['infopoint']
	data = infopoint['dt']
	f = populate_form(request, OpzioniAvanzateForm,
		av_quando=infopoint['quando'] if 'quando' in infopoint else 2,
		av_piedi=infopoint['piedi'],
		av_bus=infopoint['bus'],
		av_metro=infopoint['metro'],
		av_ferro=infopoint['ferro'],
		av_bici_sul_tpl=getdef(infopoint, 'bici_sul_tpl', False),
		av_max_distanza_bici=infopoint['max_distanza_bici'] / 1000,
		av_wd=data.weekday(),
		av_hour="%d" % data.hour,
		av_minute="%d" % ((data.minute / 10) * 10),
		av_parcheggi_scambio=infopoint['parcheggi_scambio'],
		av_parcheggi_autorimesse=infopoint['parcheggi_autorimesse'],
	)
	error_fields = []
	error_messages = []
	n = datetime.now()
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		quando = int(cd['av_quando'])
		if quando == 0:
			dt = n
		elif quando == 1:
			dt = n + timedelta(minutes=5)
		else:
			d = prossima_data(int(cd['av_wd']))
			t = time(int(cd['av_hour']), int(cd['av_minute']))
			dt = dateandtime2datetime(d, t)

		try:
			max_distanza_bici = float(getdef(cd, 'av_max_distanza_bici', infopoint['max_distanza_bici'])) * 1000
		except Exception:
			error_messages.append(_("distanza massima in bici (errata)"))
			error_fields.extend(['av_max_distanza_bici'])
		infopoint['bici_sul_tpl'] = True if 'av_bici_sul_tpl' in cd else False
		if len(error_fields) > 0:
			f.set_error(error_fields)
		else:
			infopoint.update({
				'max_distanza_bici': max_distanza_bici,
				'quando': quando,
				'dt': dt,
			})
			if 'av_piedi' in cd:
				infopoint.update({
					'piedi': int(cd['av_piedi']),
					'bus': 'av_bus' in cd,
					'metro': 'av_metro' in cd,
					'ferro': 'av_ferro' in cd,
					'teletrasporto': 'av_teletrasporto' in cd,
				})
			if infopoint['mezzo'] == 2:
				infopoint.update({
					'parcheggi_scambio': 'av_parcheggi_scambio' in cd,
					'parcheggi_autorimesse': 'av_parcheggi_autorimesse' in cd,
				})

			return calcola_percorso_dinamico(request)

	ctx.update({'form': f, 'errors': error_messages})
	return calcola_percorso_espandi(request, ctx=ctx)


def bici(request, bici):
	infopoint = request.session['infopoint']
	infopoint['mezzo'] = 3 if bici == '1' else 1
	return calcola_percorso_dinamico(request)


def escludi(request, linea):
	infopoint = request.session['infopoint']
	try:
		nome_linea = request.GET['nome']
	except Exception:
		nome_linea = linea
	infopoint['linee_escluse'][linea] = nome_linea	
	return calcola_percorso_dinamico(request)


def includi(request, linea):
	infopoint = request.session['infopoint']
	try:
		del infopoint['linee_escluse'][linea]
	except Exception:
		pass
	return calcola_percorso_dinamico(request)


def offri_passaggio(request):
	infopoint = request.session['infopoint']
	p = palinemodels.PercorsoSalvatoTest(nome=str(datetime.now()))
	p.percorso = infopoint['percorso_auto_salvato']
	p.save()
	return calcola_percorso_dinamico(request)


def calcola_percorso_espandi(request, espandi='', ctx=None):
	if ctx is None:
		ctx = {}
	infopoint = request.session['infopoint']
	ctx['infopoint'] = infopoint
	ctx['mappa_statica'] = not re.search("Android|iPhone", request.META['HTTP_USER_AGENT'])
	opzioni = {'espandi': espandi}
	tr = request.session['percorso-trattoroot']
	return formatta_calcola_percorso(request, False, ctx, tr, opzioni)


def calcola_percorso_mail(request, addresses):
	ctx = {}
	infopoint = request.session['infopoint']
	ctx['infopoint'] = infopoint
	opzioni = {}
	tr = request.session['percorso-trattoroot']
	formatta_calcola_percorso(request, False, ctx, tr, opzioni, mail=addresses)


def calcola_percorso(request, start, stop, mezzo, modo, data):
	ctx = {}
	percorso = infopoint.calculate_route(request, mezzo, modo, start, stop, data)
	ctx['steps'] = _get_percorso(percorso)
	ctx['infopoint'] = request.session['infopoint']
	return TemplateResponse(request, 'percorso-dettaglio.html', ctx)
			
	
def _place_choice(elem):
	loc, place = elem
	if place != loc:
		return (place, loc, "i")
	return (place, loc) 


def _validate_address(request, address, partenza):
	af = None
	pf = None
	error_messages = []
	error_fields = []
	correct_output = None
	cosa = {True: _("partenza"), False: _("arrivo")}[partenza]
	what = {True: 'start', False: 'stop'}[partenza]
	
	if len(address) == 5 and address.isdigit():
		address = "fermata:" + address
	
	if address.startswith('fermata:'):
		id_palina = address[8:]
		ps = palinemodels.Palina.objects.by_date().filter(id_palina=id_palina)
		if len(ps) == 0:
			error_messages.append(_("fermata di %s (non esiste)") % cosa)
			error_fields.append("%s_address" % what)
		else:
			p = ps[0]
			correct_output = {
				'address': address,
				'place': 'Roma',
				'palina': id_palina,
				'indirizzo': "%s (%s)" % (p.nome_ricapitalizzato(), p.id_palina),
				'ricerca': address,				
			}			
	else:
		res = infopoint_to_cp(request, address)
		if address == '':
			error_messages.append(_("indirizzo di %s (manca)") % cosa)
			error_fields.append("%s_address" % what)
		if res['stato'] == 'OK':
			correct_output = res	
		elif res['stato'] == 'Ambiguous':
			error_messages.append(_("indirizzo di %s (molti trovati)") % cosa)
			error_fields.append("%s_address" % what)
			af = forms.TypedChoiceField(choices=[(x, x) for x in res['indirizzi']])
		else:
			error_messages.append(_("indirizzo di %s (errato)") % cosa)
			error_fields.append("%s_address" % what)
	return af, pf, error_messages, error_fields, correct_output


class RisorseForm(forms.Form):
	risorse = forms.ModelMultipleChoiceField(queryset=risorse.models.TipoRisorsa.objects.all())


class PercorsoBaseForm(forms.Form):
	start_address = forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))
	stop_address = forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))
	mezzo = forms.TypedChoiceField(
		choices=(
			(0, _("Mezzo privato")),
			(1, _("Mezzi pubblici")),
			#(2, _("Park and ride")),
			(3, _("Bike and ride")),
			#(4, _("Car sharing")),
		),
		widget=BrRadioSelect,
	)
	quando = forms.TypedChoiceField(
		choices=(
			(0, _(u"Adesso (dati in tempo reale)")),
			(1, _(u"Fra 5 minuti (dati in tempo reale)")),
			(2, _(u"Scegli orario di partenza:")),
			(3, _(u"Scegli orario di arrivo:")),
		),
		widget=BrRadioSelect
	)
	gs = giorni_settimana(capital=True)
	wd = forms.TypedChoiceField(
		choices=[(i, gs[i]) for i in range(7)],
	)
	hour = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(24)])
	minute = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(0, 60, 10)])

	def set_error(self, fields):
		for f in fields:
			self.fields[f].widget.attrs.update({'class': 'hlform'})
		

class OpzioniAvanzateForm(forms.Form):
	av_piedi = forms.TypedChoiceField(
		choices=(
			(0, _(u"Bassa (camminatore lento)")),
			(1, _(u"Media")),
			(2, _(u"Alta (camminatore veloce)")),
		),
		widget=BrRadioSelect,
	)
	av_quando = forms.TypedChoiceField(
		choices=(
			(0, _(u"Adesso (dati in tempo reale)")),
			(1, _(u"Fra 5 minuti (dati in tempo reale)")),
			(2, _(u"Scegli orario partenza:")),
			(3, _(u"Scegli orario arrivo:")),
		),
		widget=BrRadioSelect
	)
	gs = giorni_settimana(capital=True)
	av_wd = forms.TypedChoiceField(
		choices=[(i, gs[i]) for i in range(7)],
	)
	av_hour = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(24)])
	av_minute = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(0, 60, 10)])

	av_bici_sul_tpl = forms.BooleanField()
	av_max_distanza_bici = forms.FloatField(widget=forms.TextInput(attrs={'size':'3'}))
	av_bus = forms.BooleanField()
	av_metro = forms.BooleanField()
	av_ferro = forms.BooleanField()
	av_teletrasporto = forms.BooleanField()

	av_parcheggi_scambio = forms.BooleanField()
	av_parcheggi_autorimesse = forms.BooleanField()
		
	def set_error(self, fields):
		for f in fields:
			self.fields[f].widget.attrs.update({'class': 'hlform'})


def default(request):
	error_messages = []
	error_fields = []	
	n = datetime.now()
	ctx = {}
	request.GET = dict([(k, request.GET[k]) for k in request.GET])
	
	if request.user.is_authenticated():
		luoghi_preferiti = IndirizzoPreferito.objects.filter(user=request.user)
		ctx['luoghi_preferiti'] = luoghi_preferiti
		
	bt = [k for k in request.GET if k[:3] == 'bt-']
	if len(bt) > 0:
		bt = bt[0]
		cmd = bt[3]
		id = int(bt[4:])
		if cmd == 's' or cmd == 't':
			request.GET = dict([(k, request.GET[k]) for k in request.GET])
			e = 'start_' if cmd == 's' else 'stop_'
			i = IndirizzoPreferito.objects.get(user=request.user, pk=id)
			request.GET[e + "address"] = u"%s, %s" % (i.indirizzo, i.luogo)
		elif cmd == 'e':
			return elimina_indirizzo(request, id)
	
	if 'Inverti' in request.GET:
		request.GET['start_address'], request.GET['stop_address'] = request.GET['stop_address'], request.GET['start_address']
		
	start_address = request.GET['start_address'] if 'start_address' in request.GET else ''
	stop_address = request.GET['stop_address'] if 'stop_address' in request.GET else ''
	
	f = populate_form(request, PercorsoBaseForm,
		mezzo=1,
		quando=1,
		wd=n.weekday(),
		hour="%d" % n.hour,
		minute="%d" % ((n.minute / 10) * 10),
		start_address=start_address,
		stop_address=stop_address,
	)

	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		a1, p1, em1, ef1, start = _validate_address(request, cd['start_address'],  True)
		a2, p2, em2, ef2, stop = _validate_address(request, cd['stop_address'], False)
		error_messages.extend(em1 + em2)
		error_fields.extend(ef1 + ef2)
		
		quando = int(cd['quando'])
		
		if quando == 0:
			dt = n
		elif quando == 1:
			dt = n + timedelta(minutes=5)
		else:
			d = prossima_data(int(cd['wd']))
			t = time(int(cd['hour']), int(cd['minute']))
			dt = dateandtime2datetime(d, t)

		if not (a1 is None and p1 is None and a2 is None and p2 is None):
			class CorreggiPercorsoForm(PercorsoBaseForm):
				if a1 is not None:
					start_address = a1
				if a2 is not None:
					stop_address = a2
	
			if not 'wd' in cd:
				cd['wd'] = n.weekday(),
				cd['hour'] = "%02d" % n.hour,
				cd['minute'] = "%02d" % ((n.minute / 10) * 10),
	
			f = populate_form(request, CorreggiPercorsoForm,
				mezzo=cd['mezzo'],
				quando=cd['quando'],
				wd=cd['wd'],
				hour=cd['hour'],
				minute=cd['minute'],
			)
			
			
		if len(error_fields) > 0:
			f.set_error(error_fields)
		else:
			request.session['infopoint'] = {
				'punti': [start, stop],
				'mezzo': int(cd['mezzo']),
				'piedi': 1,
				'bus': True,
				'metro': True,
				'ferro': True,
				'teletrasporto': False,
				'max_distanza_bici': 5000,
				'carpooling': False,
				'dt': dt,
				'linee_escluse': inizializza_linee_escluse(),
				'quando': quando,
				'parcheggi_scambio': True,
				'parcheggi_autorimesse': False,
				#'tipi_ris': [r.nome for r in risorse_form.cleaned_data['risorse']],
			}				
			return calcola_percorso_dinamico(request)


	ctx.update({'form': f, 'errors': error_messages})
	return TemplateResponse(request, 'percorso.html', ctx)

def da_palina(request, id_palina):
	indirizzo = request.GET['stop_address']
	linee = palinemodels.Linea.objects.by_date().filter(id_linea=indirizzo)
	if len(linee) > 0:
		return hist_redirect(request, '/paline/linea/%s' % indirizzo)
	request.GET = {
		'start_address': 'fermata:%s' % id_palina,
		'stop_address': indirizzo,
		'Submit': 'Calcola',
		'bus': 'on',
		'metro': 'on',
		'ferro': 'on',
		'mezzo': '1',
		'piedi': '1',
		'quando': '0',
		'max_distanza_bici': '5.0',
	}
	return default(request)

@richiedi_conferma(_('Confermi di voler eliminare l\'indirizzo?'))
def elimina_indirizzo(request, id):
	IndirizzoPreferito.objects.filter(user=request.user, pk=id).delete()	
	return hist_redirect(request, '/percorso', msg=(u"Indirizzo preferito eliminato"))


def visualizza_percorso(request, start_address, start_place, stop_address, stop_place, mezzo, opzioni):
	a1, p1, em1, ef1, start = _validate_address(request, start_address, start_place, True)
	a2, p2, em2, ef2, stop = _validate_address(request, stop_address, stop_place, False)
	return calcola_percorso(request, start, stop, mezzo, opzioni, datetime.now())


def mappa(request, numero):
	ctx = {}
	ip = request.session['infopoint']
	ctx['steps'] = _get_percorso(ip['soup'])
	ctx['infopoint'] = ip
	ctx['mappa'] = numero
	infopoint.prepare_map(request, number=numero)
	return TemplateResponse(request, 'percorso-dettaglio.html', ctx)

def dettaglio(request):
	ctx = {}
	ip = request.session['infopoint']
	ctx['steps'] = _get_percorso(ip['soup'])
	ctx['infopoint'] = ip
	return TemplateResponse(request, 'percorso-dettaglio.html', ctx)

def mappaimg(request):
	return HttpResponse(infopoint.get_map(request), mimetype="image/gif")

@group_excluded('readonly')
def preferiti_aggiungi(request, estremo):
	e = 'start' if estremo == 's' else 'stop'
	punto = request.session['infopoint'][e]
	IndirizzoPreferito(
		user=request.user,
		nome = punto['address'],
		indirizzo = punto['address'],
		luogo = punto['place'],
	).save()
	return hist_redirect(request, '/percorso/espandi', msg=_(u"Luogo aggiunto ai preferiti"))


def trovaci(request, a):
	ctx={'a': a}
	return TemplateResponse(request, 'trovaci.html', ctx)

def cerca_luogo_custom(request, id_tipo_ris):
	ctx={'id_tipo_ris': id_tipo_ris}
	tr = risorse.models.TipoRisorsa.objects.get(id=id_tipo_ris)
	ctx['tipo'] = tr.nome
	return TemplateResponse(request, 'cerca_luogo_custom.html', ctx)

def aggiungi_widget(request):
	ctx ={}
	class IndirizzoLocaleForm(forms.Form):
		indirizzo = forms.CharField(widget=forms.TextInput(attrs={'size':'20'}))
	indirizzo=""
	f = populate_form(request, IndirizzoLocaleForm,	indirizzo=indirizzo,
	)
	
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		indirizzo=cd['indirizzo']
		ind=urllib.urlencode({'a': indirizzo})
		ctx['iframe']='<iframe src="http://127.0.0.1:8000/percorso/trovaci?%s" scrolling="no" style="width:400px; height:50px; border-radius: 20px; -webkit-border-radius:20px; -moz-border-radius:20px" frameborder="0" ></iframe>' %ind
		ctx['indirizzo']=ind
		return TemplateResponse(request, 'aggiungi_widget.html', ctx)
	ctx['form']=f
	
	return TemplateResponse(request, 'crea_widget.html', ctx)

def percorso_js(request):
	ctx = {}
	if 'stylesheet' in request.GET:
		ctx['css'] = request.GET['stylesheet']
	return TemplateResponse(request, 'percorso-js.html', ctx)
