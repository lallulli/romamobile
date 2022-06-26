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

from django.db import models, connections
from django.contrib.gis.db import models as gismodels
from django.contrib.gis.geos import Point, GEOSGeometry
import urllib2
import re
import time
from xml.dom import minidom
import errors
import settings
from servizi.utils import oggetto_con_min, oggetto_con_max, aggiungi_banda, giorni_settimana
from servizi.utils import ricapitalizza, FunctionInThread, PickledObjectField, transaction
from datetime import datetime, timedelta
from servizi.models import VersioneManager, VersionatoManager, VersioneVersioning, Versionato, RichiestaNotifica
from servizi.models import UtenteGenerico, Luogo, Festivita
from news.models import News
from django.db.models import Q
from django.contrib.auth.models import User
from django.template.response import TemplateResponse
from django.template.defaultfilters import time as timefilter
from django.utils.translation import ugettext as _
from django.core.cache import cache
import rpyc
import cPickle as pickle
import random
from time import sleep 
import csv
import traceback
import base64
from paline.geomath import gbfe_to_wgs84
from mercury.models import Mercury
from gis.models import Polilinea
from pprint import pprint
import zlib

INTERVALLO_IN_ARRIVO = 90 # secondi

TIPI_LINEA_INFOTP = ['BU', 'TR']
TIPI_LINEA_FERRO = ['ME', 'FR', 'FC']
GESTORI_INFOTP = ['ATAC']


web_mercury = [None, None]


def get_web_cl_mercury():
	if web_mercury[0] is None:
		web_mercury[0] = Mercury(settings.MERCURY_WEB_CL, persistent_connection=True)
	return web_mercury[0]


def get_web_cpd_mercury():
	if web_mercury[1] is None:
		web_mercury[1] = Mercury(settings.MERCURY_WEB, persistent_connection=True)
	return web_mercury[1]


# istanziazione versioning paline
class VersionePaline(VersioneVersioning):
	pass


class VersionatoPaline(Versionato):
	objects = VersionatoManager(VersionePaline)
	versione = VersionePaline

	class Meta:
		abstract = True


# paline
class DisabilitazioneManager(models.Manager):
	def attive(self, orario=None):
		if orario is None:
			orario = datetime.now()
		return self.get_query_set().filter(Q(orario_fine__gte=orario) | Q(orario_fine__isnull=True), orario_inizio__lte=orario)


class Disabilitazione(models.Model):
	orario_inizio = models.DateTimeField(db_index=True)
	orario_fine = models.DateTimeField(null=True, db_index=True)
	news = models.ForeignKey(News, null=True, default=None)
	
	objects = DisabilitazioneManager()
	
	class Meta:
		abstract = True


class Disabilitabile(models.Model):
	chiave_disabilitazione = ''
	disabilitazione = Disabilitazione
		
	def get_chiave_filter_dict(self):
		if isinstance(self.chiave_disabilitazione, str) or isinstance(self.chiave_disabilitazione, unicode):
			return {self.chiave_disabilitazione: getattr(self, self.chiave_disabilitazione)}
		else:
			return dict([(k[0], k[1](self)) for k in self.chiave_disabilitazione])
	
	class Meta:
		abstract = True

	def abilita(self):
		ds = self.disabilitazione.objects.attive().filter(**self.get_chiave_filter_dict())
		n = datetime.now()
		for d in ds:
			d.orario_fine = n
			d.save()
	
	def disabilita(self, orario_fine=None, orario_inizio=None):
		if self.disabilitazione.objects.attive().filter(**self.get_chiave_filter_dict()).count() == 0:
			if orario_inizio is None:
				orario_inizio = datetime.now()
			self.disabilitazione(orario_inizio=orario_inizio, orario_fine=orario_fine, **self.get_chiave_filter_dict()).save()
	
	def abilitata(self, orario=None):
		return self.disabilitazione.objects.attive(orario).filter(**self.get_chiave_filter_dict()).count() == 0
	
	def news_disabilitazione(self, orario=None):
		ds = self.disabilitazione.objects.attive(orario).filter(**self.get_chiave_filter_dict())
		if len(ds) == 1:
			return ds[0].news
		return None
	
	def id_news_disabilitazione(self, orario=None):
		news = self.news_disabilitazione(orario)
		if news is None:
			return -1
		return news.id_news
	
	def abilitata_complessivo(self, orario=None):
		def aci():
			if not self.abilitata(orario):
				return False
			for d in self.dipendenze_abilitazione:
				if not getattr(self, d).abilitata_complessivo(orario):
					return False
			return True
	
		if orario is None:
			ac = cache.get('disabilitazione-abilitata-complessivo-%s-%d' % (self.disabilitazione.__name__, self.pk))
			if ac is not None:
				return ac
		ac = aci()
		if orario is None:
			cache.set('disabilitazione-abilitata-complessivo-%s-%d' % (self.disabilitazione.__name__, self.pk), ac, 60)
		return ac
	
	def news_disabilitazione_complessivo(self, orario=None):
		def ndc():
			n = self.news_disabilitazione(orario)
			if n is not None:
				return n
			for d in self.dipendenze_abilitazione:
				n = getattr(self, d).news_disabilitazione_complessivo(orario)
				if n is not None:
					return n
			return None
		if orario is None:
			ac = cache.get('disabilitazione-news-disabilitazione-complessivo-%s-%d' % (self.disabilitazione.__name__, self.pk))
			if ac is not None:
				return ac
		ac = ndc()
		if orario is None:
			cache.set('disabilitazione-news-disabilitazione-complessivo-%s-%d' % (self.disabilitazione.__name__, self.pk), ac, 60)
		return ac
	
	def id_news_disabilitazione_complessivo(self, orario=None):
		news = self.news_disabilitazione_complessivo(orario)
		if news is None:
			return -1
		return news.id_news
	
	dipendenze_abilitazione = []
		
		
class Carteggio(VersionatoPaline):
	codice = models.CharField(max_length=3, db_index=True)
	descrizione = models.CharField(max_length=60)


class DisabilitazioneFermata(Disabilitazione):
	id_percorso = models.CharField(max_length=30, db_index=True)
	id_palina = models.CharField(db_index=True, max_length=20) 


class Fermata(VersionatoPaline, Disabilitabile):
	percorso = models.ForeignKey('Percorso', db_index=True)
	palina = models.ForeignKey('Palina', db_index=True)
	progressiva = models.IntegerField()
	abilitato = models.BooleanField(default=True)
	
	def get_id_palina(self):
		return self.palina.id_palina
	
	def get_id_percorso(self):
		return self.percorso.id_percorso

	chiave_disabilitazione = [('id_palina', get_id_palina), ('id_percorso', get_id_percorso)]
	disabilitazione = DisabilitazioneFermata
	dipendenze_abilitazione = ['palina', 'percorso']


class DisabilitazioneGestore(Disabilitazione):
	nome = models.CharField(max_length=30, db_index=True)


class Gestore(VersionatoPaline, Disabilitabile):
	nome = models.CharField(max_length=30, db_index=True)
	descrizione = models.CharField(max_length=120)
	
	def __unicode__(self):
		return u"Gestore " + self.descrizione	
	
	chiave_disabilitazione = 'nome'
	disabilitazione = DisabilitazioneGestore
	

class DisabilitazioneLinea(Disabilitazione):
	id_linea = models.CharField(max_length=30, db_index=True)


TIPO_LINEA_CHOICES = (
	(u"BU", u"Autobus"),
	(u"TR", u"Tram"),
	(u"ME", u"Metropolitana"),
	(u"FR", u"Ferrovia Regionale"),
	(u"FC", u"Ferrovia Concessa"),
)


TIPO_LINEA_CHOICES_DICT = dict(TIPO_LINEA_CHOICES)


def componi_annuncio(el, short=False):
	if int(el['a_capolinea']) and el['prossima_partenza'] == '':
		if short:
			return _("Capol.")
		else:
			return _("Capolinea")
	if int(el['in_arrivo']):
		return _("In Arrivo")
	tempo = int(el['tempo_attesa'])
	fermate = int(el['distanza_fermate'])
	if tempo == -1:
		tempo_s = ''
	else:
		tempo_s = "(%d')" % int(round(tempo / 60.0))
	if fermate == 1:
		if short:
			out = _("1 Ferm. %(tempo)s") % {'tempo': tempo_s}
		else:
			out = _("1 Ferm. %(tempo)s") % {'tempo': tempo_s}
	elif short:
		out = _("%(fermate)d Ferm. %(tempo)s") % {'fermate': fermate, 'tempo': tempo_s}
	else:
		out = _("%(fermate)d Ferm. %(tempo)s") % {'fermate': fermate, 'tempo': tempo_s}
	if el['a_capolinea']:
		if short:
			out = _("Capol. %(tempo)s (p.%(orario)s)") % {'tempo': tempo_s, 'orario': el['prossima_partenza'].strftime("%H:%M")}
		else:
			out += _(" (parte alle %(orario)s)") % {'orario': el['prossima_partenza'].strftime("%H:%M")}
	return out


class Linea(VersionatoPaline, Disabilitabile):
	id_linea = models.CharField(max_length=30, db_index=True)
	monitorata = models.IntegerField()
	gestore = models.ForeignKey('Gestore', db_index=True)
	tipo = models.CharField(max_length=2, choices=TIPO_LINEA_CHOICES, default="BU", db_index=True)

	chiave_disabilitazione = 'id_linea'
	disabilitazione = DisabilitazioneLinea
	dipendenze_abilitazione = ['gestore']
	
	def __unicode__(self):
		return u"Linea " + self.id_linea
	
	def getPercorsi(self):
		
		ret = {}
		ret['monitorata'] = self.monitorata
		
		rs = Percorso.objects.by_date().select_related('arrivo').filter(linea=self, soppresso=False).distinct()
		
		ret['abilitata'] = self.abilitata_complessivo()
		ret['id_news'] = -1
		if not ret['abilitata']:
			ret['id_news'] = self.id_news_disabilitazione_complessivo()
		
		percorsi = []
		
		for r in rs:
			p = {}
			p['id_percorso'] = r.id_percorso
			p['descrizione'] = r.decodeCarteggio()
			p['capolinea'] = r.arrivo.nome_ricapitalizzato()
			
			percorsi.append(p)
		
		ret['percorsi'] = percorsi
		return ret

	def percorsi_attivi(self):
		return Percorso.objects.by_date().select_related('arrivo').filter(linea=self, soppresso=False).distinct()

	def getTipoDec(self):
		return TIPO_LINEA_CHOICES_DICT[self.tipo]

	
class DisabilitazionePalina(Disabilitazione):
	id_palina = models.CharField(db_index=True, max_length=20)


class Palina(VersionatoPaline, Disabilitabile):
	id_palina = models.CharField(db_index=True, max_length=20)
	nome = models.CharField(max_length=300)
	# x = models.IntegerField(default=0)
	# y = models.IntegerField(default=0)
	descrizione = models.CharField(max_length=1023, blank=True, default='')
	soppressa = models.BooleanField(blank=True, default=False)
	geom = gismodels.PointField(srid=3004, blank=True, null=True, default=None)

	chiave_disabilitazione = 'id_palina'
	disabilitazione = DisabilitazionePalina

	def nome_ricapitalizzato(self):
		return ricapitalizza(self.nome)

	def getVeicoli(self, lineas=None, caching=True):
		"""
		Restituisce i veicoli
		
		lineas filtra per linea. Può essere:
			* None: restituisce tutte le linee
			* Una stringa: restituisce solo la linea passata
			* Una lista di stringhe: restituisce solo le linee passate

		caching è un parametro fittizio, presente nella segnatura per compatibilità con il passato
		"""
		if type(lineas) == str or type(lineas) == unicode:
			lineas = [lineas]			
		ret = {}
		ret['abilitata'] = self.abilitata_complessivo()
		if ret['abilitata']:
			ret['id_news'] = -1
		else:
			ret['id_news'] = self.id_news_disabilitazione_complessivo()
		if lineas is not None:
			ret['linea'] = ",".join(lineas)
		ret['collocazione'] = self.descrizione
		merc = get_web_cl_mercury()
		v = merc.sync_any('tempi_attesa_ap', {'id_palina': self.id_palina})
		veicoli = []
		for el in v:
			el2 = {}
			id_linea = el['id_linea']
			if lineas is None or id_linea in lineas:
				tempo = int(el['tempo'])
				distanza_fermate = int(el['fermate'])
				if tempo > (10 + 4 * distanza_fermate) * 60:
					tempo = -1
				a_capolinea = el['a_capolinea']
				id_percorso = el['id_percorso']
				el2['linea'] = id_linea
				el2['tempo_attesa'] = str(tempo)
				el2['distanza_fermate'] = str(distanza_fermate)
				el2['id_percorso'] = id_percorso
				el2['id_veicolo'] = el['id_veicolo']
				el2['in_arrivo'] = int((tempo == -1 and distanza_fermate < 1) or (not a_capolinea and tempo >= 0 and tempo <= INTERVALLO_IN_ARRIVO))
				el2['pedana'] = int(el['pedana'])
				el2['moby'] = int(el['moby'])
				el2['aria'] = int(el['aria'])
				el2['meb'] = int(el['meb'])
				el2['a_capolinea'] = int(a_capolinea)
				el2['stato_occupazione'] = el['stato_occupazione']
				el2['dest_zone'] = el['dest_zone']
				el2['prossima_partenza'] = ''
				if a_capolinea:
					try:
						if 'orario_partenza_capolinea' in el:
							el2['prossima_partenza'] = el['orario_partenza_capolinea']
						# else:
						# 	percorso = Percorso.seleziona_con_cache(id_percorso=id_percorso)
						# 	prossima_partenza = percorso.getProssimaPartenza()
						# 	if prossima_partenza is not None:
						# 		el2['prossima_partenza'] = prossima_partenza
					except Exception as e:
						pass
				el2['annuncio'] = componi_annuncio(el2)
				try:
					p = Percorso.seleziona_con_cache(el['id_percorso'])
					el2['carteggi_dec'] = p.decodeCarteggio()
					el2['carteggi'] = p.carteggio_quoz
					arrivo = p.getArrivo()
					el2['capolinea'] = arrivo['nome']
				except Exception, e:
					#e = errors.XMLRPC['XRE_NO_PERCORSO']
					#e.message = "Percorso inesistente: %s, %s" % (type(l['id_percorso']), str(l['id_percorso']))
					#raise e
					#print e
					el2['carteggi_dec'] = ''					
					el2['capolinea'] = ''	
					el2['carteggi'] = ''
				veicoli.append(el2)
		ret['veicoli'] = veicoli 
		ret['nome'] = self.nome_ricapitalizzato()

		return ret

	
	def getVeicoliFiltraPerLinea(self, id_linea, caching=False):
		vs = self.getVeicoli(caching=caching)

		linee = []
		for v in vs['veicoli']:
			if v['linea'] == id_linea:
				linee.append(v)
		vs['veicoli'] = linee
		return vs

	def getLinee(self):
		ret = []
		
		fs = Fermata.objects.by_date().filter(palina=self)
		ps = Percorso.objects.by_date().filter(fermata__in=fs, soppresso=False)
		rs = Linea.objects.by_date().filter(percorso__in=ps, tipo__in=TIPI_LINEA_INFOTP).distinct()
		
		for r in rs:
			l = {}
			l['linea'] = r.id_linea
			l['monitorata'] = r.monitorata
			l['abilitata'] = r.abilitata_complessivo()
			if l['abilitata']:
				l['id_news'] = -1
			else:
				l['id_news'] = r.id_news_disabilitazione_complessivo()
			ret.append(l)
		
		return ret
	
	def ha_linee_infotp(self):
		return Linea.objects.by_date().filter(tipo__in=TIPI_LINEA_INFOTP, percorso__fermata__palina=self).count() > 0


class DisabilitazionePercorso(Disabilitazione):
	id_percorso = models.CharField(max_length=30, db_index=True)


class NomePalina(VersionatoPaline):
	parte = models.CharField(max_length=300, db_index=True)
	palina = models.ForeignKey(Palina)


class MaxIdPercorso(models.Model):
	id_percorso = models.IntegerField(default=0)

	@classmethod
	def get_max_id_percorso(cls):
		try:
			ip = cls.objects.get(pk=1)
			i = ip.id_percorso
		except cls.DoesNotExist:
			i = 0
		return i

	@classmethod
	def set_max_id_percorso(cls, i):
		ip, created = cls.objects.get_or_create(pk=1)
		ip.id_percorso = i
		ip.save()


class Percorso(VersionatoPaline, Disabilitabile):
	id_percorso = models.CharField(max_length=30, db_index=True)
	linea = models.ForeignKey(Linea, db_index=True)
	partenza = models.ForeignKey(Palina, related_name='id_palina_partenza', db_index=True)
	arrivo = models.ForeignKey(Palina,related_name='id_palina_arrivo', db_index=True)
	verso = models.CharField(max_length=1)
	carteggio = models.CharField(max_length=20, db_index=True)
	carteggio_quoz = models.CharField(max_length=19, db_index=True)
	descrizione = models.CharField(max_length=150, null=True, default=None)
	no_orari = models.BooleanField(blank=True, default=False)
	soppresso = models.BooleanField(blank=True, default=False)
	note_no_orari = models.CharField(max_length=127, blank=True, default='')
	
	chiave_disabilitazione = 'id_percorso'
	disabilitazione = DisabilitazionePercorso
	dipendenze_abilitazione = ['linea']
	
	@classmethod
	def seleziona_con_cache(cls, id_percorso):
		p = cache.get('percorso-%s' % id_percorso)
		if p is not None:
			return p
		p = Percorso.objects.by_date().select_related().get(id_percorso=id_percorso)
		cache.set('percorso-%s' % id_percorso, p, 300)
		return p
	
	def getPercorso(self):
		abilitato = self.abilitata_complessivo()
		return {
			'id_percorso': self.id_percorso,
			'id_linea': self.linea.id_linea,
			'arrivo': self.arrivo.nome_ricapitalizzato(),
			'carteggio': self.carteggio_quoz,
			'carteggio_dec': self.decodeCarteggio(),
			'abilitata': abilitato,
			'id_news': -1 if abilitato else self.id_news_disabilitazione_complessivo(),
			'gestore': self.linea.gestore.descrizione,
			'descrizione': self.descrizione,
		}
	
	def getFermate(self):
		ret = {}
		ret['linea'] = self.linea.id_linea
		ret['capolinea'] = self.arrivo.nome_ricapitalizzato()
		ret['descrizione'] = self.decodeCarteggio()
		
		fs = Fermata.objects.by_date().select_related().filter(percorso=self).order_by('progressiva')
		
		fermate = []
		
		for fe in fs:
			p = fe.palina
			if not p.soppressa:
				f = {}
				f['id_palina'] = p.id_palina
				f['nome'] = p.nome_ricapitalizzato()
				f['progressiva'] = fe.progressiva
				f['abilitata'] = fe.abilitata_complessivo()
				id_news = -1
				if not f['abilitata']:
					id_news = p.id_news_disabilitazione_complessivo()
					f['id_news'] = id_news
				fermate.append(f)
		
		ret['fermate'] = fermate
		return ret
	
	def decodeCarteggio(self):
		c = cache.get('percorso-carteggio-dec-%s' % self.carteggio_quoz)
		if c is not None:
			return c
		c = " ".join([Carteggio.objects.by_date().get(codice=k).descrizione for k in self.carteggio_quoz])
		cache.set('percorso-carteggio-dec-%s' % self.carteggio_quoz, c, 5000)
		return c
	
	def getNomeCompleto(self):
		return _(u"%(linea)s %(cart)s direz. %(dest)s") % {
			'linea': self.descrizione if self.descrizione else self.linea.id_linea,
			'cart': self.decodeCarteggio(),
			'dest': ricapitalizza(self.arrivo.nome),
		}
		
	def getArrivo(self):
		ret = {}
		ret['id_palina'] = self.arrivo.id_palina
		ret['nome'] = self.arrivo.nome_ricapitalizzato()
		ret['id_linea'] = self.linea.id_linea		
		return ret
	
	def getProssimaPartenza(self):
		sql = """
			select min(orario_partenza) as op
			from partenze_capilinea
			where id_percorso = %s
			and orario_partenza >= now() - interval 5 minute
		"""
		
		try:
			cursor = connections['default'].cursor()
			cursor.execute(sql, (self.id_percorso, ))
			return cursor.fetchall()[0][0]
		except Exception as e:
			raise e
			raise errors.XMLRPC['XRE_DB']
		
	def getVeicolo(self, id_veicolo, caching=False):
		
		ret = {}
		ret['linea'] = self.linea.id_linea
		ret['carteggi_dec'] = self.decodeCarteggio()
		ret['capolinea'] = self.arrivo
		
		fermate_orig = self.getFermate()['fermate']
		veicolo_transitato = False
		fermate = []
		for p in fermate_orig:
			try:
				palina = Palina.objects.by_date().get(id_palina=p['id_palina'])
			except:
				raise errors.XMLRPC['XRE_NO_ID_PALINA']
			veicoli = palina.getVeicoli(caching)
			
			f = {}
			f['in_arrivo'] = False
			f['orario_previsto'] = ''
			
			for v in veicoli['veicoli']:
				if v['id_veicolo'] == id_veicolo:
					ret['meb'] = v['meb']
					ret['pedana'] = v['pedana']
					ret['moby'] = v['moby']
					ret['aria'] = v['aria']
					ret['a_capolinea'] = v['a_capolinea']
					veicolo_transitato = True
					f['in_arrivo'] = True
					if not ret['a_capolinea']:
						f['orario_previsto'] = time.strftime("%H:%M", time.localtime(time.time() + v['tempo_attesa']))
					break
			
			
			f['id_palina'] = palina.id_palina
			f['nome'] = palina.nome_ricapitalizzato()
			f['raggiunta'] = veicolo_transitato
			fermate.append(f)
		
		# Check veicolo trovato
		if not veicolo_transitato:
			raise errors.XMLRPC['XRE_NO_VEHICLE']
		
		ret['fermate'] = fermate
		return ret
	
	def get_veicoli(self, get_arrivi, id_veicolo=None):
		"""
		Vehicles are sorted starting from "oldest" (nearest to final destination)
		"""
		fermate = None  # Loaded lazily if needed
		merc = get_web_cl_mercury()
		vs = merc.sync_any('veicoli_percorso_ap', {'id_percorso': self.id_percorso, 'get_arrivi': get_arrivi})
		out = []
		for v in vs:
			try:
				if id_veicolo is None or v['id_veicolo'] == id_veicolo:
					p = gbfe_to_wgs84(v['x'], v['y'])
					el = {
						'id_veicolo': v['id_veicolo'],
						'lon': p[0],
						'lat': p[1],
						'id_prossima_palina': v['id_prossima_palina'],
						'a_capolinea': v['a_capolinea'],
						'orario_partenza_capolinea': v['orario_partenza_capolinea'],
						'stato_occupazione': v['stato_occupazione'],
					}
					if get_arrivi:
						infobox = '<p><b>Veicolo %s</b></p><p>' % v['id_veicolo']
						arrivi = v['arrivi']
						if fermate is None:
							fermate = Fermata.objects.by_date().filter(percorso=self).order_by('progressiva')
						for f in fermate:
							pal = f.palina
							if not pal.soppressa and pal.id_palina in arrivi:
								orario = arrivi[pal.id_palina]
								infobox += '<b>%s:</b> %s<br/>' % (orario.strftime("%H:%M"), pal.nome_ricapitalizzato())
						infobox += '</p>'
						el['infobox'] = infobox
					out.append(el)
			except:
				# An exception may be raised if arrivals are being updated, and vehicle data is incomplete
				# In this case, we simply skip the vehicle
				traceback.print_exc()
		return out

	def adesso_attivo(self):
		key = 'percorso_adesso_attivo_%s' % self.id_percorso
		a = cache.get(key)
		if a is not None:
			return a
		if self.no_orari:
			return True
		now = datetime.now()
		count = PartenzeCapilinea.objects.filter(
			id_percorso=self.id_percorso,
			orario_partenza__gt=now - timedelta(minutes=60),
			orario_partenza__lt=now + timedelta(minutes=60),
		).count()
		a = count > 0
		cache.set(key, a, 20 * 60)
		return a


class TrattoPercorsi(VersionatoPaline):
	palina_s = models.ForeignKey(Palina, on_delete=models.CASCADE, related_name='fstar')
	palina_t = models.ForeignKey(Palina, on_delete=models.CASCADE, related_name='bstar')
	geom = gismodels.LineStringField(srid=3004)
	tipo = models.CharField(max_length=2, choices=TIPO_LINEA_CHOICES, default="BU")


class GtfsTrip(models.Model):
	trip_id = models.CharField(max_length=255)
	id_percorso = models.CharField(max_length=30)


class PercorsoAtac(VersionatoPaline):
	"""
	Sometimes Atac routes have different ID's than RSM
	"""
	percorso = models.ForeignKey(Percorso)
	id_percorso_atac = models.CharField(max_length=10, db_index=True)

	@classmethod
	def lookup(cls, id_percorso):
		"""
		Lookup for route id as an Atac id. If id is not found, look up in RSM routes.

		Return route (instance of Percorso), or None
		"""
		pas = cls.objects.by_date().filter(id_percorso_atac=id_percorso)
		if len(pas) == 1:
			return pas[0].percorso
		ps = Percorso.objects.by_date().filter(id_percorso=id_percorso)
		if len(ps) == 1:
			return ps[0]
		return None


def get_primi_arrivi(paline):
	ids = [p.id_palina for p in paline]
	merc = get_web_cl_mercury()
	arrivi_raw = merc.sync_any('primi_arrivi_per_paline', {'id_paline': ids})
	out = {}
	for palina in paline:
		fermate = Fermata.objects.by_date().filter(palina=palina)
		percorsi = Percorso.objects.by_date().filter(fermata__in=fermate, soppresso=False)
		percorsi = [p for p in percorsi if p.adesso_attivo()]
		linee = Linea.objects.by_date().filter(percorso__in=percorsi, tipo__in=TIPI_LINEA_INFOTP).distinct()
		ret = {}
		# Preparazione linee
		info_linee = {}
		for l in linee:
			linea = {}
			info_linee[l.id_linea] = linea
			linea['linea'] = l.id_linea
			if not l.abilitata_complessivo():
				linea['disabilitata'] = True
				news = l.news_disabilitazione_complessivo()
				linea['id_news'] = news.pk if news is not None else -1
			elif not l.monitorata:
				linea['non_monitorata'] = True
			else:
				linea['nessun_autobus'] = True

		# Aggiornamento linee con dati realtime
		id_palina = palina.id_palina
		v = arrivi_raw[id_palina]
		for el in v:
			el2 = {}
			id_linea = el['id_linea']
			if id_linea in info_linee:
				tempo = int(el['tempo'])
				distanza_fermate = int(el['fermate'])
				# Protezione da malfunzionamenti algoritmo previsione causati da dati di input errati:
				# in caso di tempi anomali, rendi tempo non disponibile
				if tempo > (10 + 4 * distanza_fermate) * 60:
					tempo = -1
				a_capolinea = el['a_capolinea']
				id_percorso = el['id_percorso']
				el2['tempo_attesa'] = str(tempo)
				el2['distanza_fermate'] = str(distanza_fermate)
				el2['id_percorso'] = id_percorso
				el2['id_veicolo'] = el['id_veicolo']
				el2['in_arrivo'] = int((tempo == -1 and distanza_fermate < 1) or (not a_capolinea and tempo >= 0 and tempo <= INTERVALLO_IN_ARRIVO))
				el2['a_capolinea'] = int(a_capolinea)
				el2['prossima_partenza'] = ''
				if a_capolinea:
					try:
						if 'orario_partenza_capolinea' in el:
							el2['prossima_partenza'] = el['orario_partenza_capolinea']
						# else:
						# 	percorso = Percorso.seleziona_con_cache(id_percorso=id_percorso)
						# 	prossima_partenza = percorso.getProssimaPartenza()
						# 	if prossima_partenza is not None:
						# 		el2['prossima_partenza'] = prossima_partenza
					except Exception as e:
						pass
				el2['annuncio'] = componi_annuncio(el2, short=True)
				info_linee[id_linea].update(el2)
				info_linee[id_linea]['nessun_autobus'] = False
		veicoli = [info_linee[id_linea] for id_linea in info_linee]
		veicoli.sort(key=lambda v: v['linea'])
		ret['veicoli'] = veicoli
		ret['nome_palina'] = palina.nome_ricapitalizzato()
		ret['id_palina'] = id_palina
		out[id_palina] = ret

	return out


class ReteDinamicaSerializzata(models.Model):
	ultimo_aggiornamento = models.DateTimeField()
	_rete = models.TextField(db_column='rete')

	def set_rete(self, data):
		self._rete = base64.encodestring(zlib.compress(pickle.dumps(data)))

	def get_rete(self):
		return pickle.loads(zlib.decompress(base64.decodestring(self._rete)))

	rete = property(get_rete, set_rete)


def _converti_dotazioni_bordo(x, dotaz):
	if x[dotaz]:
		x[dotaz + 'alt'] = dotaz[0].upper()
		x[dotaz] = dotaz
	else:
		x[dotaz + 'alt'] = ' '
		x[dotaz] = 'blank'


def _aggiungi_dotazioni_default(x, as_service=False):
	for dotaz in ['meb', 'moby', 'aria', 'pedana']:
		x[dotaz] = False
		if not as_service:
			_converti_dotazioni_bordo(x, dotaz)


def _cmp_linea_tempo(v1, v2):
	l1 = v1['linea']
	l2 = v2['linea']
	res = cmp(l1, l2)
	if res != 0:
		return res
	return cmp_tempi_attesa(v1, v2)



def enhance_routes_with_stats(routes):
	"""
	Given a list of Percorso instances (routes), enhance each route with its stats

	Adds two attributes to stats:
	- departures_count (hourly)
	- vehicles_count  (number of running vehicles)

	Return True if some routes shall be hidden
	"""
	route_ids = [p.id_percorso for p in routes]
	merc = get_web_cl_mercury()
	stats = merc.sync_any('route_stats', {'route_ids': route_ids})
	to_hide = 0
	for p in routes:
		if p.id_percorso in stats:
			s = stats[p.id_percorso]
			p.departures_count = s['departures']
			p.vehicles_count = s['vehicles']
			p.dest_zone = s['dest_zone']
			if 'alerts' in s:
				p.alerts = s['alerts']
			if p.departures_count + p.vehicles_count == 0:
				p.nascondi_percorso = True
				to_hide += 1
	return to_hide


def get_occupation_status_decoder():
	STATO_OCCUPAZIONE = {
		0: _(u"Vuoto"),
		1: _(u"Disponibili molti posti"),
		2: _(u"Disponibili pochi posti"),
		3: _(u"Solo posti in piedi"),
		4: _(u"Molto affollato"),
		5: _(u"Pieno"),
		6: _(u"Non accetta passeggeri"),
		7: _(u"Nessun dato sulla disponibilità di posti"),
		8: _(u"Fuori servizio"),
	}
	def decode_occupation_status(v):
		"""
		Decode occupation status and add decoded data to dictionary v
		"""
		v['stato_occupazione_dec'] = None
		v['stato_occupazione_3l'] = None
		if v.get('stato_occupazione'):
			so = v.get('stato_occupazione')
			v['stato_occupazione_dec'] = STATO_OCCUPAZIONE.get(so)
			if so < 2:
				v['stato_occupazione_3l'] = 1
			elif so < 4:
				v['stato_occupazione_3l'] = 2
			else:
				v['stato_occupazione_3l'] = 3
	return decode_occupation_status


def dettaglio_palina(palina, linee_escluse=set([]), nome_palina=None, caching=False, as_service=False):
	v = palina.getVeicoli(caching=caching)['veicoli']
	v.sort(cmp=_cmp_linea_tempo)
	v1 = []
	v2 = []
	linee_usate = set()
	linee_disabilitate = set()
	linea = None
	carteggi_usati = set()
	fermate = Fermata.objects.by_date().filter(palina=palina)
	percorsi = Percorso.objects.by_date().filter(fermata__in=fermate, soppresso=False).select_related('linea')
	ld = Linea.objects.by_date().filter(percorso__in=percorsi, tipo__in=TIPI_LINEA_INFOTP).distinct()
	percorsi = list(percorsi)
	enhance_routes_with_stats(percorsi)
	alerts = {}
	decode_occupation_status = get_occupation_status_decoder()
	for p in percorsi:
		if hasattr(p, 'alerts'):
			alerts[p.linea.id_linea] = p.alerts

	for x in v:
		if x['linea'] not in linee_escluse:
			x['id_palina'] = palina.id_palina
			x['nome_palina'] = nome_palina
			if not as_service:
				for dotaz in ['meb', 'moby', 'aria', 'pedana']:
					_converti_dotazioni_bordo(x, dotaz)
			tempo_attesa_secondi = int(x['tempo_attesa'])
			x['tempo_attesa'] = int(round(tempo_attesa_secondi / 60.0))
			x['tempo_attesa_secondi'] = tempo_attesa_secondi
			carteggi_usati.update(set(x['carteggi']))
			linee_usate.add(x['linea'])
			x['disabilitata'] = False
			x['alerts'] = alerts.get(x['linea'])
			decode_occupation_status(x)
			try:
				perc = Percorso.objects.by_date().get(id_percorso=x['id_percorso'])
				f = Fermata.objects.by_date().filter(percorso=perc, palina=palina)[0]
				x['destinazione'] = perc.arrivo.nome_ricapitalizzato()
				disabilitata = not f.abilitata_complessivo()
				x['disabilitata'] = disabilitata
				if disabilitata:
					news = f.news_disabilitazione_complessivo()
					if as_service:
						x['id_news'] = news.pk if news is not None else -1 
					else:
						x['news'] = news
					linee_disabilitate.add(x['linea'])
			except (Percorso.DoesNotExist, Fermata.DoesNotExist()):
				pass
			if linea != x['linea']:
				# ultima_linea_a_capolinea = False
				if x['a_capolinea'] and x['prossima_partenza'] != '':
					# ultima_linea_a_capolinea = True
					x['partenza'] = timefilter(x['prossima_partenza'], _("H:i"))
				if not x['disabilitata']:
					linea = x['linea']
					v1.append(x)
			elif not x['disabilitata']:
				if x['a_capolinea'] and x['prossima_partenza'] != '': # and not ultima_linea_a_capolinea:
					# ultima_linea_a_capolinea = True
					x['partenza'] = timefilter(x['prossima_partenza'], _("H:i"))
					v2.append(x)
				elif not x['a_capolinea']:
					v2.append(x)

	v3 = []
	for l in ld:
		if l.id_linea not in linee_escluse:
			if True: #l.id_linea[0].lower() != 'n':
				x = {}
				x['nome_palina'] = nome_palina
				x['id_palina'] = palina.id_palina
				x['alerts'] = alerts.get(l.id_linea)
				if not l.abilitata_complessivo() or not l.monitorata:
					news = None
					if not l in linee_disabilitate:
						x['linea'] = l.id_linea
						if not l.monitorata:
							x['non_monitorata'] = True
						else:
							x['disabilitata'] = True
							news = l.news_disabilitazione_complessivo()
						if as_service:
							x['id_news'] = news.pk if news is not None else -1
						else:
							x['news'] = news
						_aggiungi_dotazioni_default(x, as_service)
						v3.append(x)
				elif l.id_linea not in linee_usate:
					x['linea'] = l.id_linea
					x['nessun_autobus'] = True
					_aggiungi_dotazioni_default(x, as_service)
					v3.append(x)
	return v1, v2, v3, carteggi_usati


def cmp_tempi_attesa(a, b):
	ta = int(a['tempo_attesa'])
	tb = int(b['tempo_attesa'])
	if ta != -1 and tb == -1:
		return -1
	elif ta == -1 and tb != -1:
		return 1
	elif ta != -1:
		return ta.__cmp__(tb)
	else:
		c = cmp(int(a['distanza_fermate']), int(b['distanza_fermate']))
		if c != 0 or not a['a_capolinea']:
			return c
		# Entrambi i veicoli a capolinea. Privilegio quello con orario di partenza più basso,
		# ma prima di tutto privilegio quello con partenza nota
		pa = a['prossima_partenza']
		pb = b['prossima_partenza']
		if pa != '' and pb == '':
			return -1
		if pb != '' and pa == '':
			return 1
		return cmp(pa, pb)


def dettaglio_paline(nome, paline, linee_escluse=[], aggiungi=None, caching=False, as_service=False):
	v1 = []
	v2 = []
	v3 = []
	carteggi_usati = set()
	for p in paline:
		if isinstance(p, PalinaPreferita):
			try:
				palina = Palina.objects.by_date().get(id_palina=p.id_palina)
				nome = p.nome
			except Palina.DoesNotExist:
				palina = None
		else:
			palina = p
		if palina is not None:
			w1, w2, w3, c = dettaglio_palina(palina, linee_escluse, nome_palina=nome, caching=caching, as_service=as_service)
			v1.extend(w1)
			v2.extend(w2)
			v3.extend(w3)
			carteggi_usati.update(c)
	v1.sort(cmp=cmp_tempi_attesa)
	v2.sort(cmp=cmp_tempi_attesa)
	return v1, v2, v3, carteggi_usati


# Segnalazione disservizi
class Disservizio(models.Model):
	user = models.ForeignKey(User)
	orario = models.DateTimeField(db_index=True)
	id_palina = models.CharField(db_index=True, max_length=20)
	id_linea_segnalata = models.CharField(max_length=30, db_index=True, blank=True, null=True)
	id_linea_passata = models.CharField(max_length=30, blank=True, null=True)
	id_veicolo = models.CharField(max_length=7, db_index=True, blank=True, null=True)
	note = models.TextField(blank=True, null=True)
	
	def __unicode__(self):
		return u"%s: %s" % (self.orario, self.id_linea_segnalata if self.id_linea_segnalata is not None else "")


class DisservizioPalinaElettronica(models.Model):
	user = models.ForeignKey(User)
	orario = models.DateTimeField(db_index=True)
	id_palina = models.CharField(db_index=True, max_length=20)
	
	def __unicode__(self):
		return u"%s: %s" % (self.orario, self.id_palina)
	
	
# Monitoring
class GestoreDisabilitatoE20(models.Model):
	nome_gestore = models.CharField(max_length=30, db_index=True, unique=True)
	disabilitazione_pk = models.IntegerField()


# Preferenze profilazione: paline preferite			
class GruppoPalinePreferite(models.Model):
	user = models.ForeignKey(User)
	nome = models.CharField(max_length=63)
	singleton = models.BooleanField()
	
	def __unicode__(self):
		if self.singleton:
			try:
				p = PalinaPreferita.objects.get(gruppo=self)
				return unicode(p)
			except Exception:
				return ''			
		else:
			return self.nome
		
	def get_paline(self):
		ids = [p.id_palina for p in self.palinapreferita_set.all()]
		return Palina.objects.by_date().filter(id_palina__in=ids).distinct()

			
class PalinaPreferita(models.Model):
	id_palina = models.CharField(db_index=True, max_length=20)
	nome = models.CharField(max_length=63)
	gruppo = models.ForeignKey(GruppoPalinePreferite)
	
	def __unicode__(self):
		return self.nome


class LineaPreferitaEsclusa(models.Model):
	gruppo = models.ForeignKey(GruppoPalinePreferite)
	id_linea = models.CharField(max_length=30, db_index=True)
	
	def __unicode__(self):
		return u"%s: %s" % (self.gruppo, self.id_linea)


# Notifiche
class RichiestaNotificaPalina(RichiestaNotifica):
	def __init__(self, *args, **kwargs):
		kwargs['su_visita'] = True
		RichiestaNotifica.__init__(self, *args, **kwargs)
	
	gruppo = models.ForeignKey(GruppoPalinePreferite)
	min_attesa = models.IntegerField(default=2)
	max_attesa = models.IntegerField(default=7)
	
	def verifica_condizione(self):
		gp = self.gruppo
		nome = unicode(gp)
		paline = gp.palinapreferita_set.all()
		linee_escluse = [l.id_linea for l in gp.lineapreferitaesclusa_set.all()]
		v1, v2, v3, carteggi_usati = dettaglio_paline(nome, paline, linee_escluse)
		linee = set()
		veicoli = set()
		attesa_max = 0
		for a in v1 + v2:
			ta = a['tempo_attesa']
			if self.min_attesa <= ta and ta <= self.max_attesa:
				linee.add((a['linea'], a['nome_palina']))
				veicoli.add(a['id_veicolo'])
				attesa = ta
				attesa_max = max(attesa_max, ta)
		if len(linee) > 0:
			if len(linee) == 1:
				l = linee.pop()
				messaggio = _("%(palina)s: %(linea)s a %(tempo)d %(minuti)s") % {'palina': l[1], 'linea': l[0], 'tempo': attesa, 'minuti': _("minuto") if attesa == 1 else _("minuti")}
			else:
				linee_nodup = set([l[0] for l in linee])
				linea_plur = _("linea") if len(linee_nodup) == 1 else _("linee")
				messaggio = _("%(palina)s: in arrivo %(linea_plur)s %(linee)s") % {'palina': nome, 'linea_plur': linea_plur, 'linee': ", ".join(linee_nodup)}
			self.messaggio = messaggio
			self.scadenza = datetime.now() + timedelta(minutes=attesa_max)
			return self.pickle(veicoli)
		return None
	
	def verifica_footprint(self, nuovo):
		vecchio = self.unpickle(str(self.footprint))
		nuovo = self.unpickle(str(nuovo))
		return nuovo.issubset(vecchio)
	
	def get_url(self):
		return '/paline/gruppo/%d' % self.gruppo.pk


# Modelli per il calcola percorso
class FrequenzaPercorso(models.Model):
	id_percorso = models.CharField(max_length=30, db_index=True)
	ora_inizio = models.IntegerField(db_index=True)
	giorno_settimana = models.IntegerField(db_index=True)
	frequenza = models.FloatField()
	da_minuto = models.IntegerField(default=0)
	a_minuto = models.IntegerField(default=59)

	@classmethod
	def by_datetime(cls, id_percorso, dt=None):
		if dt is None:
			dt = datetime.now()
		d = Festivita.get_weekday(dt, compatta_feriali=True)
		f = cls.objects.get(
			id_percorso=id_percorso,
			ora_inizio=dt.hour,
			giorno_settimana=d,
		)
		if f.da_minuto <= dt.minute <= f.a_minuto:
			return f.frequenza
		return -1


class PartenzeCapilinea(models.Model):
	id_percorso = models.CharField(db_index=True, max_length=30)
	orario_partenza = models.DateTimeField(db_index=True)

	@classmethod
	def count_departures_by_route_id(cls, time_before=20 * 60, time_after=40 * 60):
		"""
		Map each route_id to the count of departures occurring in the specified period of time
		"""
		sql = """
			select P.id_percorso, count(*)
			from partenze_capilinea P
			where P.orario_partenza between %(from_time)s and %(to_time)s
			group by id_percorso		
		"""
		c = connections['default'].cursor()
		now = datetime.now()
		out = {}
		c.execute(sql, {'from_time': now - timedelta(seconds=time_before), 'to_time': now + timedelta(seconds=time_after)})
		for id_percorso, cnt in c:
			out[id_percorso] = cnt
		return out

	class Meta:
		db_table = 'partenze_capilinea'


class OrarioTreno(models.Model):
	id_percorso = models.CharField(max_length=30)
	# Validity: 0 = monday (and other working days), 5 = saturday, 6 = sunday
	giorno = models.IntegerField()
	# Comma-separated list of times
	orari = models.TextField()
	# Comma-separated list of stop id's
	id_paline = models.TextField()

	def __unicode__(self):
		return self.id_percorso

	class Meta:
		verbose_name_plural = "Orari treno"


class LineaSospesa(models.Model):
	id_linea = models.CharField(max_length=30, db_index=True)

	def __unicode__(self):
		return self.id_linea
	
	class Meta:
		verbose_name_plural = "Linee sospese"


class FermataSospesa(models.Model):
	id_fermata = models.CharField(max_length=30, db_index=True)
	descrizione = models.CharField(max_length=255, default='', blank=True)

	def __unicode__(self):
		return u"[{}] {}".format(self.id_fermata, self.descrizione)

	class Meta:
		verbose_name_plural = "Fermate sospese"


class ArcoRimosso(models.Model):
	"""
	Rappresenta l'id di un arco da eliminare dal grafo dopo averlo caricato
	
	Ad esempio, per rimuovere un arco tomtom con id 12345 (intero), creare due istanze di ArcoRimosso con i seguenti id:
	(12, 12345, 0)
	(12, 12345, 1)
	
	Non è possibile usare l'interfaccia di backend per creare un ArcoRimosso perché eid è un oggetto generico. Usare la shell, esempio:
	
	from paline.model import *
	ArcoRimosso(descrizione="Arco dannoso", eid=(12, 12345, 0)).save()  
	"""	
	descrizione = models.CharField(max_length=255, blank=True)
	eid = PickledObjectField()
	rimozione_attiva = models.BooleanField(blank=True, default=True)

	def __unicode__(self):
		return self.descrizione
	
	class Meta:
		verbose_name_plural = "Archi rimossi"

	
class LogTempoArco(models.Model):
	id_palina_s = models.CharField(db_index=True, max_length=20)
	id_palina_t = models.CharField(db_index=True, max_length=20)
	data = models.DateField(db_index=True)
	ora = models.TimeField(db_index=True)
	tempo = models.FloatField() # In effetti è una velocità
	peso = models.FloatField(default=1.0)


class LogTempoArcoAggr(models.Model):
	id_palina_s = models.CharField(db_index=True, max_length=20)
	id_palina_t = models.CharField(db_index=True, max_length=20)
	data = models.DateField(db_index=True)
	ora = models.IntegerField(db_index=True)
	tempo = models.FloatField()
	peso = models.FloatField(default=1.0)


class LogTempoAttesaPercorso(models.Model):
	id_percorso = models.CharField(db_index=True, max_length=30)
	data = models.DateField(db_index=True)
	ora = models.TimeField(db_index=True)
	tempo = models.FloatField()


class LogTempoAttesaPercorsoAggr(models.Model):
	id_percorso = models.CharField(db_index=True, max_length=30)
	data = models.DateField(db_index=True)
	ora = models.IntegerField(db_index=True)
	tempo = models.FloatField()


class LogPosizioneVeicolo(models.Model):
	id_percorso = models.CharField(db_index=True, max_length=30)
	id_veicolo = models.CharField(db_index=True, max_length=10)
	orario = models.DateTimeField(db_index=True)
	distanza_capolinea = models.FloatField()
	lon = models.FloatField()
	lat = models.FloatField()
	sistema = models.CharField(max_length=31, null=True, blank=True, default=None)


class StatPeriodoAggregazione(models.Model):
	"""
	Definizione dei periodi di aggregazione, per livelli
	
	Il livello più basso è quello più generico; all'aumentare del livello, aumenta la specificità
	(e quindi diminuisce la popolazione campionaria)
	"""
	livello = models.IntegerField(db_index=True)
	ora_inizio = models.TimeField(db_index=True)
	ora_fine = models.TimeField(db_index=True)
	wd0 = models.BooleanField(db_index=True)
	wd1 = models.BooleanField(db_index=True)
	wd2 = models.BooleanField(db_index=True)
	wd3 = models.BooleanField(db_index=True)
	wd4 = models.BooleanField(db_index=True)
	wd5 = models.BooleanField(db_index=True)
	wd6 = models.BooleanField(db_index=True)
	
	def __unicode__(self):
		gs = giorni_settimana(True)
		giorni = ", ".join([gs[i].capitalize() for i in range(7) if getattr(self, "wd%d" % i)])
		return "%s-%s di %s" % (
			self.ora_inizio.strftime("%H:%M"),
			self.ora_fine.strftime("%H:%M"),
			giorni,
		)  


class StatTempoArco(models.Model):
	id_palina_s = models.CharField(db_index=True, max_length=20)
	id_palina_t = models.CharField(db_index=True, max_length=20)
	tempo = models.FloatField()
	numero_campioni = models.IntegerField()
	periodo_aggregazione = models.ForeignKey(StatPeriodoAggregazione)
	

class StatTempoArcoNew(models.Model):
	id_palina_s = models.CharField(db_index=True, max_length=20)
	id_palina_t = models.CharField(db_index=True, max_length=20)
	tempo = models.FloatField()
	numero_campioni = models.IntegerField()
	periodo_aggregazione = models.ForeignKey(StatPeriodoAggregazione)


class StatTempoAttesaPercorso(models.Model):
	id_percorso = models.CharField(db_index=True, max_length=30)
	tempo = models.FloatField()
	numero_campioni = models.IntegerField()
	periodo_aggregazione = models.ForeignKey(StatPeriodoAggregazione)


class StatTempoAttesaPercorsoNew(models.Model):
	id_percorso = models.CharField(db_index=True, max_length=30)
	tempo = models.FloatField()
	numero_campioni = models.IntegerField()
	periodo_aggregazione = models.ForeignKey(StatPeriodoAggregazione)

	
"""
class PercorsoSalvato(models.Model):
	utente_generico = models.ForeignKey(UtenteGenerico)
	punti = PickledObjectField()
	percorso = PickledObjectField()
	opzioni = PickledObjectField()
"""


class StradaTomtom(Luogo):
	GeoModel = Polilinea 
	
	eid = models.IntegerField(db_index=True)
	count = models.IntegerField(db_index=True)
	sid = models.IntegerField(db_index=True)
	tid = models.IntegerField(db_index=True)
	velocita = models.FloatField(db_index=True)
	auto = models.FloatField()
	lunghezza = models.FloatField()
	tipo = models.IntegerField()
	ztl = models.BooleanField()
	

class LogCercaPercorso(models.Model):
	orario_richiesta = models.DateTimeField(db_index=True)
	orario_partenza = models.DateTimeField()
	da = models.CharField(max_length=127)
	a = models.CharField(max_length=127)
	piedi = models.IntegerField()
	max_bici = models.FloatField()
	tempo_calcolo = models.FloatField()
	bus = models.BooleanField()
	metro = models.BooleanField()
	fr = models.BooleanField()
	fc = models.BooleanField()
	auto = models.IntegerField()
	carpooling = models.BooleanField()
	linee_escluse = models.CharField(max_length=127)
	da_lng = models.FloatField(null=True, blank=True, default=None)
	da_lat = models.FloatField(null=True, blank=True, default=None)
	a_lng = models.FloatField(null=True, blank=True, default=None)
	a_lat = models.FloatField(null=True, blank=True, default=None)
	distanza = models.FloatField(null=True, blank=True, default=None)
	tempo = models.IntegerField(null=True, blank=True, default=None)
	
	def __unicode__(self):
		return "[%s] %s -> %s" % (self.orario_richiesta, self.da, self.a)
	
	class Meta:
		verbose_name_plural = "Log cerca percorso"	


class LogAvm(models.Model):
	id_gestore = models.ForeignKey(Gestore)
	id_veicolo = models.CharField(max_length=5)
	data = models.DateField()
	ora = models.TimeField()
	lat = models.FloatField()
	lon = models.FloatField()
	gps_fix = models.CharField(max_length=1)
	id_linea = models.CharField(max_length=10)
	id_percorso = models.CharField(max_length=10, blank=True, null=True)
	evento = models.CharField(max_length=5)
	numero_passeggeri = models.IntegerField(blank=True, null=True, default=-1)
	carico_passeggeri = models.FloatField(blank=True, null=True, default=-1)

	def __unicode__(self):
		return "[%s] %s" % (self.id_linea, self.id_veicolo)

	class Meta:
		verbose_name_plural = "Log Avm"


class IndirizzoAutocompl(models.Model):
	indirizzo = models.CharField(max_length=127, db_index=True)

	def __unicode__(self):
		return self.indirizzo

	class Meta:
		verbose_name = "Indirizzo autocompletamento"
		verbose_name_plural = "Indirizzi autocompletamento"


class ParolaIndirizzoAutocompl(models.Model):
	parola = models.CharField(max_length=63, db_index=True)
	indirizzo_autocompl = models.ForeignKey(IndirizzoAutocompl)

	def __unicode__(self):
		return "(%s, %s)" % (self.parola, self.indirizzo_autocompl.indirizzo)

	class Meta:
		verbose_name = "Parola indirizzo autocompletamento"
		verbose_name_plural = "Parole indirizzi autocompletamento"

	@classmethod
	def costruisci(cls):
		with transaction():
			cls.objects.all().delete()
			ias = IndirizzoAutocompl.objects.all()
			for ia in ias:
				# print ia.indirizzo
				for p in ia.indirizzo.split():
					ParolaIndirizzoAutocompl(
						parola=p.lower(),
						indirizzo_autocompl=ia,
					).save()


class Area(gismodels.Model):
	name = gismodels.CharField(max_length=254)
	geom = gismodels.MultiPolygonField(srid=3004)

	objects = gismodels.GeoManager()

	def __unicode__(self):
		return self.name

	class Meta:
		db_table = 'areas'
