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
from django.db.models import Avg, Sum
from django.contrib.auth.models import User, Group
from django.template.defaultfilters import date as datefilter
from datetime import date, time, datetime, timedelta
import cPickle as pickle
import base64
from django.utils.translation import ugettext as _
from autenticazione.models import Telefono
from mercury.models import Mercury
import cPickle as pickle
import rpyc
import settings
from constance import config
from servizi.utils import template_to_mail, group_by
import math

CARPOOLING_DAYS = 7

mercury = [None]

"""
	Gruppi richiesti:
		carpooling
		carpooling_manager
"""

def get_mercury():
	if mercury[0] is None:
		mercury[0] = Mercury(settings.MERCURY_WEB, None)
	return mercury[0]

class PercorsoAutoSalvato(object):
	def __init__(self, grafo=None, max_posti=3):
		object.__init__(self)
		self.archi = []
		self.max_posti = max_posti
		self.grafo = grafo
		
	def serialize(self):
		return {
			'archi': self.archi,
			'max_posti': self.max_posti
		}
		
	def deserialize(self, el):
		self.archi = el['archi']
		self.max_posti = el['max_posti']
		
	def add_arco(self, t, eid, sid, tid, tp, posti=None):
		if posti is None:
			posti = self.max_posti
		self.archi.append({
			't': t, 
			'eid': eid,
			'sid': sid,
			'tid': tid,
			'tp': tp,
			'p': posti,
		})
		
	def offset_posti(self, da_arco, a_arco, offset):
		for i in range(int(da_arco), int(a_arco) + 1):
			self.archi[i]['p'] += offset
		return self.archi[int(da_arco)]['t']

class PercorsoSalvato(models.Model):
	_percorso = models.TextField(blank=True, db_column='percorso')
	
	def set_percorso(self, data):
		self._percorso = base64.encodestring(pickle.dumps(data))
	
	def get_percorso(self):
		return pickle.loads(base64.decodestring(self._percorso))
	percorso = property(get_percorso, set_percorso)

class PassaggioOfferto(models.Model):
	orario = models.DateTimeField(db_index=True)
	user = models.ForeignKey(User)
	indirizzo_partenza = models.CharField(max_length=127, blank=True, null=True)
	indirizzo_arrivo = models.CharField(max_length=127, blank=True, null=True)
	note = models.CharField(max_length=1023, blank=True, null=True)
	percorso = models.ForeignKey(PercorsoSalvato)
	durata = models.IntegerField() # secondi
	flessibilita = models.IntegerField() # secondi, semidurata dell'intervallo centrato in orario
	orario_definito = models.DateTimeField(null=True, default=None) # Definito se l'orario è fissato da una richiesta di passaggio
	annullato = models.BooleanField(blank=True, default=False, db_index=True)
	ripeti = models.BooleanField(blank=True, default=False, db_index=True)
	
	class Meta:
		verbose_name_plural = 'Passaggi offerti'	
	
	"""def annulla_offerta(self, off=None):
		if off is None:
			for r in self.passaggiorichiesto_set.filter(stato__in=['RI', 'CO']):		#annullare solo quelli futuri!
				r.stato = 'AO'
				r.save()
				template_to_mail(r.user.email, 'annulla_richiedente.mail', {'r': r, 'user': r.user})
		else:
			off.stato = 'AO'
			off.save()
			template_to_mail(r.user.email, 'annulla_richiedente.mail', {'off': off, 'user': off.user})
		self.annullato = True
		self.save()
		self.aggiorna_server()
		
	"""
	
	def sintesi(self):
		richieste = self.passaggiorichiesto_set.filter(stato__in=['RI', 'CO'])
		n = ''
		if len(richieste) > 0:
			n = ' (%d)' % len(richieste)
		return "%s da %s a %s%s" % (self.orario.strftime("%d/%m/%Y"), self.indirizzo_partenza, self.indirizzo_arrivo, n)
	
	def sintesi_futuro(self):
		richieste = self.passaggiorichiesto_set.filter(stato__in=['RI', 'CO'])
		n = ''
		if len(richieste) > 0:
			n = ' (%d)' % len(richieste)
		return "%s da %s a %s%s" % (datefilter(self.orario, "D j F").capitalize(), self.indirizzo_partenza, self.indirizzo_arrivo, n)
	
	def __unicode__(self):
		return self.sintesi()
	
	def fascia_partenza(self):
		if self.orario_definito:
			return datefilter(self.orario_definito, _('d/m/y H:i'))
		elif self.flessibilita == 0:
			return datefilter(self.orario, _('d/m/y H:i'))
		else:
			t1 = self.orario - timedelta(seconds=self.flessibilita)
			t2 = self.orario + timedelta(seconds=self.flessibilita)
			return _("%(data)s tra le %(t1)s e le %(t2)s") % {
				'data': datefilter(t1, _('d/m/y')),
				't1': datefilter(t1, _('H:i')),
				't2': datefilter(t2, _('H:i')),
			}
			
	def durata_minuti(self):
		return int(self.durata / 60)
	
	def telefoni(self):
		return ", ".join([x.numero for x in Telefono.objects.filter(user=self.user)])
	
	def numero_richieste_attive(self):
		return self.passaggiorichiesto_set.filter(stato__in=['RI', 'CO']).count()
	
	def aggiungi_richiesta(self, richiesta, offset):
		"""
		Aggiorna il modello e il calcola percorso per tener conto della nuova richiesta.
		
		La richiesta deve essere già stata salvata, con stato 'RI'.
		"""
		pas = PercorsoAutoSalvato()
		pas.deserialize(self.percorso.percorso)
		t = pas.offset_posti(richiesta.da_arco, richiesta.a_arco, -1)
		self.percorso.percorso = pas.serialize()
		self.percorso.save()
		if self.orario_definito is None:
			self.orario_definito = self.orario + offset
		self.save()
		self.aggiorna_server()
	
	def rimuovi_richiesta(self, richiesta):
		"""
		Aggiorna il modello e il calcola percorso per tener conto del fatto che la nuova richiesta è stata annullata.
		
		La richiesta deve avere già uno stato annullato.
		"""		
		pas = PercorsoAutoSalvato()
		pas.deserialize(self.percorso.percorso)
		pas.offset_posti(richiesta.da_arco, richiesta.a_arco, 1)
		self.percorso.percorso = pas.serialize()
		self.percorso.save() 
		if self.numero_richieste_attive() == 0:
			self.orario_definito = None
		self.save()
		self.aggiorna_server()
	
	def aggiorna_server(self):
		get_mercury().async_all('carica_percorso_carpooling', {'pk': self.pk})
		
	def futura(self):
		return datetime.now() < self.orario
	
	def utente_car_pooling(self):
		return UtenteCarPooling.from_user(self.user)
	
	@classmethod
	def ripeti_offerte(cls, orario_spartiacque):
		"""
		Ripete le offerte ricorrenti.
		
		Considera tutte le offerte programmate nella settimana che termina con l'orario spartiacque,
		e le ripete per la settimana successiva se sono ricorrenti (ripeti = True).
		Invia un'email di riepilogo agli utenti
		"""
		medio = orario_spartiacque
		inizio = medio - timedelta(days=7)
		pos = PassaggioOfferto.objects.filter(ripeti=True, orario__gte=inizio, orario__lte=medio, annullato=False).order_by('user')
		pous = group_by(pos, func=lambda x: x.user)
		pks = []
		for pou in pous:
			user = pou[0].user
			pcs = []
			for p in pou:
				pc = PassaggioOfferto(
					user=user,
					orario=p.orario + timedelta(days=7),
					indirizzo_partenza = p.indirizzo_partenza,
					indirizzo_arrivo = p.indirizzo_arrivo,
					percorso = p.percorso,
					durata = p.durata,
					flessibilita = p.flessibilita,
					orario_definito = p.orario_definito,
					ripeti = True,					
				)
				pc.save()
				pks.append(pc.pk)
				pcs.append(pc)
			template_to_mail(user.email, 'ripeti_offerte.mail', {'pcs': pcs, 'user': user})
		get_mercury().async_all('carica_percorsi_carpooling', {'pks': pks})
				

STATO_CHOICES = [
	('RI', 'Richiesto'),
	('CO', 'Confermato'),
	('AR', 'Annullato dal richiedente'),
	('AO', 'Annullato dall\'offerente'),
]

class PassaggioRichiesto(models.Model):
	user = models.ForeignKey(User)
	offerta = models.ForeignKey(PassaggioOfferto)
	note = models.CharField(max_length=1023, blank=True, null=True)
	stato = models.CharField(max_length=2, choices=STATO_CHOICES, db_index=True)
	scambio_dati = models.BooleanField(default=False) # True iff è avvenuto lo scambio del numero di telefono
	da_arco = models.IntegerField()
	a_arco = models.IntegerField()
	da_indirizzo = models.CharField(max_length=63)
	a_indirizzo = models.CharField(max_length=63)
	da_orario = models.DateTimeField()
	a_orario = models.DateTimeField()
	distanza = models.FloatField()
	costo = models.FloatField()
	feedback_richiedente = models.IntegerField(blank=True, null=True, default=None)
	feedback_offerente = models.IntegerField(blank=True, null=True, default=None)
	
	
	class Meta:
		verbose_name_plural = 'Passaggi richiesti'		
	
	def utente_car_pooling(self):
		return UtenteCarPooling.from_user(self.user)	

	def imposta_feedback_richiedente(self, feedback):
		feedback = int(feedback)
		if self.feedback_richiedente is None and (1 <= feedback <= 5):
			self.feedback_richiedente = feedback
			self.save()
			UtenteCarPooling.from_user(self.user).aggiorna_feedback_richiedente(feedback)
		else:
			raise Exception("Precondizioni feedback non rispettate")
			
	def imposta_feedback_offerente(self, feedback):
		feedback = int(feedback)
		if self.feedback_offerente is None and (1 <= feedback <= 5):
			self.feedback_offerente = feedback
			self.save()
			UtenteCarPooling.from_user(self.offerta.user).aggiorna_feedback_offerente(feedback)
		else:
			raise Exception("Precondizioni feedback non rispettate")
			
	
	def telefoni(self):
		return ", ".join([x.numero for x in Telefono.objects.filter(user=self.user)])
		
	
	
	def sintesi(self):
		confermato = ' (1)' if self.stato == 'CO' else ''
		return "%s da %s a %s%s" % (self.da_orario.strftime("%d/%m/%Y"), self.da_indirizzo, self.a_indirizzo, confermato)
	
	def sintesi_futuro(self):
		confermato = ' (1)' if self.stato == 'CO' else ''
		return "%s da %s a %s%s" % (datefilter(self.da_orario, "D j F").capitalize(), self.da_indirizzo, self.a_indirizzo, confermato)
	
	def __unicode__(self):
		return self.sintesi()
	
	def futura(self):
		return datetime.now() < self.da_orario
		
	"""def annulla_richiesta(self, ric=None):
		if r is None:
			for r in self.passaggiorichiesto_set.filter(stato__in=['RI', 'CO']):
				r.stato = 'AO'
				r.save()
				r.offerta.rimuovi_richiesta(r)
				template_to_mail(r.user.email, 'annulla_richiedente.mail', {'r': r, 'user': r.user})
		else:
			ric.stato = 'AO'
			ric.save()
			ric.offerta.rimuovi_richiesta(ric)
			template_to_mail(ric.user.email, 'annulla_richiedente.mail', {'ric': ric, 'user': ric.user})
		self.annullato = True
		self.save()
		self.aggiorna_server()
"""
	
class PassaggioRichiestoLog(models.Model):
	richiesta = models.ForeignKey(PassaggioRichiesto)
	nuovo_stato = models.CharField(max_length=2, choices=STATO_CHOICES)
	messaggio = models.TextField()

class OrganizzazioneCarPooling(models.Model):
	nome = models.CharField(max_length=63)
	dominio = models.CharField(max_length=100)

	def __unicode__(self):
		return self.nome
	
	class Meta:
		verbose_name_plural = 'Organizzazioni Car Pooling'


class DominioOrganizzazione(models.Model):
	dominio = models.CharField(max_length=100, db_index=True)
	organizzazione = models.ForeignKey(OrganizzazioneCarPooling)
	
	def __unicode__(self):
		return self.dominio

SESSO_CHOICES = [
	('M', 'Uomo'),
	('F', 'Donna'),
]

class UtenteCarPooling(models.Model):
	user = models.ForeignKey(User)
	organizzazione = models.ForeignKey(OrganizzazioneCarPooling, blank=True, null=True)
	feedback_richiedente_total = models.IntegerField(default=0)
	feedback_richiedente_count = models.IntegerField(default=0)
	feedback_offerente_total = models.IntegerField(default=0)
	feedback_offerente_count = models.IntegerField(default=0)
	sesso = models.CharField(choices=SESSO_CHOICES, max_length=1)
	solo_stesso_sesso = models.BooleanField(default=False)
	solo_utenti_aziendali = models.BooleanField(default=False)
	fumatore = models.BooleanField(default=False)
	solo_non_fumatori = models.BooleanField(default=True)
	preferenze_impostate = models.BooleanField(default=False)
	abilitato=models.BooleanField(default=True)
	
	class Meta:
		verbose_name_plural = 'Utenti Car Pooling'	

	def feedback_richiedente(self):
		cnt = self.feedback_richiedente_count
		if cnt > 0:
			return self.feedback_richiedente_total / cnt
		return None

	def feedback_offerente(self):
		cnt = self.feedback_offerente_count
		if cnt > 0:
			return self.feedback_offerente_total / cnt
		return None

	def feedback_complessivo(self):
		cnt = self.feedback_richiedente_count + self.feedback_offerente_count
		if cnt > 0:
			return (self.feedback_richiedente_total + self.feedback_offerente_total) / float(cnt)
		return None
	
	def feedback_complessivo_arrotondato(self):
		f = self.feedback_complessivo()
		if f is None:
			return '-'
		return "%.1f" % f
	
	def feedback_offerente_arrotondato(self):
		f = self.feedback_offerente()
		if f is None:
			return '-'
		return "%.1f" % f
	
	def feedback_richiedente_arrotondato(self):
		f = self.feedback_richiedente()
		if f is None:
			return '-'
		return "%.1f" % f

	def aggiorna_feedback_richiedente(self, feedback):
		self.feedback_richiedente_total += feedback
		self.feedback_richiedente_count += 1
		self.save()

	def aggiorna_feedback_offerente(self, feedback):
		self.feedback_offerente_total += feedback
		self.feedback_offerente_count += 1
		self.save()

	def ricalcola_feedback_richiedente(self):
		passaggi = self.user.passaggiorichiesto_set.filter(feedback_richiedente__isnull=False)
		self.feedback_richiedente_count = passaggi.count()
		self.feedback_richiedente_total = passaggi.aggregate(Sum)

	def ricalcola_feedback_offerente(self):
		passaggi = self.user.passaggiorichiesto_set.filter(feedback_richiedente__isnull=False)
		self.feedback_offerente_count = passaggi.count()
		self.feedback_offerente_total = passaggi.aggregate(Sum)
	
	def carpoolED(self):
		p= PassaggioRichiesto.objects.filter(offerta__user=self.user, stato='CO').count()
		return p
	
	def stats(self):
		""""0:richiesti 1:offerti 2:accettati
		#nomi_stat=['Passaggi Richiesti', 'Passaggi Offerti', 'Richiesti annullati', 'Offerti Annullati']"""
		statistiche=[]
		statistiche.append(self.user.passaggiorichiesto_set.count())
		statistiche.append(self.user.passaggiorichiesto_set.filter(stato__in=['AR']).count())
		statistiche.append(self.user.passaggioofferto_set.count())
		statistiche.append(self.user.passaggioofferto_set.filter(annullato=True).count())
		statistiche.append(self.carpoolED)
		statistiche.append(self.feedback_offerente_arrotondato)
		statistiche.append(self.feedback_richiedente_arrotondato)
		statistiche.append(self.feedback_complessivo_arrotondato)
		return statistiche

	@classmethod
	def from_user(cls, user):
		return cls.objects.get(user=user)

	def __unicode__(self):
		return "%s (%s/5.0)" % (unicode(self.user), self.feedback_complessivo_arrotondato())

def costo_arrotondato(distanza):
	c = (distanza * config.CARPOOLING_COSTO_CHILOMETRICO) / (1000.0 * 2.0)
	return math.ceil(c / 0.5) * 0.5
	
	
def verifica_abilitazione_utente(u, org=None):
	if len(UtenteCarPooling.objects.filter(user=u)) == 0:
		if org is None:
			s = u.email.split('@')
			if len(s) == 2:
				os = DominioOrganizzazione.objects.filter(dominio=s[1])
				if len(os) > 0:
					org = os[0].organizzazione
		if True: # org is not None:
			ucp = UtenteCarPooling(
				user=u,
				organizzazione=org,
			)
			ucp.save()
			g = Group.objects.get(name='carpooling') 
			g.user_set.add(u)

def migra_organizzazioni():
	nomi = OrganizzazioneCarPooling.objects.values('nome')
	for el in nomi:
		n = el['nome']
		os = OrganizzazioneCarPooling.objects.filter(nome=n)
		o1 = os[0]
		DominioOrganizzazione(dominio=o1.dominio, organizzazione=o1).save()
		if len(os) > 1:
			for i in range(1, len(os)):
				o2 = os[i]
				DominioOrganizzazione(dominio=o2.dominio, organizzazione=o1).save()
				UtenteCarPooling.objects.filter(organizzazione=o2).update(organizzazione=o1)
				o2.delete()

def get_vincoli(user):
	if user.is_authenticated():
		ucp = UtenteCarPooling.from_user(user)
		vincoli = {
			'fumatore': ucp.fumatore,
			'sesso': ucp.sesso,
			'pk_utente': user.pk,
			'solo_stesso_sesso': ucp.solo_stesso_sesso,
			'solo_non_fumatori': ucp.solo_non_fumatori,
		}
	else:
		vincoli = {
			'fumatore': False,
			'sesso': '-',
			'pk_utente': -1,
			'solo_stesso_sesso': False,
			'solo_non_fumatori': False,
		}
	return vincoli