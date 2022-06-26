# Create your views here.
from carpooling.views import is_utente_carpooling
from models import *
from django.db import models, connections, transaction
from servizi.utils import dict_cursor, project, datetime2mysql, group_required
from datetime import datetime, timedelta, time, date
from jsonrpc import jsonrpc_method
from paline import tratto
from copy import copy
import rpyc
import cPickle as pickle
import views
from pprint import pprint


@jsonrpc_method('carpooling_dettaglio_offerta', safe=True)
def dettaglio_offerta(
	request,
	id,
	richiedi
):
	ctx = {}
	tr = request.session['percorso-trattoroot']
	offerta = PassaggioOfferto.objects.get(pk=id.split('-')[1])
	for t in tr.sub:
		if isinstance(t, tratto.TrattoCarPooling):
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

			if richiedi and is_utente_carpooling(request.user):
				richiesta = PassaggioRichiesto(
					user=request.user,
					offerta=offerta,
					note="",
					stato="RI",
					da_arco=da_arco,
					a_arco=a_arco,
					da_indirizzo=da_indirizzo,
					a_indirizzo=a_indirizzo,
					da_orario=da_orario,
					a_orario=a_orario,
					distanza=distanza,
					costo=costo_arrotondato(distanza),
				)
				richiesta.save()
				offerta.aggiungi_richiesta(richiesta, t.offset)

			return {
				'feedback_offerente': offerta.utente_car_pooling().feedback_complessivo_arrotondato(),
				'da_indirizzo': da_indirizzo,
				'a_indirizzo': a_indirizzo,
				'da_orario': da_orario.strftime('%H:%M'),
				'a_orario': a_orario.strftime('%H:%M'),
				'distanza': distanza,
				'costo': costo_arrotondato(distanza),
				'id_linea_esclusa': "CP%s" % offerta.pk,
				'nome_linea_esclusa': "Car pooling da %s a %s" % (da_indirizzo, a_indirizzo),
			}
