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


from django.db import models
from django.contrib.gis.db import models as gismodels
from django.db.models import Q
from django.contrib.contenttypes import models as contenttypes
from datetime import datetime, timedelta, time
from utils import oggetto_con_min, oggetto_con_max, ora_breve, weekday2string, datetime2date, date2mysql
from django.contrib.auth.models import User, Group
import cPickle as pickle
import hashlib
from django.core.cache import cache
from contextlib import contextmanager
import random


RICERCHE_RECENTI_MAX_LENGTH = 10
RICERCHE_RECENTI_MAX_AGE = timedelta(days=60)

# Supporto fasce di validità
class ConFasce(models.Model):
	"""
	Modello astratto per definire istanze con fasce di attivazione
	
	Osservare che, se un'istanza non ha fasce di attivazione, è sempre attiva.
	Altrimenti è attiva solo nelle fasce di attivazione.
	
	Uso:
	Semplicemente da derivare, non necessita di alcun overriding (necessario invece per FasciaValidita)
	"""
	def attivo(self):
		if self.disabilitatore.filter(consenso=False).count() > 0:
			return False
		frns = self.fasce.all()
		if len(frns) == 0:
			return True
		n = datetime.now()
		nt = time(hour=n.hour, minute=n.minute, second=n.second)
		for frn in frns:
			if frn.ora_inizio <= nt and nt <= frn.ora_fine and str(n.weekday()) in frn.giorni:
				return True
		return False

	class Meta:
		abstract = True	


class FasciaValidita(models.Model):
	"""
	Modello astratto per definire fasce di attivazione
		
	Uso:
	Effettuare overriding di con_fasce:
	con_fasce = models.ForeignKey(<modello_con_fasce>, related_name='fasce')
	"""
	ora_inizio = models.TimeField(db_index=True)
	ora_fine = models.TimeField(db_index=True)
	giorni = models.CharField(max_length=7)
	
	def ora_inizio_breve(self):
		return ora_breve(self.ora_inizio)
	
	def ora_fine_breve(self):
		return ora_breve(self.ora_fine)
	
	def giorni_breve(self):
		return ", ".join([weekday2string(int(x), True).capitalize() for x in self.giorni])
	
	def __unicode__(self):
		return "%s: Dalle %s alle %s di %s" % (unicode(self.con_fasce), self.ora_inizio_breve(), self.ora_fine_breve(), self.giorni_breve())
	
	class Meta:
		abstract = True


class DisabililtatoreConFasce(models.Model):
	"""
	Modello astratto per disabilitare temporaneamente istanze di tipo ConFasce
		
	Uso:
	Effettuare overriding di con_fasce:
	con_fasce = models.ForeignKey(<modello_con_fasce>, related_name='disabilitatore')
	"""
	consenso = models.BooleanField(db_index=True)
	

class Festivita(models.Model):
	giorno = models.IntegerField(db_index=True)
	mese = models.IntegerField(db_index=True)
	anno = models.IntegerField(db_index=True, null=True, blank=True)
	prefestivo = models.BooleanField(blank=True, default=False)
	
	def __unicode__(self):
		if self.anno is None:
			return "%02d-%02d" % (self.mese, self.giorno)
		return "%d-%02d-%02d" % (self.anno, self.mese, self.giorno)
	
	class Meta:
		verbose_name = u'Festività'
		verbose_name_plural = u'Festività'
		
	@classmethod
	def find_festivita(cls, dt):
		"""
		Se il datetime dt corrisponde a una festività, restituisce la festività. Altrimenti None.
		"""
		fs = Festivita.objects.filter(giorno=dt.day, mese=dt.month)
		for f in fs:
			if f.anno is None or f.anno == dt.year:
				return f
		return None
	
	@classmethod
	def get_weekday(cls, dt, giorno_successivo=False, compatta_feriali=False):
		if giorno_successivo:
			d = dt + timedelta(days=1)
		else:
			d = dt
		d = datetime2date(dt)
		cache_key = "get_weekday_%s_%d" % (date2mysql(d), 1 if compatta_feriali else 0)
		r = cache.get(cache_key)
		if r is not None:
			return r
		f = cls.find_festivita(d)
		if f is None:
			wd = d.weekday()
		else:
			if f.prefestivo:
				wd = 5
			else:
				wd = 6
		if compatta_feriali and wd < 5:
			wd = 0
		cache.set(cache_key, wd)
		return wd


# Preferenze utenti
class Lingua(models.Model):
	codice = models.CharField(max_length=10, primary_key=True)
	descrizione = models.CharField(max_length=31)
	attiva = models.BooleanField(default=True)
	
	def __unicode__(self):
		return self.descrizione
	
	class Meta:
		verbose_name_plural = 'Lingue'
		
		
class LinguaPreferita(models.Model):
	utente = models.ForeignKey(User)
	lingua = models.ForeignKey(Lingua)
	def __unicode__(self):
		
		return unicode(self.utente)
	
	class Meta:
		verbose_name_plural = 'Lingue preferite'	
	
class LogoPersonalizzato(models.Model):
	utente = models.ForeignKey(User)
	path = models.CharField(max_length=63)
	
	def __unicode__(self):
		return unicode(self.utente)
	
	class Meta:
		verbose_name_plural = 'Loghi personalizzati'		


# Servizi
class Servizio(ConFasce):
	nome = models.CharField(max_length=100)

	def attivo(self):
		return self.abilitato == '1' or (self.abilitato == 'A' and ConFasce.attivo(self))
	
	abilitato = models.CharField(max_length=1, choices=[('0', 'Off'), ('A', 'Auto'), ('1', 'On')])
	
	def utente_abilitato(self, u):
		gs = self.grupposervizio_set
		return gs.count() == 0 or (u.is_authenticated() and gs.filter(gruppo__in=u.groups.all()).count()) > 0 
	
	def __unicode__(self):
		return self.nome
	
	class Meta:
		verbose_name_plural = 'Servizi'


class FasciaServizio(FasciaValidita):
	con_fasce = models.ForeignKey(Servizio, related_name='fasce')


class DisabilitatoreServizio(DisabililtatoreConFasce):
	con_fasce = models.ForeignKey(Servizio, related_name='disabilitatore')


class Versione(models.Model):
	servizio = models.ForeignKey(Servizio)
	numero = models.IntegerField()
	attiva = models.BooleanField(default=True)
	log_invocazioni = models.BooleanField(default=True)
	log_parametri = models.BooleanField(default=False)
	log_risposte = models.BooleanField(default=False)
	
	def __unicode__(self):
		return u"%s/%d" % (unicode(self.servizio), self.numero)
	
	class Meta:
		verbose_name_plural = 'Versioni'	
	
	def is_attiva(self):
		c = cache.get('versione-is-attiva-%s' % self.__unicode__())
		if c is not None:
			return c
		c = self.attiva and self.servizio.attivo()
		cache.set('versione-is-attiva-%s' % self.__unicode__(), c, 30)
		return c

	
class ServizioFrontEnd(models.Model):
	servizio = models.ForeignKey(Servizio)
	descrizione = models.CharField(max_length=63)
	attivo = models.BooleanField(default=True)
	nascosto = models.BooleanField(default=False)
	ordine = models.IntegerField()
	
	def __unicode__(self):
		return self.descrizione
	
	class Meta:
		verbose_name_plural = 'ServiziFrontEnd'
		
	def nome(self):
		return self.servizio.nome


class ServizioLingua(models.Model):
	servizio = models.ForeignKey(ServizioFrontEnd)
	lingua = models.ForeignKey(Lingua)
	attivo = models.BooleanField(default=True)
	nascosto = models.BooleanField(default=False)
	descrizione = models.CharField(max_length=63)
	
	def get_attivo(self):
		return self.attivo and self.servizio.attivo and self.servizio.servizio.attivo() and self.lingua.attiva
	
	def get_nascosto(self):
		return self.nascosto or self.servizio.nascosto
	
	def __unicode__(self):
		return "%s (%s: %s)" % (self.servizio.descrizione, self.lingua.descrizione, self.descrizione)
	
	def nome(self):
		return self.servizio.servizio.nome
	
	class Meta:
		verbose_name = 'Servizio in lingua'
		verbose_name_plural = 'Servizi in lingua'
		

class GruppoServizio(models.Model):
	servizio = models.ForeignKey(Servizio)
	gruppo = models.ForeignKey(Group)
	
	def __unicode__(self):
		return u"(%s, %s)" % (unicode(self.servizio), unicode(self.gruppo))
	
	class Meta:
		verbose_name = 'Gruppo abilitato al servizio'
		verbose_name_plural = 'Gruppi abilitati ai servizi'


class AggiornamentoStato(models.Model):
	orario = models.DateTimeField()
	modello = models.ForeignKey(contenttypes.ContentType)
	oggetto = models.IntegerField()


class Stato(object):
	def save(self, *args, **kwargs):
		models.Model.save(self, *args, **kwargs)
		a = AggiornamentoStato(
			orario=datetime.now(),
			modello=contenttypes.ContentType.objects.get_for_model(type(self)),
			oggetto=self.pk,
		)
		a.save()


def enforce_session(request):
	if request.session.session_key is None:
		request.session.create()

class UtenteGenerico(models.Model):
	utente = models.ForeignKey(User, null=True, blank=True, default=None)
	sessione = models.CharField(max_length=40, db_index=True, blank=True, null=True, default=None)
	ultimo_aggiornamento = models.DateTimeField(db_index=True, auto_now_add=True)
	
	@classmethod
	def by_request(cls, request):
		if request is None:
			raise UtenteGenerico.DoesNotExist()
		enforce_session(request)
		try:
			if request.user.is_authenticated():
				return cls.objects.filter(utente=request.user)[0]
			else:
				return cls.objects.filter(sessione=request.session.session_key)[0]
		except Exception:
			raise UtenteGenerico.DoesNotExist()
		
	@classmethod
	def update(cls, request):
		if request.user.is_authenticated():
			ugs = cls.objects.filter(utente=request.user)
			if len(ugs) > 0:
				ug = ugs[0]
			else: 
				ug = cls(utente=request.user)
				ug.save()
		else:
			enforce_session(request)
			ugs = cls.objects.filter(sessione=request.session.session_key)
			if len(ugs) > 0:
				ug = ugs[0]
			else: 
				ug = cls(sessione=request.session.session_key)
				ug.save()			
		ug.ultimo_aggiornamento = datetime.now()
		ug.save()
		return ug
		
	
	def __unicode__(self):
		if self.utente is not None:
			return unicode(self.utente)
		else:
			return self.sessione
	
	class Meta:
		verbose_name_plural = "Utenti generici"	


class Luogo(models.Model):
	nome_luogo = models.CharField(max_length=255, db_index=True)
	GeoModel = None

	def __init__(self, *args, **kwargs):
		if 'geom' in kwargs:
			self._geom = kwargs['geom']
			del kwargs['geom']
			self.dirtygeom = True
		else:
			self.dirtygeom = False
		
		models.Model.__init__(self, *args, **kwargs)
		
	def _get_geom(self):
		if self.dirtygeom:
			return self._geom
		try:
			g = self.GeoModel.objects.get(parent_type=contenttypes.ContentType.objects.get_for_model(type(self)).pk, parent_id=self.pk)
			return g.geom
		except self.GeoModel.DoesNotExist:
			return None
	
	def _set_geom(self, geom):
		self._geom = geom
		self.dirtygeom = True
		
	geom = property(_get_geom, _set_geom)
	
	def save(self):
		models.Model.save(self)
		if self.dirtygeom:
			self.dirtygeom = False
			try:
				g = self.GeoModel.objects.get(parent_type=contenttypes.ContentType.objects.get_for_model(type(self)).pk, parent_id=self.pk)
				g.geom = self._geom
				g.save()
			except self.GeoModel.DoesNotExist:
				g = self.GeoModel(
					parent_type=contenttypes.ContentType.objects.get_for_model(type(self)).pk,
					parent_id=self.pk,
					geom=self._geom
				)
				g.save()
				
	def delete(self):
		if self.GeoModel is not None:
			try:
				g = self.GeoModel.objects.get(parent_type=contenttypes.ContentType.objects.get_for_model(type(self)).pk, parent_id=self.pk)
				g.delete()
			except self.GeoModel.DoesNotExist:
				pass
		models.Model.delete(self)
		
	def descrizione(self):
		return unicode(self)	
	
	class Meta:
		verbose_name_plural = "Luoghi"
		
	
class LuogoUtente(models.Model):
	luogo = models.ForeignKey(Luogo)
	utente_gererico = models.ForeignKey(UtenteGenerico)
	
	class Meta:
		verbose_name_plural = "Luoghi utente"		
	

class StatoTrasportistico(Stato, models.Model):
	severita = models.FloatField()
	t_pubblico = models.FloatField()
	t_privato = models.FloatField()
	luogo = models.ForeignKey(Luogo)


class GiornoSettimana(models.Model):
	# modello giorno della settimana:
	# 1 = domenica
	codice = models.IntegerField(unique=True)
	nome = models.CharField(max_length=100)
	
	def __unicode__(self):
		return self.nome
	
	class Meta:
		verbose_name = u'Giorni settimana'
		verbose_name_plural = u'Giorno settimana'
	

# versioning generico
class VersioneManager(models.Manager):
	def ultima(self):
		return oggetto_con_max(self.get_query_set(), 'numero')
	

class VersioneVersioning(models.Model):
	@classmethod
	def auto_create(cls, inizio_validita=None):
		try:
			n = cls.objects.ultima().numero + 1
		except cls.DoesNotExist:
			n = 1
		if inizio_validita is None:
			inizio_validita = datetime.now()
		return cls(numero=n, inizio_validita=inizio_validita)
		
	numero = models.IntegerField(db_index=True)
	inizio_validita = models.DateTimeField(db_index=True)
	attiva = models.BooleanField(db_index=True)
	
	objects = VersioneManager()
	
	class Meta:
		abstract = True
		
	@classmethod
	def attuale(cls):
		v = oggetto_con_max(cls.objects.filter(attiva=True, inizio_validita__lte=datetime.now()), 'inizio_validita')
		return v

	@classmethod
	def by_date(cls, dt=None):
		v = oggetto_con_max(cls.objects.filter(attiva=True, inizio_validita__lte=dt), 'inizio_validita').numero
		return cls.objects.get(numero=v)


class VersionatoManager(gismodels.GeoManager):
	def __init__(self, versione):
		models.Manager.__init__(self)
		self.versione = versione

	def by_date(self, dt=None):
		if dt is None:
			v = cache.get('versionato-%s' % self.versione.__name__)
			if v is None:
				v = oggetto_con_max(self.versione.objects.filter(attiva=True, inizio_validita__lte=datetime.now()), 'inizio_validita').numero
				cache.set('versionato-%s' % self.versione.__name__, v, 60)
		else:
			v = oggetto_con_max(self.versione.objects.filter(attiva=True, inizio_validita__lte=dt), 'inizio_validita').numero
		return self.get_query_set().filter(min_versione__lte=v, max_versione__gte=v)
	
	def by_version(self, v):
		n = v.numero
		return self.get_query_set().filter(min_versione__lte=n, max_versione__gte=n)
	
	def with_latest_version(self):
		v = self.versione.objects.ultima().numero
		return self.get_query_set().filter(min_versione__lte=v, max_versione__gte=v)

	def delete_queryset(self, qs):
		for q in qs:
			q.delete()


class Versionato(gismodels.Model):
	min_versione = models.IntegerField(db_index=True)
	max_versione = models.IntegerField(db_index=True)
		
	class Meta:
		abstract = True
		
	def get_field_names(self):
		return [f.name for f in self._meta.fields if f.name not in ['id', 'min_versione', 'max_versione']]		
		
	def save(self):
		v = self.versione.objects.ultima().numero
		try:
			o = oggetto_con_max(self.__class__.objects.filter(**dict([(fn, getattr(self, fn)) for fn in self.get_field_names()])), 'max_versione')
			if o.max_versione == v:
				self.pk = o.pk
				self.min_versione = o.min_versione
				self.max_versione = v
			else:
				if o.max_versione == v - 1:
					self.pk = o.pk
					self.min_versione = o.min_versione
					self.max_versione = v
				else:
					self.pk = None
					self.min_versione = v
					self.max_versione = v
		except Exception: #self.DoesNotExist:
			self.pk = None
			self.min_versione = v
			self.max_versione = v
		models.Model.save(self)
		
	@classmethod
	def revert(cls, v):
		"""
		Copia tutte le istanze dalla versione v nella versione attuale.
		
		Prima di invocare revert, è necessario creare una nuova versione.
		v deve essere un'istanza del modello Versione 
		"""
		ss = cls.__subclasses__()
		if len(ss) > 0:
			for s in ss:
				s.revert(v)
		else:
			os = cls.objects.by_version(v)
			for o in os:
				o.save()

	def delete(self):
		if self.max_versione == self.min_versione:
			models.Model.delete(self)
		else:
			self.max_versione -= 1
			models.Model.save(self)

	@classmethod
	def extend_to_current_version(cls):
		"""
		Estende la validità di tutte le istanze della versione precedente (ultima attiva) alla versione attuale

		Prima di invocare extend_to_current_version, è necessario creare una nuova versione
		"""
		ultima = cls.versione.objects.ultima().numero
		precedente = oggetto_con_max(cls.versione.objects.filter(attiva=True, numero__lt=ultima), 'numero').numero
		cls.objects.filter(max_versione__gte=precedente).update(max_versione=ultima)


# Ricerche recenti


class RicercaRecente(models.Model):
	ricerca = models.CharField(max_length=63, blank=True)
	descrizione = models.CharField(max_length=127, blank=True)
	orario = models.DateTimeField(db_index=True)
	utente_generico = models.ForeignKey(UtenteGenerico, db_index=True)
	
	def __unicode__(self):
		return self.ricerca
	
	class Meta:
		verbose_name_plural = "Ricerche recenti"
		
	@classmethod
	def get_queryset_by_request(cls, request):
		try:
			ug = UtenteGenerico.by_request(request)
		except UtenteGenerico.DoesNotExist:
			return cls.objects.none()
		return cls.objects.filter(utente_generico=ug)	
	
	@classmethod
	def by_request(cls, request, limit=True):
		rrs = cls.get_queryset_by_request(request)
		# Non cancello più le ricerche vecchie perché questa operazione è eseguita da un job
		# rrs.filter(orario__lt=datetime.now() - RICERCHE_RECENTI_MAX_AGE).delete()
		if limit:
			return rrs.order_by('-orario')[:RICERCHE_RECENTI_MAX_LENGTH]
		return rrs.order_by('-orario')
	
	@classmethod
	def update(cls, request, ricerca, descrizione):
		if request is None or "punto:" in ricerca:
			return
		n = datetime.now()
		rrs = cls.get_queryset_by_request(request).filter(ricerca=ricerca)
		if len(rrs) == 0:
			ug = UtenteGenerico.update(request)
			cls(
				ricerca=ricerca,
				descrizione=descrizione,
				orario=n,
				utente_generico=ug,
			).save()
		else:
			r = rrs[0]
			r.orario = n
			r.descrizione = descrizione
			r.save()

class RicercaErrata(models.Model):
	ricerca = models.CharField(max_length=63, db_index=True)
	orario_prima = models.DateTimeField(db_index=True, auto_now_add=True)
	conteggio = models.IntegerField(default=1, db_index=True)
	conversione = models.CharField(max_length=63, null=True, blank=True, default=None)

	def __unicode__(self):
		return "[%d] %s -> %s" % (self.conteggio, self.ricerca, self.conversione if self.conversione is not None else '')

	class Meta:
		verbose_name = u'Ricerca errata'
		verbose_name_plural = u'Ricerche errate'


# Notifiche
class RichiestaNotifica(ConFasce):
	user = models.ForeignKey(User)
	su_visita = models.BooleanField(default=False)
	modello = models.ForeignKey(contenttypes.ContentType)
	footprint = models.CharField(max_length=4095, default=None, null=True, blank=True)
	messaggio = models.CharField(max_length=1023, default='')
	scadenza = models.DateTimeField(default=datetime.now)
	validita_min = models.DateTimeField(default=datetime.now)
	nascosta = models.BooleanField(default=True)	
	
	def __init__(self, *args, **kwargs):
		kwargs['modello'] = contenttypes.ContentType.objects.get_for_model(type(self))
		models.Model.__init__(self, *args, **kwargs)
		
	def downcast(self):
		return getattr(self, self.modello.model)

	attiva = ConFasce.attivo
	
	def calcola(self):
		"""
		Metodo principale da invocare per sapere se la notifica deve essere visualizzata o no.
		
		Restituisce True sse la notifica deve essere visualizzata
		"""
		now = datetime.now()
		if self.validita_min > now:
			return not self.nascosta
		h = self.verifica_condizione() 
		if h is not None:
			self.imposta_validita_min()
			if now > self.scadenza or self.footprint == None or not self.verifica_footprint(h):
				self.nascosta = False
			self.footprint = h
			self.save()
			return not self.nascosta
		else:
			self.imposta_validita_min()
			self.nascosta = True
			self.save()
			return False
			
	def hash_object(self, object):
		return hashlib.md5(pickle.dumps(object)).hexdigest()
	
	def pickle(self, object):
		return pickle.dumps(object)
	
	def unpickle(self, string):
		return pickle.loads(string)
	
	# Membri di cui e' POSSIBILE fare overriding
	def imposta_validita_min(self):
		self.validita_min = datetime.now() + self.durata_validita_min
	
	durata_validita_min = timedelta(minutes=1)
	
	def verifica_footprint(self, nuovo):
		"""
		Verifica se il nuovo footprint rappresenta la notifica precedente
		"""
		return self.footprint == nuovo
	
	# Membri di cui è NECESSARIO fare overriding
	def verifica_condizione(self):
		"""
		Verifica la condizione di notifica
		
		Se la condizione di notifica è vera, imposta il messaggio, aggiorna la scadenza
		e restituisce il nuovo footprint
		Altrimenti restituisce None
		"""
		return None
	
	def get_url(self):
		"""
		Restituisce la URL della pagina di dettaglio relativa alla notifica
		"""
		return ''


class DisabilitatoreRichiestaNotifica(DisabililtatoreConFasce):
	con_fasce = models.ForeignKey(RichiestaNotifica, related_name='disabilitatore')
	
class FasciaRichiestaNotifica(FasciaValidita):
	con_fasce = models.ForeignKey(RichiestaNotifica, related_name='fasce')


# App

class VersioneApp(models.Model):
	versione = models.CharField(max_length=13, db_index=True)
	orario_rilascio = models.DateTimeField(db_index=True)
	orario_deprecata = models.DateTimeField(null=True, blank=True, default=None)
	beta = models.BooleanField(blank=True, default=False)
	messaggio_custom = models.CharField(max_length=2047, blank=True, null=True)
	os = models.CharField(max_length=31, blank=True, null=True, default=None)


class LogAppInit(models.Model):
	orario = models.DateTimeField(db_index=True)
	versione = models.ForeignKey(VersioneApp)
	session_key = models.CharField(max_length=40, db_index=True)
	user = models.ForeignKey(User, null=True, default=None)


# Registro processamenti

class StatoProcessamento(models.Model):
	nome = models.CharField(max_length=63, db_index=True)
	orario_inizio_esecuzione = models.DateTimeField(default=None, null=True, blank=True)
	orario_fine_esecuzione = models.DateTimeField(default=None, null=True, blank=True)
	orario_ultimo_elemento = models.DateTimeField(default=None, null=True, blank=True)
	id_ultimo_elemento = models.IntegerField(default=None, null=True, blank=True)

	def __unicode__(self):
		return self.nome

	class Meta:
		verbose_name = u'Stato processamento'
		verbose_name_plural = u'Stati processamento'


@contextmanager
def processa_prossimo_lotto(nome, queryset, field, limit=200, by_id=False):
	sp = StatoProcessamento.objects.get_or_create(nome=nome)[0]
	sp.orario_inizio_esecuzione = datetime.now()
	sp.save()
	if not by_id:
		attr = 'orario_ultimo_elemento'
	else:
		attr = 'id_ultimo_elemento'
	if getattr(sp, attr) is not None:
		lookup = "%s__gt" % field
		queryset = queryset.filter(**{lookup: getattr(sp, attr)}).order_by(field)
	else:
		queryset = queryset.all().order_by(field)
	if limit > 0:
		queryset = queryset[:limit]
	instances = list(queryset)
	yield instances
	sp.orario_fine_esecuzione = datetime.now()
	if len(instances) > 0:
		oue = getattr(instances[-1], field)
		setattr(sp, attr, oue)
	sp.save()


def processa_lotti(nome, queryset, field, limit=200, by_id=False):
	esci = False
	while not esci:
		with processa_prossimo_lotto(nome, queryset, field, limit, by_id) as els:
			if len(els) > 0:
				yield els
			if len(els) < limit:
				esci = True


def processamento_in_corso(nome, intervallo_guardia=timedelta(minutes=1)):
	sp = StatoProcessamento.objects.get_or_create(nome=nome)[0]
	if sp.orario_inizio_esecuzione is None:
		return False
	return sp.orario_inizio_esecuzione >= datetime.now() - intervallo_guardia


@contextmanager
def sospendi_servizi(queryset=None):
	"""
	Disabilita temporaneamente i servizi aventi stato 'A' durante l'esecuzione del contesto

	:param queryset: eventuale sottoinsieme dei servizi da sospendere
	"""
	if queryset is None:
		queryset = Servizio.objects.all()

	ss = list(queryset.filter(abilitato='A'))
	try:
		print("Disabling services")
		for s in ss:
			s.abilitato = '0'
			s.save()
		yield
	finally:
		print("Enabling services")
		for s in ss:
			s.abilitato = 'A'
			s.save()
