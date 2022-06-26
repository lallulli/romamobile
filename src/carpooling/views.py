# coding: utf-8

#
#    Copyright 2013-2016 Roma servizi per la mobilità srl
#    Developed by Luca Allulli, Damiano Morosi and Davide Valvason
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
from datetime import date, time, datetime, timedelta
from django import forms
from django.db.models import Q
from servizi.utils import BrRadioSelect, giorni_settimana, populate_form, hist_redirect	
from servizi.utils import richiedi_conferma, datetime2date, dateandtime2datetime, template_to_mail
from servizi.utils import group_required, AtacMobileForm, messaggio
from percorso.views import _validate_address, calcola_percorso_dinamico, inizializza_linee_escluse
from django.utils.translation import ugettext_lazy as _
from django.template.response import TemplateResponse
from paline.tratto import TrattoCarPooling, TrattoCarPoolingArco, TrattoCarPoolingAttesa
from percorso.views import AggiungiPuntoForm
import traceback
from paline import tratto
import settings
from django.utils.translation import ugettext as _
from django.http import HttpResponseRedirect
from django.contrib.auth.models import User, Group
from pprint import pprint

def is_utente_carpooling(user):
	try:
		return UtenteCarPooling.from_user(user).abilitato
	except:
		return False

def controllo_diritti(view_func):
	def wrap(request, *args, **kwargs):
		if is_utente_carpooling(request.user):
			return view_func(request, *args, **kwargs)
		return TemplateResponse(request, 'carpooling.html')
	return wrap


@controllo_diritti
@group_required('carpooling')
def aggiungi_punto(request):
	ctx = {}
	punti = request.session['infopoint']['punti']
	i = int(request.GET['index'])
	f = AggiungiPuntoForm(request.GET)
	cd = f.data
	a, p, em, ef, punto = _validate_address(request, cd['address'],  True)
	if len(em) > 0:
		class CorreggiAggiungiPuntoForm(AggiungiPuntoForm):
			address = a
	
		f = CorreggiAggiungiPuntoForm(request.GET)
		f.fields['address'].widget.attrs.update({'class': 'hlform'})
		
		ctx['form'] = f
		ctx['indice'] = i
		ctx['errors'] = em
	else:
		punti.insert(i, punto)
	return calcola_percorso_dinamico(request, ctx=ctx)


@controllo_diritti
def offri_passaggio_tempo(request, pk_copia=None):
	ctx = {}
	now = datetime.now()
	
	class TempoPassaggioForm(forms.Form):	
		day = forms.TypedChoiceField(widget=forms.HiddenInput())
		month = forms.TypedChoiceField(widget=forms.HiddenInput())
		y = now.year
		year = forms.TypedChoiceField(widget=forms.HiddenInput())
		hour = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(24)])
		minute = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(0, 60, 5)])
		
		hours = forms.TypedChoiceField(choices=[(i, str(i)) for i in range(2)])
		minutes = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(0, 60, 5)])
		
		flessibilita_ant = forms.TypedChoiceField(choices=[(i, str(i)) for i in range(0, 60, 5)])
		flessibilita_post = forms.TypedChoiceField(choices=[(i, str(i)) for i in range(0, 60, 5)])
		
		#self.fields['day'].widget.attrs['disabled'] = True
		
		giorno0 = forms.BooleanField(required=False)
		giorno1 = forms.BooleanField(required=False)
		giorno2 = forms.BooleanField(required=False)
		giorno3 = forms.BooleanField(required=False)
		giorno4 = forms.BooleanField(required=False)
		giorno5 = forms.BooleanField(required=False)
		giorno6 = forms.BooleanField(required=False)
		
		ripeti = forms.BooleanField(required=False)
		
	if pk_copia is None:
		infopoint = request.session['infopoint']
		punti = infopoint['punti']
		tr = request.session['percorso-trattoroot']
		stat = tratto.PercorsoStat()
		tratto.formatta_percorso(tr, 'stat', stat, {})
		
		dt = infopoint['dt']
		durata = stat.tempo_totale
		indirizzo_partenza = punti[0]['address']
		indirizzo_arrivo = punti[-1]['address']
		flessibilita_ant = 10
		flessibilita_post = 10
		ripeti = False
		
	else:
		originale = PassaggioOfferto.objects.get(user=request.user, pk=pk_copia)
		dt = originale.orario
		indirizzo_partenza = originale.indirizzo_partenza
		indirizzo_arrivo = originale.indirizzo_arrivo
		durata = originale.durata
		flessibilita_ant = originale.flessibilita / 60
		flessibilita_post = originale.flessibilita / 60
		ripeti = originale.ripeti
		
	
	ctx['indirizzo_partenza'] = indirizzo_partenza
	ctx['indirizzo_arrivo'] = indirizzo_arrivo
	durata = durata / 60
	durata_arr = int(durata / 5) * 5
	if durata_arr < durata:
		durata_arr += 5
	durata_ore = durata_arr / 60
	durata_minuti = durata_arr % 60
	#print "%02d" % dt.hour
		
			
	data0=datetime.now()
	data1=datetime.now()+timedelta(days=1)
	data2=datetime.now()+timedelta(days=2)
	data3=datetime.now()+timedelta(days=3)
	data4=datetime.now()+timedelta(days=4)
	data5=datetime.now()+timedelta(days=5)
	data6=datetime.now()+timedelta(days=6)
	lista_giorni=[data1,data2,data3,data4,data5,data6]	
					
	#print "Durata minuti", durata_minuti
	
	dtr = None
	if pk_copia is None:
		dtr = dt.date()
	
	f = populate_form(request, TempoPassaggioForm,
		day=dt.day,
		month=dt.month,
		year=dt.year,
		hour=dt.hour,
		minute=((dt.minute / 5) * 5),
		hours=durata_ore,
		minutes=durata_minuti,
		flessibilita_ant=((flessibilita_ant / 5) * 5),
		flessibilita_post=((flessibilita_post / 5) * 5),
		giorno0=data0.date()==dtr,
		giorno1=data1.date()==dtr,
		giorno2=data2.date()==dtr,
		giorno3=data3.date()==dtr,
		giorno4=data4.date()==dtr,
		giorno5=data5.date()==dtr,
		giorno6=data6.date()==dtr,
		ripeti=ripeti,
	)
	
	
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		print 'data mancante'
		print cd
		dt = datetime(int(cd['year']), int(cd['month']), int(cd['day']), int(cd['hour']), int(cd['minute']))
		flessibilita_ant = int(cd['flessibilita_ant']) * 60
		flessibilita_post = int(cd['flessibilita_post']) * 60
		flessibilita = (flessibilita_ant + flessibilita_post) / 2
		offset = (flessibilita_post - flessibilita_ant) / 2
		dt += timedelta(seconds=offset)
		durata = (int(cd['hours']) * 3600 + int(cd['minutes'])) * 60
		giorno_offset=dt-datetime.now()
		ripeti = 'ripeti' in cd
		
		giorno0 = 'giorno0' in cd
		giorno1 = 'giorno1' in cd
		giorno2 = 'giorno2' in cd
		giorno3 = 'giorno3' in cd
		giorno4 = 'giorno4' in cd
		giorno5 = 'giorno5' in cd
		giorno6 = 'giorno6' in cd
		box_gg= [
			{'box':giorno0, 'data':data0},
			{'box':giorno1, 'data':data1},
			{'box':giorno2, 'data':data2},
			{'box':giorno3, 'data':data3},
			{'box':giorno4, 'data':data4},
			{'box':giorno5, 'data':data5},
			{'box':giorno6, 'data':data6},
		]
		
		if pk_copia is None:
			percorso = PercorsoSalvato(percorso=infopoint['percorso_auto_salvato'])
			percorso.save()
		else:
			percorso = originale.percorso
			
		passaggi_creati = []
		for i in range(0,7):
			if box_gg[i]['box']:
				po = PassaggioOfferto(
					orario=datetime(box_gg[i]['data'].year,box_gg[i]['data'].month,box_gg[i]['data'].day,int(cd['hour']), int(cd['minute'])),
					user=request.user,
					indirizzo_partenza=indirizzo_partenza,
					indirizzo_arrivo=indirizzo_arrivo,
					percorso=percorso,
					durata=durata,
					flessibilita=flessibilita,
					ripeti=ripeti,
				)
				po.save()
				passaggi_creati.append(po.pk)
		
		if len(passaggi_creati) > 0:
			get_mercury().async_all('carica_percorsi_carpooling', {'pks': passaggi_creati})

		return hist_redirect(request, '/carpooling', msg=_("Offerta di passaggio salvata"))
		
	
	ctx['form'] = f
	ctx['data0']=data0
	ctx['data1']=data1
	ctx['data2']=data2
	ctx['data3']=data3
	ctx['data4']=data4
	ctx['data5']=data5
	ctx['data6']=data6

	return TemplateResponse(request, 'offri-passaggio-tempo.html', ctx)

@group_required('carpooling')
def mostra_form(request, offri=True):
	now = datetime.now()
	class PercorsoForm(forms.Form):
		start_address = forms.CharField(widget=forms.TextInput(attrs={'size':'30'}))
		stop_address = forms.CharField(widget=forms.TextInput(attrs={'size':'30'}))
		piedi = forms.TypedChoiceField(
			choices=(
				(0, _(u"Bassa (camminatore lento)")),
				(1, _(u"Media")),
				(2, _(u"Alta (camminatore veloce)")),
			),
			widget=BrRadioSelect,
			required=False,
		)
		piedi = forms.TypedChoiceField(
			choices=(
				(0, _(u"Bassa (camminatore lento)")),
				(1, _(u"Media")),
				(2, _(u"Alta (camminatore veloce)")),
			),
			widget=BrRadioSelect,
			required=False,
		)		
		day = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(1, 32)])
		month = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(1, 13)])
		y = now.year
		year = forms.TypedChoiceField(choices=[(y, str(y)[2:]), (y + 1, str(y + 1)[2:])])
		hour = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(24)])
		minute = forms.TypedChoiceField(choices=[(i, "%02d" % i) for i in range(0, 60, 5)])
		
		bici = forms.BooleanField(required=False)
		max_distanza_bici = forms.FloatField(widget=forms.TextInput(attrs={'size':'3'}), required=False)
		bus = forms.BooleanField(required=False)
		metro = forms.BooleanField(required=False)
		ferro = forms.BooleanField(required=False)
		
		def set_error(self, fields):
			for f in fields:
				self.fields[f].widget.attrs.update({'class': 'hlform'})
	
	
	error_messages = []
	error_fields = []	
	n = datetime.now()
	ctx = {}
	ctx['offri'] = offri
	request.GET = dict([(k, request.GET[k]) for k in request.GET])

	if 'Inverti' in request.GET:
		request.GET['start_address'], request.GET['stop_address'] = request.GET['stop_address'], request.GET['start_address']
	
	tomorrow = now + timedelta(days=1)	
	
	if offri:
		f = populate_form(request, PercorsoForm,
			day="%d" % tomorrow.day,
			month="%d" % tomorrow.month,
			year=str(tomorrow.year)[2:],
			hour="7",
			minute="00",
		)
	else:
		f = populate_form(request, PercorsoForm,
			day="%d" % tomorrow.day,
			month="%d" % tomorrow.month,
			year=str(tomorrow.year)[2:],
			hour="7",
			minute="00",
			piedi=1,
			bus=True,
			metro=True,
			ferro=True,
			bici=False,
			max_distanza_bici=5.0,
		)
	
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		a1, p1, em1, ef1, start = _validate_address(request, cd['start_address'],  True)
		a2, p2, em2, ef2, stop = _validate_address(request, cd['stop_address'], False)
		error_messages.extend(em1 + em2)
		error_fields.extend(ef1 + ef2)
		
		dt = datetime(int(cd['year']), int(cd['month']), int(cd['day']), int(cd['hour']), int(cd['minute']))
		
		if not offri:	
			try:
				max_distanza_bici = float(cd['max_distanza_bici']) * 1000
			except Exception:
				error_messages.append(_("distanza massima in bici (errata)"))
				error_fields.extend(['max_distanza_bici'])			

		if not (a1 is None and p1 is None and a2 is None and p2 is None):
			class CorreggiPercorsoForm(PercorsoForm):
				if a1 is not None:
					start_address = a1
				if p1 is not None:
					start_place = p1
				if a2 is not None:
					stop_address = a2
				if p2 is not None:
					stop_place = p2
	
			if not offri:
				f = populate_form(request, CorreggiPercorsoForm,
					day=cd['day'],
					month=cd['month'],
					year=cd['year'],
					hour=cd['hour'],
					minute=cd['minute'],											
					piedi=cd['piedi'],
					bus='bus' in cd,
					metro='metro' in cd,
					ferro='ferro' in cd,
					bici='bici' in cd,
					max_distanza_bici=cd['max_distanza_bici'],
				)
			else:
				f = populate_form(request, CorreggiPercorsoForm,
					day=cd['day'],
					month=cd['month'],
					year=cd['year'],
					hour=cd['hour'],
					minute=cd['minute'],
				)

		if len(error_fields) > 0:
			f.set_error(error_fields)

		else:
			# Validazione ok, inizializzo gli attributi specifici
			if not offri:
				bus = 'bus' in cd
				metro = 'metro' in cd
				ferro = 'ferro' in cd
				bici = 'bici' in cd
				piedi = int(cd['piedi'])
			else:
				bus = True
				metro = True
				ferro = True
				max_distanza_bici = 5000
				bici = False
				piedi = 1

			ucp = UtenteCarPooling.from_user(request.user)
			request.session['infopoint'] = {
				'punti': [start, stop],
				'mezzo': 0 if offri else (3 if bici else 1),
				'piedi': piedi,
				'bus': bus,
				'metro': metro,
				'ferro': ferro,
				'teletrasporto': False,
				'max_distanza_bici': max_distanza_bici,
				'carpooling': 1 if offri else 2,
				'carpooling_vincoli': get_vincoli(request.user),
				'dt': dt,
				'linee_escluse': inizializza_linee_escluse(),
				'quando': 2,
				'parcheggi_scambio': True,
				'parcheggi_autorimesse': False,
			}		
			return calcola_percorso_dinamico(request)

	ctx.update({'form': f, 'errors': error_messages})
	return TemplateResponse(request, 'percorso-cp.html', ctx)
	
@controllo_diritti
@group_required('carpooling')
def offri_passaggio(request):
	return mostra_form(request, True)

@controllo_diritti
@group_required('carpooling')
def cerca_passaggio(request):
	return mostra_form(request, False)

@controllo_diritti
@group_required('carpooling')
def ripeti(request, pk):
	return offri_passaggio_tempo(request, pk)

@controllo_diritti
@group_required('carpooling')
@richiedi_conferma(_('Confermi di voler annullare l\'offerta di passaggio?'))
def annulla(request, pk):
	ora=datetime.now()
	o = PassaggioOfferto.objects.get(user=request.user, pk=pk)
	for r in o.passaggiorichiesto_set.filter(stato__in=['RI', 'CO']):
		r.stato = 'AO'
		r.save()
		template_to_mail(r.user.email, 'annulla_richiedente.mail', {'r': r, 'user': r.user})
	o.annullato = True
	o.save()
	o.aggiorna_server()
	return hist_redirect(request, '/carpooling', msg=_(u"Offerta di passaggio annullata"))


@controllo_diritti
@group_required('carpooling')
@richiedi_conferma(_('Confermi di voler accettare la richiesta di passaggio?'))
def accetta(request, pk):
	r = PassaggioRichiesto.objects.get(offerta__user=request.user, pk=pk, stato="RI")
	r.stato="CO"
	r.scambio_dati = True
	r.save()
	template_to_mail(r.user.email, 'conferma_richiedente.mail', {'r': r, 'user': r.user})
	return hist_redirect(request, '/carpooling', msg=_(u"Offerta di passaggio accettata"))

@controllo_diritti
@group_required('carpooling')
@richiedi_conferma(_('Confermi di voler rifiutare la richiesta di passaggio?'))
def rifiuta(request, pk):
	r = PassaggioRichiesto.objects.get(offerta__user=request.user, pk=pk, stato__in=["RI", "CO"])
	r.stato="AO"
	r.save()
	r.offerta.rimuovi_richiesta(r)
	template_to_mail(r.user.email, 'annulla_richiedente.mail', {'r': r, 'user': r.user})
	return hist_redirect(request, '/carpooling', msg=_(u"Offerta di passaggio rifiutata"))

@controllo_diritti
@group_required('carpooling')
@richiedi_conferma(_('Confermi di voler annullare la richiesta di passaggio?'))
def annulla_richiesta(request, pk):
	ora=datetime.now()
	r = PassaggioRichiesto.objects.get(user=request.user, pk=pk, stato__in=["RI", "CO"])
	r.stato="AR"
	r.save()
	r.offerta.rimuovi_richiesta(r)
	template_to_mail(r.offerta.user.email, 'annulla_offerente.mail', {'r': r, 'user': r.offerta.user})
	return hist_redirect(request, '/carpooling', msg=_(u"Richiesta di passaggio annullata"))


@controllo_diritti
@group_required('carpooling')
def dettaglio_offerta(request, pk):
	ctx = {}
	o = PassaggioOfferto.objects.get(pk=pk, user=request.user)
	ctx['offerta'] = o
	ctx['pendenti'] = o.passaggiorichiesto_set.filter(stato='RI')
	ctx['confermate'] = o.passaggiorichiesto_set.filter(stato='CO')
	ctx['rifiutate'] = o.passaggiorichiesto_set.filter(stato__in=['AR', 'AO'])
	return TemplateResponse(request, 'offerta.html', ctx)

@controllo_diritti
@group_required('carpooling')
def dettaglio_richiesta(request, pk):
	ctx = {}
	c = PassaggioRichiesto.objects.get(pk=pk, user=request.user)
	ctx['richiesta'] = c
	return TemplateResponse(request, 'richiesta.html', ctx)

@controllo_diritti
@group_required('carpooling')
def richiedi(request, id):
	ctx = {}
	tr = request.session['percorso-trattoroot']
	offerta = PassaggioOfferto.objects.get(pk=id.split('-')[1])
	for t in tr.sub:
		if isinstance(t, TrattoCarPooling):
			sub = [s for s in t.sub if isinstance(s, tratto.TrattoCarPoolingArco)]
			"""
			if sub[0].id_arco == id[2:]:
				print "Tratto car pooling:", t
			"""
			nomi_archi = []
			nome_corr = None
			for s in sub:
				if s.nome_arco != "" and s.nome_arco != nome_corr:
					nomi_archi.append(s.nome_arco)
					nome_corr = s.nome_arco
			da_indirizzo = ""
			a_indirizzo = ""
			if len(nomi_archi) > 0:
				da_indirizzo = nomi_archi[0]
				a_indirizzo = nomi_archi[-1]
				
			"""
			for s in sub:
				print s.tempo
			"""
			
			da_orario = sub[0].tempo
			a_orario = sub[-1].tempo + timedelta(seconds=sub[-1].get_tempo_totale())
			da_arco = sub[0].id_arco.split("-")[-1]
			a_arco = sub[-1].id_arco.split("-")[-1]
			
			distanza = t.get_distanza()
			
			richiesta = PassaggioRichiesto(
				user=request.user,
				offerta=offerta,
				note="",
				stato="-",
				da_arco=da_arco,
				a_arco=a_arco,
				da_indirizzo=da_indirizzo,
				a_indirizzo=a_indirizzo,
				da_orario=da_orario,
				a_orario=a_orario,
				distanza=distanza,
				costo=costo_arrotondato(distanza),
			)
			ctx['richiesta'] = richiesta
			ctx['richiedente'] = True
						
			if not 'conferma' in request.GET:
				return TemplateResponse(request, 'richiesta.html', ctx)
			else:
				richiesta.stato="RI"
				richiesta.save()
				offerta.aggiungi_richiesta(richiesta, t.offset)
				# todo: logga
				template_to_mail(offerta.user.email, 'richiesta_offerente.mail', {'r': richiesta, 'user': offerta.user})
				return hist_redirect(request, '/carpooling', msg=_("Richiesta di passaggio inviata"))




@controllo_diritti
@group_required('carpooling')
def escludi(request, id):
	ctx = {}
	tr = request.session['percorso-trattoroot']
	infopoint = request.session['infopoint']
	
	offerta = PassaggioOfferto.objects.get(pk=id.split('-')[1])
	for t in tr.sub:
		if isinstance(t, TrattoCarPooling):
			sub = [s for s in t.sub if isinstance(s, tratto.TrattoCarPoolingArco)]
			nomi_archi = []
			nome_corr = None
			for s in sub:
				if s.nome_arco != "" and s.nome_arco != nome_corr:
					nomi_archi.append(s.nome_arco)
					nome_corr = s.nome_arco
			da_indirizzo = ""
			a_indirizzo = ""
			if len(nomi_archi) > 0:
				da_indirizzo = nomi_archi[0]
				a_indirizzo = nomi_archi[-1]
				
			
			da_orario = sub[0].tempo
			a_orario = sub[-1].tempo + timedelta(seconds=sub[-1].get_tempo_totale())
			da_arco = sub[0].id_arco.split("-")[-1]
			a_arco = sub[-1].id_arco.split("-")[-1]
			infopoint['linee_escluse']["CP%s" % offerta.pk] = "Car pooling da %s a %s" % (da_indirizzo, a_indirizzo)
			
	return calcola_percorso_dinamico(request)
			
class AbilitaForm(AtacMobileForm):
	username = forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))
	
class AbilitaManagerForm(AtacMobileForm):
	username = forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))
	organizzazione= forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))

@group_required('carpooling_manager')
def abilita(request, pk):
	ctx = {}
	mm = UtenteCarPooling.from_user(request.user)
	u = UtenteCarPooling.objects.get(pk=pk, organizzazione=mm.organizzazione)
	u.abilitato=True
	u.save()
	return hist_redirect(request, '/carpooling/gestione_utenti', msg=_("Utente abilitato"))
		
	return TemplateResponse(request, 'abilita.html', ctx)

@group_required('carpooling_manager')	
@richiedi_conferma(_('Confermi di voler disabilitare l\'utente?'))
def disabilita(request,  pk):
	ora=datetime.now()
	#toglie abilitazione a pagina carpooling
	ctx = {}
	mm = UtenteCarPooling.from_user(request.user)
	u = UtenteCarPooling.objects.get(pk=pk, organizzazione=mm.organizzazione)
	u.abilitato=False
	u.save()
	#annulla tutte le offerte
	pof = PassaggioOfferto.objects.filter(user=u.user, orario__gt=ora)
	for p in pof:
		for r in p.passaggiorichiesto_set.filter(stato__in=['RI', 'CO']):
			r.stato = 'AO'
			r.save()
			template_to_mail(r.user.email, 'annulla_richiedente.mail', {'r': r, 'user': r.user})
		p.annullato = True
		p.save()
		p.aggiorna_server()
	#annulla tutte le richieste
	pri = PassaggioRichiesto.objects.filter(user=u.user, stato__in=["RI", "CO"],  a_orario__lt=ora)
	for pr in pri:
		pr.stato="AR"
		pr.save()
		pr.offerta.rimuovi_richiesta(pr)
		template_to_mail(pr.offerta.user.email, 'annulla_offerente.mail', {'pr': pr, 'user': pr.offerta.user})
	return hist_redirect(request, '/carpooling/gestione_utenti', msg=_("Utente disabilitato"))
	

class TelefonoForm(AtacMobileForm):
	numero = forms.CharField(widget=forms.TextInput(attrs={'size':'24'}))
	sesso = forms.TypedChoiceField(choices=SESSO_CHOICES)
	fumatore = forms.BooleanField()
	solo_non_fumatori = forms.BooleanField()
	solo_stesso_sesso = forms.BooleanField()


@controllo_diritti
@group_required('carpooling')
def telefono(request):
	ctx = {}
	ctx['user'] = request.user

	utente_cp = UtenteCarPooling.from_user(request.user)
	tel = Telefono.objects.filter(user=request.user)
	if len(tel) == 0:
		num = ''
	else:
		num = tel[0].numero


	f = populate_form(request, TelefonoForm,
		numero=num,
		sesso=utente_cp.sesso,
		fumatore=utente_cp.fumatore,
		solo_non_fumatori=utente_cp.solo_non_fumatori,
		solo_stesso_sesso=utente_cp.solo_stesso_sesso,
	)
	ctx['form'] = f
	
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		num = cd['numero'].strip()
		if num != '':
			tel.delete()
			Telefono(user=request.user, numero=num).save()
			utente_cp.sesso = cd['sesso']
			utente_cp.fumatore = 'fumatore' in cd
			utente_cp.solo_non_fumatori = 'solo_non_fumatori' in cd
			utente_cp.solo_stesso_sesso = 'solo_stesso_sesso' in cd
			utente_cp.preferenze_impostate = True
			utente_cp.save()
			return hist_redirect(request, '/carpooling', msg=_("Numero di telefono impostato"))
		ctx['error'] = True
	return TemplateResponse(request, 'telefono.html', ctx)
	
@group_required('carpooling')
def default(request):
	ctx = {}
	ctx['user'] = request.user
	ctx['carpooling_manager'] = len(request.user.groups.filter(name='carpooling_manager')) > 0	
	utente_cp = UtenteCarPooling.from_user(request.user)
	if not utente_cp.preferenze_impostate:
		return HttpResponseRedirect('/carpooling/telefono')
	now = datetime.now()
	ctx['richieste_feedback_pendente'] = PassaggioRichiesto.objects.filter(user=request.user, da_orario__lt=now, stato='CO', feedback_offerente=None).order_by('-da_orario')
	ctx['offerte_feedback_pendente'] = PassaggioRichiesto.objects.filter(offerta__user=request.user, da_orario__lt=now, stato='CO', feedback_richiedente=None).order_by('-da_orario')
	ctx['passaggi_richiesti'] = PassaggioOfferto.objects.filter(user=request.user, passaggiorichiesto__stato="RI", orario__gte=now)
	ctx['passaggi_futuri'] = PassaggioOfferto.objects.filter(user=request.user, orario__gte=now, annullato=0).order_by('orario')
	ctx['passaggi_passati'] = PassaggioOfferto.objects.filter(user=request.user).filter(Q(annullato=1) | Q(orario__lt=now)).order_by('-orario')
	ctx['richieste_future'] = PassaggioRichiesto.objects.filter(user=request.user, da_orario__gte=now, stato__in=['RI', 'CO']).order_by('da_orario')
	ctx['richieste_passate'] = PassaggioRichiesto.objects.filter(user=request.user).filter(Q(da_orario__lt=now) | Q(stato__in=['AR', 'AO'])).order_by('-da_orario')	
	ctx['abilitato'] = UtenteCarPooling.from_user(request.user).abilitato
	return TemplateResponse(request, 'carpooling.html', ctx)
	
@controllo_diritti
@group_required('carpooling')
def feedback_richiedente(request, ricpk, feedback):
	try:
		r = PassaggioRichiesto.objects.get(pk=ricpk, offerta__user=request.user)
		r.imposta_feedback_richiedente(feedback)
		return hist_redirect(request, '/carpooling/dettaglio_offerta/%s' % r.offerta.pk, msg="Grazie per il tuo feedback")
	except Exception, e:
		return messaggio(request, "Hai già lasciato il feedback per questo passaggio. Grazie.")
	
@controllo_diritti
@group_required('carpooling')
def feedback_offerente(request, ricpk, feedback):
	try:
		r = PassaggioRichiesto.objects.get(pk=ricpk, user=request.user)
		r.imposta_feedback_offerente(feedback)
		return hist_redirect(request, '/carpooling', msg="Grazie per il tuo feedback")
	except Exception, e:
		return messaggio(request, "Hai già lasciato il feedback per questo passaggio. Grazie.")

@group_required('operatori')
def abilitamanager(request):

	ctx = {}
	
	f = populate_form(request, AbilitaManagerForm,
		username='', organizzazione='',
	)
	ctx['form'] = f
	
	if f.is_bound and 'Submit' in request.GET:
		cd = f.data
		username = cd['username'].strip()
		organizzazione= cd['organizzazione'].strip()
		try:
			u = User.objects.get(username=username)
			u.groups.add(Group.objects.get(name='carpooling_manager'))
			u.groups.add(Group.objects.get(name='carpooling'))
			u.save()
			if len(UtenteCarPooling.objects.filter(user=u)) == 0:
				ucp = UtenteCarPooling(
					user=u,
					#organizzazione=UtenteCarPooling.from_user(request.user).organizzazione,
					organizzazione=OrganizzazioneCarPooling.objects.get_or_create(nome=organizzazione)[0],
				)
				ucp.save()
			return hist_redirect(request, '/carpooling', msg=_("Utente abilitato con diritti manager"))
		except:
			ctx['error'] = True	
	return TemplateResponse(request, 'abilitamanager.html', ctx)
	
#interfaccia di gestione mobiliti manager

@group_required('carpooling_manager')
def gestione_utenti(request):
	ctx ={}
	ctx['organizzazione'] = UtenteCarPooling.from_user(request.user).organizzazione
	org = UtenteCarPooling.from_user(request.user).organizzazione
	listautenti = org.utentecarpooling_set.exclude(user__groups__name='carpooling_manager').order_by('user__last_name')
	listamanager = org.utentecarpooling_set.filter(user__groups__name='carpooling_manager').order_by('user__last_name')
	if len(listautenti)==0:
		return messaggio(request, 'nessun utente registrato per questa organizzazione')
	ctx['listautenti'] = listautenti
	ctx['listamanager'] = listamanager
	return TemplateResponse(request, 'gestione_utente.html', ctx)
	
	
def login_carpooling(request, pk):
	request.session['carpooling_login_pk'] = pk
	return HttpResponseRedirect('/servizi/login?IdSubSito=2')

def login_carpooling_landing(request):
	o = OrganizzazioneCarPooling.objects.get(pk=request.session['carpooling_login_pk'])
	verifica_abilitazione_utente(request.user, o)
	return HttpResponseRedirect('/carpooling')
