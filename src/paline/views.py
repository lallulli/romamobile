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

# from xmlrpchandler import XMLRPCService, xmlrpcremote 
from collections import defaultdict
from paline.models import *
from log_servizi.models import ServerVersione, Versione
from servizi.infopoint import cerca_ricerca_errata
from servizi.models import RicercaRecente
import errors
from servizi.utils import datetime2mysql, populate_form, aggiungi_banda, messaggio, hist_redirect, AtacMobileForm
from servizi.utils import BrCheckboxSelectMultiple, group_excluded, mysql2date, date2mysql, mysql2datetime
from servizi.utils import date2datetime, datetime2date, group_required, multisplit, is_int, unmarshal_datetime
from servizi.utils import richiedi_conferma, datetime2compact
from servizi.views import sostituisci_preferiti
import traceback
import logging
from django import forms
from django.template.response import TemplateResponse
from django.core import serializers
from xml.dom import minidom
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.utils.encoding import force_unicode
from itertools import chain
from django.utils.html import escape, conditional_escape
from django.utils.safestring import mark_safe
from PIL import Image, ImageDraw, ImageFont
from StringIO import StringIO
from django.http import HttpResponse
import rpyc 
import settings
from paline import gmaps
from datetime import date, time, datetime, timedelta
from django.template.defaultfilters import date as datefilter
from django.template.loader import render_to_string
from django.views.defaults import server_error
import re
from urllib import quote
from servizi import infopoint
import string
import pickle
import os, os.path
import xmlrpclib
from paline.geomath import gbfe_to_wgs84
from xhtml.templatetags.format_extras import arrotonda_distanza
from mercury.models import Mercury, Job
import hashlib
from pprint import pprint


logger = logging.getLogger('paline')

# xmlrpcservice = XMLRPCService()
paline7 = ServerVersione("paline", 7)


@paline7.metodo("Veicoli")
def PalinaVeicoli(request, token, id_palina, lingua):
	translation.activate(lingua)
	try:
		palina = Palina.objects.by_date().get(id_palina=id_palina)
	except:
		raise errors.XMLRPC['XRE_NO_ID_PALINA'] 
	veicoli = palina.getVeicoli()
	return veicoli


@paline7.metodo("Previsioni")
def PalinaPrevisioni(request, token, id_palina, lingua):
	translation.activate(lingua)
	try:
		p = Palina.objects.by_date().get(id_palina=id_palina)
	except:
		raise errors.XMLRPC['XRE_NO_ID_PALINA'] 	
	prev = _dettaglio_paline(request, p.nome, [p], aggiungi=p.id_palina, as_service=True)
	prev['collocazione'] = p.descrizione
	return prev


@paline7.metodo("Veicoli.Filtra")
def PalinaVeicoliFiltra(request, token, id_palina, linea, lingua):
	try:
		palina = Palina.objects.by_date().get(id_palina=id_palina)
	except:
		raise errors.XMLRPC['XRE_NO_ID_PALINA'] 
	veicoli = palina.getVeicoli(linea)
	return veicoli


@paline7.metodo("Percorsi")
def LineaPercorsi(request, token, id_linea, lingua):
	try:
		linea = Linea.objects.by_date().get(id_linea=id_linea)
	except:
		raise errors.XMLRPC['XRE_NO_LINEA']
	return linea.getPercorsi()


@paline7.metodo("Fermate")
def PercorsoFermate(request, token, id_percorso, lingua):
	try:
		percorso = Percorso.objects.by_date().get(id_percorso=id_percorso, soppresso=False)
	except:
		raise errors.XMLRPC['XRE_NO_PERCORSO']
	return percorso.getFermate()

@paline7.metodo("Percorso")
def ws_percorso(request, token, id_percorso, id_veicolo, giorno_partenze, lingua):
	if id_veicolo == '':
		id_veicolo = None
	if giorno_partenze == '':
		giorno_partenze = None
	else:
		giorno_partenze = mysql2date(giorno_partenze)
	
	return _percorso(request, id_percorso, id_veicolo=id_veicolo, giorno_partenze=giorno_partenze, as_service=True)


@paline7.metodo("PalinaLinee")
def PalinaLinee(request, token, id_palina, lingua):
	try:
		palina = Palina.objects.by_date().get(id_palina=id_palina)
	except:
		raise errors.XMLRPC['XRE_NO_ID_PALINA']
	return palina.getLinee()


@paline7.metodo("ProssimaPartenza")
def ProssimaPartenza(request, token, id_percorso, lingua):
	logger.debug("Prossima Partenza invocato")
	try:
		percorso = Percorso.seleziona_con_cache(id_percorso=id_percorso)
		pp = percorso.getProssimaPartenza()
	except Exception as e:
		raise errors.XMLRPC['XRE_NO_PERCORSO']
	return datetime2mysql(pp)


# Xhtml
class MultiForm(AtacMobileForm):
	cerca = forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))

class PercorsoForm(forms.Form):
	stop_address = forms.CharField()

def _dettaglio_paline_app(request, palina):
	p = palina
	prev = _dettaglio_paline(request, p.nome, [p], aggiungi=p.id_palina, as_service=True)
	# Workaround per eliminare la prossima partenza da capolinea dai dati in forma strutturata,
	# poiché essa è già contenuta nell'annuncio, e le vecchie versioni dell'app la mostrerebbero due volte.
	if 'arrivi' in prev:
		for arrivo in prev['arrivi']:
			if 'partenza' in arrivo:
				arrivo['partenza'] = ''
	if 'primi_per_palina' in prev:
		for primi in prev['primi_per_palina']:
			if 'arrivi' in primi:
				for arrivo in primi['arrivi']:
					if 'partenza' in arrivo:
						arrivo['partenza'] = ''
	prev['collocazione'] = p.descrizione
	if request.user.is_authenticated():
		preferito = PalinaPreferita.objects.filter(gruppo__user=request.user, id_palina=p.id_palina).count() > 0
	else:
		preferito = False
	prev['esiste_preferito'] = preferito
	return prev


def _dettaglio_paline(request, nome, paline, linee_escluse=[], aggiungi=None, ctx=None, as_service=False):
	if ctx is None:
		ctx = {}
	if not as_service:
		ctx['aggiungi'] = aggiungi
	ctx['nome'] = nome
	# try:
	caching = True
	v1, v2, v3, carteggi_usati = dettaglio_paline(nome, paline, linee_escluse, aggiungi, caching, as_service)
	# except Exception:
	# 	return TemplateResponse(request, 'problemi-tecnici.html')
	v_primi = v1 + v3
	primi_per_palina = {}
	for v in v_primi:
		id_palina = v['id_palina']
		if not id_palina in primi_per_palina:
			primi_per_palina[id_palina] = {
				'id_palina': id_palina,
				'nome_palina': v['nome_palina'],
				'arrivi': [],
			}
		primi_per_palina[id_palina]['arrivi'].append(v)
	arrivi_per_palina = []
	for id_palina in primi_per_palina:
		a = primi_per_palina[id_palina] 
		a['arrivi'].sort(key=lambda v: v['linea'])
		arrivi_per_palina.append(a)
	arrivi_per_palina.sort(key=lambda a: a['nome_palina'])
	ctx['primi_per_palina'] = arrivi_per_palina
	v_tutti = v1 + v2
	v_tutti.sort(cmp=cmp_tempi_attesa)
	aggiungi_banda(v_tutti)

	ctx['arrivi'] = v_tutti
	if not as_service:
		ctx['percorso_form'] = populate_form(request, PercorsoForm, stop_address='')
	if len(carteggi_usati) > 0:
		ctx['carteggi'] = [{'nome': k, 'descrizione': Carteggio.objects.by_date().get(codice=k).descrizione} for k in carteggi_usati]
	if not as_service and len(paline) > 1:
		ctx['mostra_palina'] = True
	if as_service:
		return ctx
	return TemplateResponse(request, 'paline-dettaglio.html', ctx)


def percorsi_linea(request, l):
	ctx = {}
	ctx['linea'] = l
	ctx['percorsi'] = Percorso.objects.by_date().filter(linea=l, soppresso=False)
	ctx['abilitata'] = l.abilitata_complessivo()
	if not ctx['abilitata']:
		ctx['news'] = l.news_disabilitazione_complessivo()
	return TemplateResponse(request, 'paline-percorsi.html', ctx)


def palina(request, id_palina, ctx=None):
	if ctx is None:
		ctx = {}
	try:
		p = Palina.objects.by_date().get(id_palina=id_palina, soppressa=False)
		nome = "%s (%s)" % (p.nome_ricapitalizzato(), p.id_palina)
		# ctx['mappa_statica'] = not re.search("Android|iPhone", request.META['HTTP_USER_AGENT'])
		ctx.update({'id_palina': id_palina, 'palina': p, 'ad_geom': p.geom})
		RicercaRecente.update(request, "fermata:%s" % id_palina, nome)
		return _dettaglio_paline(request, nome, [p], aggiungi=p.id_palina, ctx=ctx)
	except Palina.DoesNotExist:
		return TemplateResponse(request, 'messaggio.html', {'msg': _("La palina %s non esiste") % id_palina})


def gruppo(request, id_gruppo):
	try:
		gp = GruppoPalinePreferite.objects.get(user=request.user, pk=id_gruppo)
		nome = unicode(gp)
		paline = gp.palinapreferita_set.all()
		linee_escluse = [l.id_linea for l in gp.lineapreferitaesclusa_set.all()]
		return _dettaglio_paline(request, nome, paline, linee_escluse, ctx={'id_gruppo': id_gruppo})
	except GruppoPalinePreferite.DoesNotExist:
		return TemplateResponse(request, 'messaggio.html', {'msg': _("La palina o il gruppo di paline richiesto non esiste")})


def filtraNone(arr):
	# filtra i valori None da un array associativo, necessario per xmlrpc
	for k, v in arr.iteritems():
		if arr[k] is None:
			arr[k] = ''
	return arr


def trovalinea_veicoli_locale(request, id_palina, id_percorso="", capolinea=False):
	if id_percorso is None:
		id_percorso = ""
	ctx = []
	try:
		palina = Palina.objects.by_date().get(id_palina=id_palina, soppressa=False)
		if id_percorso != "":
			percorso = Percorso.objects.by_date().get(id_percorso=id_percorso)
		else:
			percorso = None
	except:
		return errors.XMLRPC['XRE_NO_ID_PALINA']
	if capolinea > 0:
		o = trovalinea_orari(request, None, id_percorso)
		ctx = {
			'orari_partenza': o['orari_partenza'],
			'capolinea': capolinea,
			'palina': palina,
		}
	else:		
		v1, v2, v3, carteggi_usati = dettaglio_palina(palina)
		
		veicoli = []
		veicoli_altrelinee = []
		coincidenze = []
		vall = v1 + v2
		if id_percorso != "":
			for v in vall:
				v = filtraNone(v)
				if v['id_percorso'] == str(id_percorso):
					veicoli.append(v)
			for v in v1:
				v = filtraNone(v)
				if v['id_percorso'] != str(id_percorso):
					veicoli_altrelinee.append(v)
		else:
			for v in v1:
				v = filtraNone(v)
				veicoli.append(v)
		
		# coincidenze
		# fs = []
		if id_percorso != "":
			fs = Fermata.objects.by_date().filter(palina=palina).exclude(percorso=percorso).distinct()
		else:
			fs = Fermata.objects.by_date().filter(palina=palina).distinct()
		for f in fs:
			if f.percorso.linea.id_linea not in coincidenze and not f.percorso.soppresso:
				coincidenze.append(f.percorso.linea.id_linea)
			
							
		ctx = {
			'capolinea': capolinea,
			'palina': palina,
			'palina_singola': False if percorso else True,
			'linea': percorso.linea.id_linea if percorso else "",
			'veicoli': veicoli,
			'veicoli_altrelinee': veicoli_altrelinee,
			'coincidenze': ', '.join(coincidenze),
		}
	return str(render_to_string('map-baloon.html', ctx))


def _orari(id_percorso, data=None, day_only=True):
	ctx = {}
	percorso = Percorso.objects.by_date().get(id_percorso=id_percorso)
	if data:
		try:
			if type(data) != date and type(data) != datetime:
				giorno = mysql2date(data)
			else:
				giorno = data
		except Exception:
			giorno = date.today()
	else:
		giorno = date.today()

	giorno = date2datetime(giorno)

	inizio_giorno = giorno
	fine_giorno = giorno + timedelta(days=1)
	ctx['giorno_partenza'] = date2mysql(giorno)
	giorno_prec = giorno - timedelta(hours=4)
	giorno_succ = giorno + timedelta(hours=30)
	giorni_sett = giorni_settimana()
	wd_ieri = giorni_sett[giorno_prec.weekday()]
	wd_domani = giorni_sett[giorno_succ.weekday()]
	pcs = PartenzeCapilinea.objects.filter(id_percorso=id_percorso, orario_partenza__gte=giorno_prec, orario_partenza__lte=giorno_succ).order_by('orario_partenza')
	ctx['nessuna_partenza'] = len(pcs) == 0
	ore_ieri = [{'ora': _("%(orario)2d di %(giorno)s") % {'orario': x, 'giorno': wd_ieri}, 'minuti': []} for x in range(24)]
	ore = [{'ora': "%2d" % x, 'minuti': []} for x in range(24)]
	ore_domani = [{'ora': _("%(orario)2d di %(giorno)s") % {'orario': x, 'giorno': wd_domani}, 'minuti': []} for x in range(7)]
	orario_old = None
	for pc in pcs:
		orario_new = pc.orario_partenza
		h = orario_new.hour
		if orario_new < inizio_giorno:
			ore_ieri[h]['minuti'].append("%02d" % orario_new.minute)
		elif orario_new >= fine_giorno:
			# Ci interessa solo il primo "blocco" di corse del giorno successivo
			if orario_old is not None and orario_new - orario_old > timedelta(minutes=90):
				break
			ore_domani[h]['minuti'].append("%02d" % orario_new.minute)
			orario_old = orario_new
		else:
			ore[h]['minuti'].append("%02d" % orario_new.minute)
			orario_old = orario_new
	if not day_only:
		ctx['orari_partenza'] = ore_ieri + ore + ore_domani
	else:
		ctx['orari_partenza'] = ore
	ctx['no_orari'] = percorso.no_orari
	ctx['note_no_orari'] = percorso.note_no_orari
	return ctx


def trovalinea_orari(request, token, id_percorso, data=None):
	return _orari(id_percorso, data, True)


TrovalineaOrariWS = paline7.metodo("Trovalinea.Orari")(trovalinea_orari)


def _percorso(request, id_percorso, ctx=None, id_veicolo=None, giorno_partenze=None, as_service=False, id_veicoli=None):
	if ctx is None:
		ctx = {}
	try:
		p = Percorso.objects.by_date().get(id_percorso=id_percorso)
		merc = get_web_cl_mercury()
		fermate = merc.sync_any('percorso_fermate_ap', {'id_percorso': id_percorso})['fermate']
		percorsi = list(Percorso.objects.by_date().select_related('linea').filter(linea=p.linea, soppresso=False))
		ctx['nascondi_percorsi'] = enhance_routes_with_stats(percorsi)
		percorsi.sort(key=_key_sort_percorsi_by_count)
		ctx['percorso'] = [perc for perc in percorsi if perc.id_percorso == id_percorso][0]
		ctx['percorsi'] = percorsi
		# Veicolo selezionato
		if id_veicolo is not None:
			ctx['id_veicolo'] = id_veicolo
			ctx['mostra_arrivi'] = True
			arrivi = merc.sync_any('arrivi_veicolo_ap', {'id_veicolo': id_veicolo})
			if arrivi is not None:
				for i, f in enumerate(fermate):
					if i == 0 and 'departure' in arrivi:
						f['orario_arrivo'] = datefilter(arrivi['departure'], _("H:i"))
					elif i > 0 and f['id_palina'] in arrivi:
						f['orario_arrivo'] = datefilter(arrivi[f['id_palina']], _("H:i"))
			ctx['id_veicoli'] = id_veicoli.split(',') if id_veicoli is not None else [id_veicolo]
		# Veicoli percorso
		veicoli = p.get_veicoli(False)
		decode_occupation_status = get_occupation_status_decoder()
		v2 = defaultdict(list)
		for v in veicoli:
			id_palina = v['id_prossima_palina']
			v2[id_palina].append(v)
		for i, f in enumerate(fermate):
			id_palina = f['id_palina']
			f['id_fermata'] = u"{}/{}".format(id_percorso, i)
			if id_palina in v2:
				veicoli_palina = v2[id_palina]
				if id_veicolo is not None and id_veicolo in veicoli_palina:
					f['veicolo'] = id_veicolo
					f['stato_occupazione'] = veicoli_palina[id_veicolo].get('stato_occupazione')
				else:
					f['veicolo'] = v2[id_palina][0]
					so = None
					for v in veicoli_palina:
						sov = v.get('stato_occupazione')
						if sov is not None and (so is None or so > sov):
							so = sov
					f['stato_occupazione'] = so
				f['id_veicoli'] = [v['id_veicolo'] for v in veicoli_palina]
				decode_occupation_status(f)
		ctx['fermate'] = fermate
		ctx['abilitato'] = p.abilitata_complessivo()
		oggi = datetime.now()
		if giorno_partenze is not None:
			ctx.update(_orari(id_percorso, giorno_partenze, as_service))
			gp = [oggi + timedelta(days=x) for x in range(-1, 6)]
			ctx['giorni_partenza'] = [{'mysql': date2mysql(x), 'format': datefilter(x, _("l j F")).capitalize()} for x in gp]
		else:
			ctx['orari_partenza_vicini'] = PartenzeCapilinea.objects.filter(id_percorso=id_percorso, orario_partenza__gte=oggi - timedelta(minutes=5), orario_partenza__lte=oggi + timedelta(minutes=60)).order_by('orario_partenza')[:5]
		if as_service:
			ctx['no_orari'] = p.no_orari
			ctx['note_no_orari'] = p.note_no_orari
			ctx['percorso'] = ctx['percorso'].getPercorso()
			ctx['percorsi'] = [p.getPercorso() for p in ctx['percorsi']]
			if 'orari_partenza_vicini' in ctx:
				ctx['orari_partenza_vicini'] = [o.orario_partenza for o in ctx['orari_partenza_vicini']]
			# workaround WA01 for webapp client bug begin
			if len(fermate) > 0:
				if fermate[0]['id_palina'] == fermate[-1]['id_palina']:
					fermate[0]['id_palina'] += "_departure"
			# workaround WA01 for webapp client bug end
			return ctx
		if not 'paline-mappa-statica' in request.session or request.session['paline-mappa-statica'][1] != id_percorso:
			request.session['paline-mappa-statica'] = (datetime.now(), id_percorso, None, None, None, None, None)
		return TemplateResponse(request, 'paline-fermate.html', ctx)
	except Percorso.DoesNotExist:
		return TemplateResponse(request, 'messaggio.html', {'msg': _("Il percorso %s non esiste") % id_percorso})


def percorso(request, id_percorso, ctx=None):
	if ctx is None:
		ctx = {}
	ctx['mappa_statica'] = not re.search("Android|iPhone", request.META['HTTP_USER_AGENT'])		
	try:
		id_veicolo = request.GET['id_veicolo']
	except Exception:
		id_veicolo = None
	id_veicoli = request.GET.get('id_veicoli', None)
	try:
		ctx['id_palina'] = request.GET['id_palina']
	except Exception:
		pass		
	if 'partenze' in request.GET:
		giorno = date.today()
		if 'data' in request.GET:
			try:
				giorno = mysql2date(request.GET['data'])
			except Exception:
				pass
	else:
		giorno = None
	return _percorso(request, id_percorso, ctx, id_veicolo, giorno, id_veicoli=id_veicoli)


def percorso_per_json(request, id_percorso, id_veicolo=None):
	giorni = []
	t = date.today()
	for i in range(7):
		giorni.append({
			'giorno': t.strftime('%Y-%m-%d'),
			'nome': datefilter(t, "l j F").capitalize(),
		})
		t += timedelta(days=1)

	percorso = _percorso(request, id_percorso, id_veicolo=id_veicolo, as_service=True)

	return {
		'fermate': percorso['fermate'],
		'giorni': giorni,
		'id_percorso': id_percorso,
		'percorso': percorso['percorso'],
		'percorsi':  percorso['percorsi'],
		'orari_partenza_vicini': percorso['orari_partenza_vicini'],
		'no_orari': percorso['no_orari'],
		'note_no_orari': percorso['note_no_orari'],
	}


def sospendi_fermata(request, id_percorso, progressiva):
	if not request.user.is_superuser:
		return messaggio(request, "Non autorizzato")
	id_fermata = u"{}|{}".format(id_percorso, progressiva)
	progressiva = int(progressiva)
	fs = FermataSospesa.objects.filter(id_fermata=id_fermata)
	if len(fs) == 0:
		percorso = Percorso.objects.by_date().get(id_percorso=id_percorso)
		fermata = Fermata.objects.get(percorso=percorso, progressiva=progressiva)
		palina = fermata.palina
		desc = u"Palina {}: {} linea {}".format(palina.id_palina, palina.nome, percorso.linea.id_linea)
		FermataSospesa(id_fermata=id_fermata, descrizione=desc).save()
		return messaggio(request, u'Fermata sospesa: {}'.format(desc))


def visualizza_mappa(request, id_percorso):
	ctx = {}
	try:
		p = Percorso.objects.by_date().get(id_percorso=id_percorso)
		ctx['percorso'] = p
		ctx['fermate'] = list(Fermata.objects.by_date().filter(percorso=p).order_by('progressiva'))[:-1]
		ctx['abilitato'] = p.abilitata_complessivo()
		try:
			id_palina = request.GET['id_palina']
			ctx['id_palina'] = request.GET['id_palina']
		except Exception:
			id_palina = None

		c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB_CL)
		
		m = gmaps.Map()
		c.root.percorso_su_mappa(id_percorso, m, '/paline/s/img/', con_stato=True)

		ctx['id_percorso'] = id_percorso
		ctx['mappa'] = mark_safe(m.render(url_tempi="http://%s/ws/xml/paline/7" % (request.META['HTTP_HOST'],), nome_metodo='paline.Trovalinea.Veicoli.Locale', id_palina=id_palina, id_percorso=id_percorso))
		return TemplateResponse(request, 'map-fullscreen.html', ctx)
	except Percorso.DoesNotExist:
		return TemplateResponse(request, 'messaggio.html', {'msg': _("Il percorso %s non esiste") % id_percorso})


def visualizza_mappa_statica(request, action=None):
	ctx = {}
	dt_orig, id_percorso, zoom, center_x, center_y, shift_h, shift_v = request.session['paline-mappa-statica']
	if datetime.now() - dt_orig < timedelta(seconds=3):
		return messaggio(request, _(u'Spiacenti, si è verificato un errore. Ti preghiamo di riprovare.'))
	try:
		p = Percorso.objects.by_date().get(id_percorso=id_percorso)
		ctx['percorso'] = p
		ctx['fermate'] = list(Fermata.objects.by_date().filter(percorso=p).order_by('progressiva'))[:-1]
		ctx['abilitato'] = p.abilitata_complessivo()
		try:
			id_palina = request.GET['id_palina']
			ctx['id_palina'] = id_palina
		except Exception:
			id_palina = None

		c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB_CL)
		
		m = gmaps.Map()
		c.root.percorso_su_mappa(id_percorso, m, '/paline/s/img/')
		if zoom is not None and action is not None:
			if action == 'i' and zoom < 19:
				zoom += 1
			if action == 'o' and zoom > 9:
				zoom -= 1
			if action == 'n':
				center_y += shift_v
			if action == 's':
				center_y -= shift_v
			if action == 'w':
				center_x -= shift_h
			if action == 'e':
				center_x += shift_h
		ret = m.render_static(zoom, center_y, center_x, id_palina=id_palina)
		ctx['mappa'] = ret['map']
		zoom = ret['zoom']
		request.session['paline-mappa-statica'] = (dt_orig, id_percorso, zoom, float(ret['center_x']), float(ret['center_y']), ret['shift_h'], ret['shift_v'])
		if zoom < 19:
			ctx['zoom_up'] = True
		if zoom > 9:
			ctx['zoom_down'] = True
		return percorso(request, id_percorso, ctx)
	except Percorso.DoesNotExist:
		return TemplateResponse(request, 'messaggio.html', {'msg': _("Il percorso %s non esiste") % id_percorso})				


def visualizza_mappa_statica_palina(request, id_palina, zoom=None, center_x=None, center_y=None):
	ctx = {}
	
	try:
		p = Palina.objects.by_date().get(id_palina=id_palina, soppressa=False)
		nome = "%s (%s)" % (p.nome_ricapitalizzato(), p.id_palina)
		
		c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB_CL)
				
		m = gmaps.Map()
		c.root.palina_su_mappa(id_palina, m, '/paline/s/img/')
		ret = m.render_static(zoom, center_y, center_x, id_palina=p.id_palina)
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
		ctx.update({'id_palina': id_palina, 'palina': p})
		return _dettaglio_paline(request, nome, [p], aggiungi=p.id_palina, ctx=ctx)
	except Percorso.DoesNotExist:
		return TemplateResponse(request, 'messaggio.html', {'msg': _("La fermata %s non esiste") % id_palina})	


def test_mappa(request):
	ctx = {}
	
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB_CL)
	
	m = gmaps.Map()
	percorsi = pickle.loads(c.root.percorsi_su_mappa_special(m, '/paline/s/img/'))
	ctx['percorsi'] = percorsi

	ctx['mappa'] = mark_safe(m.render(url_tempi="http://%s/ws/xml/paline/7" % (request.META['HTTP_HOST'],), nome_metodo='paline.Trovalinea.Veicoli.Locale', id_palina='', id_percorso=''))

	return TemplateResponse(request, 'map-test.html', ctx)

def img_linea(request, n):
	width = 20
	height = 20
	im = Image.new('RGBA', (width, height))  # create the image
	draw = ImageDraw.Draw(im)  # create a drawing object that is
					
	text = n
	# pointsize = 20
	# text_x = 90
	# textcolor = "black" # This only works with RGB images. 
	# font = ImageFont.truetype(our_font, pointsize)
	text_size = draw.textsize(text)  # the size of the text box!
	
	# figure out center x placement:
	x = (width - text_size[0]) / 2
	y = (height - text_size[1]) / 2
	
	color = (0, 0, 0)  # color of our text
	text_pos = (x, y)  # top-left position of our text
	# Now, we'll do the drawing: 
	draw.text(text_pos, text, fill=color)
	del draw  # I'm done drawing so I don't need this anymore
	response = HttpResponse(mimetype="image/png")
	im.save(response, 'PNG')
	return response

class LineeAssociateComparer(object):
	def __init__(self, max_linee_per_palina):
		object.__init__(self)
		self.trovate = set()
		self.max = max_linee_per_palina
		
	def comp(self, l1, l2):
		li1 = l1.linea.id_linea
		li2 = l2.linea.id_linea
		if li2[0] == 'N' and li1[0] != 'N':
			return -1
		if li1[0] == 'N' and li2[0] != 'N':
			return 1
		if li1 in self.trovate and li2 not in self.trovate:
			return -1
		if li2 in self.trovate and li1 not in self.trovate:
			return 1
		if len(li1) < len(li2):
			return -1
		if len(li2) < len(li1):
			return 1
		return 0
	
	def add_trovate(self, linee):
		for i in range(min(self.max, len(linee))):
			self.trovate.add(linee[i].linea.id_linea)
		

def _disambigua_to_struct(ctx):
	res = {}
	ps = []
	if 'paline_semplice' in ctx:
		for p in ctx['paline_semplice']:
			ps.append({
				'nome': p.nome_ricapitalizzato(),
				'id_palina': p.id_palina,
			})
	res['paline_semplice'] = ps
	pe = []
	if 'paline_extra' in ctx:
		for p in ctx['paline_extra']:
			try:
				d = p.distanza
			except Exception:
				d = -1
			li = []
			le = []
			direzioni = []
			for l in p.linee_extra:
				le.append(l.linea.id_linea)
			for l in p.linee_info:
				arrivo = l.arrivo.nome_ricapitalizzato()
				if not arrivo in direzioni:
					direzioni.append(arrivo)
				li.append({
					'id_linea': l.linea.id_linea,
					'direzione': arrivo,
				})
			if len(le) > 0:
				direzioni.append('...')
			palina = {
				'nome': p.nome_ricapitalizzato(),
				'id_palina': p.id_palina,
				'nascosta': p.nascosta,
				'distanza': d,
				'distanza_arrotondata': arrotonda_distanza(d) if d > 0 else '',
				'linee_extra': le,
				'linee_info': li,
				'primi_arrivi': p.primi_arrivi,
				'preferita': p.preferita,
				'direzioni': ", ".join(direzioni),
			}
			try:
				palina['lat'] = p.lat
				palina['lng'] = p.lng
			except Exception:
				pass
			pe.append(palina)
	res['paline_extra'] = pe
	pe = []
	if 'percorsi' in ctx:
		for p in ctx['percorsi']:
			pe.append({
				'id_percorso': p.id_percorso,
				'id_linea': p.linea.id_linea,
				'direzione': p.arrivo.nome_ricapitalizzato(),
				'monitorata': p.linea.monitorata,
				'abilitata': p.abilitata_complessivo(),
				'carteggio': p.carteggio,
				'carteggio_dec': p.decodeCarteggio(),
				'descrizione': p.descrizione,
			})
	res['percorsi'] = pe
	if 'percorso' in ctx:
		res['percorso'] = ctx['percorso']
	if 'lng' in ctx:
		res['lng'] = ctx['lng']
		res['lat'] = ctx['lat']
	return res

def _cmp_percorsi(p1, p2):
	if p1.linea.id_linea != p2.linea.id_linea:
		return cmp(p1.linea.id_linea, p2.linea.id_linea)
	c1 = p1.carteggio.replace('T', '')
	c2 = p2.carteggio.replace('T', '')
	if len(c1) < len(c2):
		return -1
	elif len(c1) > len(c2):
		return 1
	else:
		return cmp(c1, c2)


def _key_sort_percorsi_by_count(p):
	try:
		cnt = (p.departures_count + 2 * p.vehicles_count)
	except:
		cnt = 0
	return (p.linea.id_linea, -cnt, len(p.carteggio.replace('T', '')))


def _disambigua(request,
	paline_semplice=None,
	linee=None,
	paline_extra=None,
	nascondi_duplicati=False,
	ctx=None,
	as_service=False,
	per_palina=None,
	dett_paline=False,
):
	if ctx is None:
		ctx_orig = {}
	else:
		ctx_orig = ctx
	ctx = {}
	max_linee_per_palina = 2
	if paline_semplice is not None:
		ctx['paline_semplice'] = paline_semplice
	if linee is not None:
		if per_palina is None:
			percorsi = list(Percorso.objects.by_date().select_related('linea').filter(linea__in=linee, soppresso=False))
			ctx['nascondi_percorsi'] = enhance_routes_with_stats(percorsi)
			percorsi.sort(key=_key_sort_percorsi_by_count)
			ctx['percorsi'] = percorsi
		else:
			fermate = Fermata.objects.by_date().filter(palina__id_palina=per_palina)
			percorsi = Percorso.objects.by_date().select_related('linea').filter(linea__in=linee, fermata__in=fermate, soppresso=False)
			if len(percorsi) == 1 and not as_service:
				return _percorso(request, percorsi[0].id_percorso)
			elif len(percorsi) == 1:
				ctx['percorso'] = percorso_per_json(request, percorsi[0].id_percorso)
			percorsi = list(percorsi)
			ctx['percorsi'] = percorsi
			if len('percorsi') > 1:
				ctx['nascondi_percorsi'] = enhance_routes_with_stats(percorsi)
				percorsi.sort(key=_key_sort_percorsi_by_count)

	if paline_extra is not None:
		if request is not None and request.user.is_authenticated():
			preferite = set([p.id_palina for p in PalinaPreferita.objects.filter(gruppo__user=request.user)])
		else:
			preferite = set()
		lac = LineeAssociateComparer(max_linee_per_palina)
		percorsi_usati = set([])
		nascoste = False
		p1 = []
		p2 = []
		for palina in paline_extra:
			if palina.ha_linee_infotp():
				nuovi_percorsi = not nascondi_duplicati
				palina.preferita = palina.id_palina in preferite
				if palina.preferita:
					p1.append(palina)
				else:
					p2.append(palina)
				ps = [p for p in Percorso.objects.by_date().select_related('linea').filter(fermata__palina=palina, soppresso=False)]
				ps.sort(key=lambda p: (p.linea.id_linea, len(p.carteggio)))
				linee = []
				idold = None
				for p in ps:
					if idold != p.linea.id_linea:
						idold = p.linea.id_linea
						linee.append(p)
						if not p in percorsi_usati:
							percorsi_usati.add(p)
							nuovi_percorsi = True
				linee.sort(cmp=lac.comp)
				lac.add_trovate(linee)
				palina.linee_info = linee[:max_linee_per_palina]
				palina.linee_extra = linee[max_linee_per_palina:]
				palina.nascosta = not (nuovi_percorsi or palina.preferita)
				palina.primi_arrivi = []
				if palina.nascosta:
					nascoste = True
		paline_extra = p1 + p2
		if dett_paline:
			paline_visibili = [p for p in paline_extra if not p.nascosta]
			primi = get_primi_arrivi(paline_visibili)
			for p in paline_visibili:
				p.primi_arrivi = primi[p.id_palina]['veicoli']

		ctx['paline_extra'] = paline_extra
		ctx['paline_nascoste'] = nascoste
	if as_service:
		ctx_orig.update(_disambigua_to_struct(ctx))
		ctx_orig['tipo'] = 'Ambiguo'
		return ctx_orig
	else:
		ctx_orig.update(ctx)
		return TemplateResponse(request, 'paline-disambigua.html', ctx_orig)


def _place_choice(indirizzo, elem):
	loc, place = elem
	return ("%s, %s" % (indirizzo, place), "%s, %s" % (indirizzo, loc))


def _address_choice(indirizzo, luogo):
	x = "%s, %s" % (indirizzo, luogo)
	return (x, x)


def linea(request, id_linea):
	ctx = {}
	ctx['form'] = populate_form(request, MultiForm, cerca=id_linea)
	linee = list(Linea.objects.by_date().filter(id_linea__iexact=id_linea))
	if 'id_palina' in request.GET:
		per_palina = request.GET['id_palina']
	else:
		per_palina = None
		linee.extend(Linea.objects.by_date().filter(id_linea__iexact=id_linea + "F"))
	if len(linee) > 0:
		return _disambigua(request, linee=linee, ctx=ctx, per_palina=per_palina)


def _default(request, cerca, ctx, as_service, dett_paline=False):
	cerca = sostituisci_preferiti(request, cerca)
	cerca = cerca.strip()
	if cerca == '':
		ctx['errore'] = True
		if as_service:
			return ctx
		else:
			return TemplateResponse(request, 'paline.html', ctx)

	if cerca.startswith('fermata:'):
		cerca = cerca[8:]

	ctx['ricerca'] = cerca

	res = cerca_ricerca_errata(cerca)
	if res is not None and res[0] is not None:
		cerca = res[0]

	per_palina = None

	if cerca.startswith('percorsi:'):
		paline = Palina.objects.none()
		try:
			dummy, id_linea, per_palina = cerca.split(':')
			linea = Linea.objects.by_date().get(id_linea=id_linea)
		except:
			ctx['errore'] = True
			return ctx
		linee = [linea]

	else:
		paline = Palina.objects.by_date().filter(id_palina=cerca, soppressa=False)
		linee_raw = Linea.objects.by_date().filter(id_linea__istartswith=cerca)
		linee = []
		for l in linee_raw:
			id_linea = l.id_linea
			# uc = id_linea[-1].upper()
			if len(id_linea) == len(cerca):
				linee.append(l)
			else:
				lun = len(cerca)
				if len(id_linea) > lun and 'A' <= id_linea[lun] <= 'Z':
					linee.append(l)

	if len(paline) == 1 and len(linee) == 0:
		p = paline[0]
		nome = "%s (%s)" % (p.nome_ricapitalizzato(), p.id_palina)
		if not as_service:
			ctx['mappa_statica'] = not re.search("Android|iPhone", request.META['HTTP_USER_AGENT'])
			ctx.update({'id_palina': p.id_palina, 'palina': p})
			RicercaRecente.update(request, "fermata:%s" % p.id_palina, nome)
			ctx['ad_geom'] = p.geom
			return _dettaglio_paline(request, nome, [p], aggiungi=p.id_palina, ctx=ctx)
		else:
			ctx['tipo'] = 'Palina'
			ctx['id_palina'] = p.id_palina
			if dett_paline:
				ctx['dettaglio'] = _dettaglio_paline_app(request, p)
			return ctx

	if len(linee) > 0:
		RicercaRecente.update(request, cerca, cerca)
		return _disambigua(request, paline, linee, ctx=ctx, as_service=as_service, per_palina=per_palina)

	# Nessuna linea o palina con l'id cercato
	# Provo a cercare la palina in base al nome
	parti = multisplit(cerca, [' ', '/'])
	res = None
	for parte in parti:
		if len(parte) > 2:
			ps = NomePalina.objects.by_date().filter(parte__istartswith=parte)
			pks = set([p.palina.pk for p in ps])
			if res is None:
				res = pks
			else:
				res = res.intersection(pks)
			if len(res) == 0:
				break

	if res is not None and len(res) > 0:
		paline = Palina.objects.by_date().filter(pk__in=res, soppressa=False)
		return _disambigua(request, paline_extra=paline, ctx=ctx, as_service=as_service)

	# Infine, provo a considerare il testo immesso come indirizzo e cercare linee e paline vicine
	if not is_int(cerca):
		try:
			res = infopoint.geocode_place(request, cerca)
			if res['stato'] == 'Ambiguous':
				if as_service:
					ctx['tipo'] = 'Indirizzo ambiguo'
					ctx['indirizzi'] = res['indirizzi']
					return ctx
				else:
					class CorreggiMultiForm(MultiForm):
						cerca = forms.TypedChoiceField(choices=[(x, x) for x in res['indirizzi']])
					ctx['form'] = populate_form(request, CorreggiMultiForm, cerca='')	
			elif res['stato'] == 'OK':
				RicercaRecente.update(request, res['ricerca'], res['indirizzo'])
				id_richiesta = hashlib.md5(pickle.dumps(('oggetti_vicini', res))).hexdigest()
				trs = cache.get(id_richiesta)
				if trs is None:
					merc = get_web_cpd_mercury()
					trs = merc.sync_any('oggetti_vicini_ap', {'start': res})
					cache.set(id_richiesta, trs)
				ps, ls = trs
				paline = []
				for p in ps:
					palina = Palina.objects.by_date().select_related().get(id_palina=p[0])
					palina.distanza = p[1]
					palina.lng, palina.lat = gbfe_to_wgs84(p[2], p[3])
					paline.append(palina)
				for l in ls:
					linea = Linea.objects.by_date().select_related().get(id_linea=l[0])
					linea.palina = Palina.objects.by_date().select_related().get(id_palina=l[1])
					linea.distanza = l[2]
				ctx['lng'], ctx['lat'] = gbfe_to_wgs84(res['x'], res['y'])
				
				return _disambigua(request, paline_extra=paline, nascondi_duplicati=True, ctx=ctx, as_service=as_service, dett_paline=dett_paline)
			else:
				ctx['errore'] = True
		except Exception, e:
			traceback.print_exc()
			# Se uno dei servizi sta giù (Infopoint, paline vicine) omettiamo la ricerca per indirizzo
			ctx['errore'] = True
	else:
		ctx['errore'] = True
	if as_service:
		return ctx
	else:
		return TemplateResponse(request, 'paline.html', ctx)
	
	
@paline7.metodo("SmartSearch")
def smart_search(request, token, qs):
	ctx = {
		'errore': False,
		'tipo': '',
		'id_palina': '',
		'indirizzi': [],
		'paline_semplice': [],
		'paline_extra': [],
		'percorsi': [], 	
	}
	return _default(None, qs, ctx, True)

def default(request):
	f = populate_form(request, MultiForm, cerca='')
	ctx = {}
	ctx['form'] = f
	if request.user.is_authenticated():
		ctx['gruppi_preferiti'] = GruppoPalinePreferite.objects.filter(user=request.user, singleton=False)
		ctx['paline_preferite'] = PalinaPreferita.objects.filter(gruppo__user=request.user, gruppo__singleton=True)
		ctx['nessun_preferito'] = len(ctx['gruppi_preferiti']) + len(ctx['paline_preferite']) == 0	
	if f.is_bound:
		cd = f.data
		cerca = cd['cerca'].strip()
		ctx['cerca'] = cerca
		return _default(request, cerca, ctx, False)
	return TemplateResponse(request, 'paline.html', ctx)

# Caricamento rete
class CaricaReteForm(forms.Form):
	rete = forms.FileField()
	shape = forms.FileField()

@group_required('carica_rete')
def carica_rete(request):
	ctx = {}
	if request.method == 'POST':
		form = CaricaReteForm(request.POST, request.FILES)
		if form.is_valid():
			rete = request.FILES['rete']
			f = open(os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/rete.zip'), 'wb')
			f.write(rete.read())
			f.close()
			shape = request.FILES['shape']
			f = open(os.path.join(settings.TROVALINEA_PATH_RETE, 'temp/shp.zip'), 'wb')
			f.write(shape.read())
			f.close()
			Job.objects.filter(function='paline.carica_rete').update(action='O')
			# c = Mercury.rpyc_connect_any_static(settings.MERCURY_CARICA_RETE)
			# caricatore = rpyc.async(c.root.carica_rete)
			# caricatore()
	else:
		ctx['form'] = CaricaReteForm()
	return TemplateResponse(request, 'paline-carica-rete.html', ctx)

# Segnalazione disservizi
def _disservizio(request, paline, redirect_to, ctx=None):
	if ctx is None:
		ctx = {}
	
	linee = Linea.objects.by_date().filter(percorso__fermata__palina__in=paline).distinct()
	linea_choices = [(l.id_linea, l.id_linea) for l in linee]
	linea_segnalata_choices = [('', _('Autobus non segnalato'))] + linea_choices
	linea_passata_choices = [('', _(u'L\'autobus segnalato non è passato')), ('DEP', _('Autobus diretto al deposito'))] + linea_choices
	palina_choices = [(p.id_palina, '%s (%s)' % (p.nome_ricapitalizzato(), p.id_palina)) for p in paline]
	
	class DisservizioForm(AtacMobileForm):
		id_palina = forms.ChoiceField(choices=palina_choices)
		id_linea_segnalata = forms.ChoiceField(choices=linea_segnalata_choices, required=False)
		id_linea_passata = forms.ChoiceField(choices=linea_passata_choices, required=False)		
		id_veicolo = forms.CharField(required=False)
		note = forms.CharField(widget=forms.Textarea, required=False)
		
	class DisservizioPalinaElettronicaForm(AtacMobileForm):
		id_palina = forms.ChoiceField(choices=palina_choices)
	
	form = populate_form(request, DisservizioForm, note='')
	pe_form = populate_form(request, DisservizioPalinaElettronicaForm, id_palina=palina_choices[0][0])	
	error = None
	if 'submit' in request.GET:
		if form.is_valid():
			cd = form.cleaned_data
			id_palina = cd['id_palina']
			id_linea_passata = cd['id_linea_passata']
			id_linea_segnalata = cd['id_linea_segnalata']
			id_veicolo = cd['id_veicolo']
			note = cd['note']
			if id_linea_passata == id_linea_segnalata:
				error = 'uguali'
			elif id_linea_segnalata == '' and id_linea_passata == 'DEP':
				error = 'non-errore'
			if error is not None:
				form.set_error('id_linea_segnalata')
				form.set_error('id_linea_passata')
			else:
				Disservizio(
					user=request.user,
					orario=datetime.now(),
					id_palina=id_palina,
					id_linea_passata=id_linea_passata,
					id_linea_segnalata=id_linea_segnalata,
					id_veicolo=id_veicolo,
					note=note,
				).save()
				return hist_redirect(request, redirect_to, msg=_(u"Grazie per la segnalazione del disservizio."))
	if 'pe_submit' in request.GET:
		if pe_form.is_valid():
			cd = pe_form.cleaned_data
			DisservizioPalinaElettronica(
				user=request.user,
				orario=datetime.now(),
				id_palina=cd['id_palina'],
			).save()
			return hist_redirect(request, redirect_to, msg=_(u"Grazie per la segnalazione del disservizio."))
	ctx['error'] = error
	ctx['form'] = form
	ctx['pe_form'] = form
	return TemplateResponse(request, 'paline-disservizio.html', ctx)

def elenco_linee(request):
	ctx = {}
	ps = Percorso.objects.by_date().select_related('linea', 'arrivo').filter(soppresso=False)
	if 'scolastico' in request.REQUEST:
		ps = ps.filter(carteggio__contains='S')
	if 'gestore' in request.REQUEST:
		ps = ps.filter(linea__gestore__nome=request.REQUEST['gestore'])
	ps = ps.order_by('linea__id_linea')
	ls = defaultdict(list)
	for p in ps:
		ls[p.linea.id_linea].append(p)
	linee = [{'id': l, 'linea': ls[l][0].linea, 'percorsi': ls[l]} for l in ls]
	linee.sort(key=lambda x: x['id'])
	ctx['linee'] = linee
	return TemplateResponse(request, 'paline-elenco-linee.html', ctx)

@group_excluded('readonly')
def disservizio(request, id_palina):
	ps = Palina.objects.by_date().filter(id_palina=id_palina)
	if len(ps) == 1:
		return _disservizio(request, ps, '/paline/palina/%s' % id_palina)
	else:
		return messaggio(request, _("La fermata non esiste"))



@group_excluded('readonly')
def disservizio_gruppo(request, id_gruppo):
	try:
		gp = GruppoPalinePreferite.objects.get(user=request.user, pk=id_gruppo)
		return _disservizio(request, gp.get_paline(), '/paline/gruppo/%s' % id_gruppo)
	except GruppoPalinePreferite.DoesNotExist:
		return messaggio(request, _("Il gruppo non esiste"))


# Gestione paline preferite
@group_excluded('readonly')
def preferiti_aggiungi(request, id_palina):
	ctx = {}
	class PalinePreferiteForm(AtacMobileForm):
		nome_palina = forms.CharField(max_length=63)
		nome_gruppo = forms.CharField(max_length=63, required=False)
		gruppo = forms.ModelChoiceField(queryset=GruppoPalinePreferite.objects.filter(user=request.user, singleton=False), required=False)
	try:
		palina = Palina.objects.by_date().get(id_palina=id_palina)
	except Palina.DoesNotExist:
		return messaggio(request, _("La fermata non esiste"))
	f = populate_form(
		request,
		PalinePreferiteForm,
		nome_palina="%s (%s)" % (palina.nome_ricapitalizzato(), palina.id_palina),
		nome_gruppo='',
	)
	if f.is_valid():
		singleton = 'Singola' in request.GET
		cd = f.cleaned_data
		if not singleton and cd['gruppo'] is not None:
			gp = cd['gruppo']
		else:
			gp = GruppoPalinePreferite(
				user=request.user,
				nome=cd['nome_gruppo'],
				singleton=singleton
			)
			gp.save()
		pp = PalinaPreferita(
			gruppo=gp,
			nome=cd['nome_palina'], 			
			id_palina=id_palina
		)
		pp.save()
		return hist_redirect(request, "/paline/preferiti/escludi_linee/%d" % gp.pk, msg=_(u"Fermata preferita impostata"))
	
	ctx['form'] = f 
	return TemplateResponse(request, 'paline-preferiti-aggiungi.html', ctx)


class GruppoForm(AtacMobileForm):
	nome_gruppo = forms.CharField(max_length=63)
	
class NotificheForm(AtacMobileForm):
	notifiche = forms.BooleanField(required=False)
	min_attesa = forms.IntegerField(widget=forms.TextInput(attrs={'size': '2'}))
	max_attesa = forms.IntegerField(widget=forms.TextInput(attrs={'size': '2'}))
	

@group_excluded('readonly')
def preferiti_escludi_linee(request, id_gruppo):
	ctx = {}
	try:
		gp = GruppoPalinePreferite.objects.get(user=request.user, pk=id_gruppo)
		ctx['gruppo'] = gp	
		
		# Nome gruppo
		fg = populate_form(
			request,
			GruppoForm,
			nome_gruppo=gp.nome
		)
		if fg.is_valid():
			ng = fg.cleaned_data['nome_gruppo']
			gp.nome = ng
			gp.save()
			return hist_redirect(request, '/paline/preferiti/escludi_linee/%s' % (id_gruppo), msg=_(u"Nome del gruppo modificato"))
		ctx['form_gruppo'] = fg
		
		# Linee escluse
		pps = PalinaPreferita.objects.filter(gruppo=gp)
		id_paline = [pp.id_palina for pp in pps]
		linee_gruppo = Linea.objects.by_date().filter(percorso__fermata__palina__id_palina__in=id_paline).distinct().order_by('id_linea')
		choices = [(l.id_linea, l.id_linea) for l in linee_gruppo]
		linee_escluse = LineaPreferitaEsclusa.objects.filter(gruppo=gp)
		linee_escluse = set([l.id_linea for l in linee_escluse])
		initial = [l.id_linea for l in linee_gruppo if not l.id_linea in linee_escluse]
		class LineeEscluseForm(AtacMobileForm):
			linee = forms.MultipleChoiceField(choices=choices, widget=BrCheckboxSelectMultiple())
		f = populate_form(request, LineeEscluseForm, linee=initial)	
		if f.is_valid():
			ls = f.cleaned_data['linee']
			LineaPreferitaEsclusa.objects.filter(gruppo=gp).delete()
			linee_escluse = [l.id_linea for l in linee_gruppo if not l.id_linea in ls]
			for l in linee_escluse:
				LineaPreferitaEsclusa(id_linea=l, gruppo=gp).save()
			return hist_redirect(request, '/paline/preferiti/escludi_linee/%s' % id_gruppo, msg=_(u"Esclusioni impostate"))
		ctx['form'] = f
	
		# Notifiche
		rns = gp.richiestanotificapalina_set.all()
		rn = None
		if len(rns) > 0:
			rn = rns[0]
			f = populate_form(
				request,
				NotificheForm,
				notifiche=True,
				min_attesa=rn.min_attesa,
				max_attesa=rn.max_attesa,
			)
			ctx['notifiche_avanzate'] = rn.pk
		else:
			f = populate_form(
				request,
				NotificheForm,
				notifiche=False,
				min_attesa=2,
				max_attesa=7,
			)
		if f.is_valid():
			cd = f.cleaned_data
			if cd['notifiche']:
				if rn is None:
					rn = RichiestaNotificaPalina(
						gruppo=gp,
						user=request.user,
						min_attesa=cd['min_attesa'],
						max_attesa=cd['max_attesa'],
					)
					rn.save()
				else:
					rn.min_attesa = cd['min_attesa']
					rn.max_attesa = cd['max_attesa']
					rn.save()
			else:
				gp.richiestanotificapalina_set.all().delete()
				rn = None
			return hist_redirect(request, '/paline/preferiti/escludi_linee/%s' % id_gruppo, msg=_(u"Notifiche impostate"))
		ctx['form_notifiche'] = f

		return TemplateResponse(request, 'paline-preferiti-escludi-linee.html', ctx)
	
	except GruppoPalinePreferite.DoesNotExist:
		return messaggio(request, _("Il gruppo non esiste"))

@group_excluded('readonly')
@richiedi_conferma(_('Confermi di voler eliminare la fermata preferita?'))
def preferiti_elimina(request, id_gruppo):
	GruppoPalinePreferite.objects.filter(user=request.user, pk=id_gruppo).delete()
	return hist_redirect(request, '/paline', msg=_(u"Fermata preferita eliminata"))

@group_excluded('readonly')
@richiedi_conferma(_('Confermi di voler eliminare la fermata dal gruppo?'))
def preferiti_elimina_palina(request, id_gruppo, id_pp):
	try:
		p = PalinaPreferita.objects.get(gruppo__user=request.user, pk=id_pp)
		g = p.gruppo
		if g.palinapreferita_set.count() == 1:
			g.delete()
			return hist_redirect(request, '/paline', msg=_(u"Gruppo di fermate eliminato"))
		else:
			p.delete()
			return hist_redirect(request, '/paline/preferiti/escludi_linee/%s' % id_gruppo, msg=_(u"Fermata preferita eliminata"))
	except PalinaPreferita.DoesNotExist:
		return messaggio(request, _("La fermata non esiste"))
	

@paline7.metodo("GetRete")
def get_rete(request, token):
	"""
	Restituisce l'ultima versione caricata della rete (struttura e shapefile)
	"""
	print "Carico file rete"
	inizio_validita = datetime2compact(VersionePaline.attuale().inizio_validita)
	path_rete = os.path.join(settings.TROVALINEA_PATH_RETE, inizio_validita)
	f = open(os.path.join(path_rete, 'rete.zip'), 'rb')
	rete = f.read()
	f.close()
	f = open(os.path.join(path_rete, 'shp.zip'), 'rb')
	shp = f.read()
	f.close()
	
	print "Restituisco rete"
	return {
		'rete': xmlrpclib.Binary(rete),
		'shp': xmlrpclib.Binary(shp),
	}
	
@paline7.metodo("GetPartenzeCapilinea")
def get_partenze_capilinea(request, token, giorno):
	"""
	Restituisce le partenze dal capolinea di tutti i percorsi in un dato giorno
	"""
	giorno = datetime.strptime(giorno, "%Y-%m-%d")
	giorno_succ = giorno + timedelta(days=1)
	ps = PartenzeCapilinea.objects.using('default').filter(orario_partenza__gte=giorno, orario_partenza__lt=giorno_succ)
	out = []
	for p in ps:
		out.append({
			'id_percorso': p.id_percorso,
			'orario_partenza': p.orario_partenza,
		})
	
	return out


@paline7.metodo("GetVeicoliPercorso")
def get_veicoli_percorso(request, token, id_percorso):
	"""
	Restituisce i veicoli di un percorso
	
	Per l'università di Tor Vergata
	"""
	return get_web_cl_mercury().sync_any('veicoli_tutti_percorsi_ap', {'get_arrivi': False, 'get_distanza': True})


@paline7.metodo("GetVeicoliTuttiPercorsi")
def get_veicoli_tutti_percorsi(request, token):
	"""
	Restituisce i veicoli di tutti i percorsi
	"""
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
	r, g = c.root.get_rete_e_grafo()
	vs = pickle.loads(c.root.veicoli_tutti_percorsi(False, True))
	
	return vs


@paline7.metodo("GetVeicoliPercorsoConPrevisioni")
def get_veicoli_percorso_con_previsioni(request, token, id_percorso):
	"""
	Restituisce i veicoli di un percorso

	Per l'università di Tor Vergata
	"""
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
	vs = pickle.loads(c.root.veicoliarshali_percorsi(True, True))

	return vs


@paline7.metodo("GetVeicoliTuttiPercorsiConPrevisioni")
def get_veicoli_tutti_percorsi_con_previsioni(request, token):
	"""
	Restituisce i veicoli di tutti i percorsi

	Per l'università di Tor Vergata
	"""
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
	r, g = c.root.get_rete_e_grafo()
	vs = pickle.loads(c.root.veicoli_tutti_percorsi(True, True))

	return {
		'ultimo_aggiornamento': unmarshal_datetime(r.ultimo_aggiornamento),
		'percorsi': vs,
	}


@paline7.metodo("GetOrarioUltimoAggiornamentoArrivi")
def get_orario_ultimo_aggiornamento_arrivi(request, token):
	"""_
	Restituisce i veicoli di tutti i percorsi
	"""
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
	r, g = c.root.get_rete_e_grafo()
		
	return {
		'ultimo_aggiornamento': unmarshal_datetime(r.ultimo_aggiornamento),
	}


@paline7.metodo("GetStatoRete")
def get_stato_rete(request, token):
	"""
	Restituisce lo stato della rete serializzato e pickled
	"""
	c = Mercury.rpyc_connect_any_static(settings.MERCURY_WEB)
	r, g = c.root.get_rete_e_grafo()
	
	return {
		'ultimo_aggiornamento': unmarshal_datetime(r.ultimo_aggiornamento),
		'stato_rete': xmlrpclib.Binary(c.root.serializza_dinamico()),
	}


@paline7.metodo("GetStatPassaggi")
def get_stat_passaggi(request, token):
	"""
	Restituisce le statistiche sui passaggi dei percorsi
	"""
	periodi_aggregazione = StatPeriodoAggregazione.objects.all()
	tempi_attesa_percorsi = StatTempoAttesaPercorso.objects.all() 
	
	return {
		'periodi_aggregazione': xmlrpclib.Binary(serializers.serialize("json", periodi_aggregazione)),
		'tempi_attesa_percorsi': xmlrpclib.Binary(serializers.serialize("json", tempi_attesa_percorsi)),
	}

	
@paline7.metodo("gtfs2mtram")
def gtfs2mtram(request, token):
	ps = Percorso.objects.by_date().all()
	out = []
	for p in ps:
		linea_carteggio = "%s%s" % (p.linea.id_linea, p.carteggio_quoz)
		direzione = 0
		if p.verso == 'R':
			direzione = 1
		out.append({
			'route_id': linea_carteggio,
			'direction': direzione,
			'mtram': p.id_percorso})

	return out
