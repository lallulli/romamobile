# coding: utf-8

from models import *
import settings
from pprint import pprint
from collections import defaultdict
from jsonrpc import jsonrpc_method


@jsonrpc_method('news_tutte', safe=True)
def news_tutte(request, lingua):
	"""
	Restituisce l'elenco delle news, raggruppate per categoria

	Restituisce una lista di categorie. Ogni categoria è un dizionario con chiavi:
	* id_categoria
	* nome_categoria
	* posizione (la lista è ordinata per tale attributo)
	* news: lista di news. Ogni news è un dizionario con chiavi:
		* id_news
		* titolo
		* contenuto
	"""
	ret = []
	ns = News.objects.filter(codice_lingua=lingua).order_by('-data_pubblicazione').distinct()
	cs = {}
	for n in ns:
		for c in n.categorie.filter(codice_lingua=lingua):
			id_categoria = c.id_categoria
			if not id_categoria in cs:
				cs[c.id_categoria] = {
					'id_categoria': id_categoria,
					'nome_categoria': c.nome,
					'posizione': c.posizione,
					'news': [],
				}
			cs[id_categoria]['news'].append({
				'id_news': n.id_news,
				'titolo': n.titolo,
				'contenuto': n.contenuto,
			})

	cs = cs.values()
	cs.sort(key=lambda c: c['posizione'])

	return cs
