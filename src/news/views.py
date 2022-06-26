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

from news.models import *
from log_servizi.models import ServerVersione, Versione
import errors
from servizi.utils import oggetto_con_max, oggetto_con_min
from django.template.response import TemplateResponse
from django.utils.translation import ugettext as _

news2 = ServerVersione("news", 2)

@news2.metodo("Categorie")
def Categorie(request, token, lingua):
	categorie = Categoria.objects.filter(codice_lingua=lingua)
	ret = []
	for c in categorie:
		ret.append({
					'id_categoria': c.id_categoria, 
					'nome': c.nome,
					'conteggio': News.objects.filter(categorie=c.id_categoria).count()
					})
	
	return ret

@news2.metodo("PrimaPagina")
def PrimaPagina(request, token, lingua):
	ret = []
	news_pp = News.objects.filter(primo_piano=True, codice_lingua=lingua).order_by('-data_pubblicazione')
	for n in news_pp:
		ret.append({
					'id_news': n.id_news,
					'id_categoria': n.categorie.values()[0]['id_categoria'],
					'titolo': n.titolo,
					'contenuto': n.contenuto,
					'data_pubblicazione': n.data_pubblicazione,
					})
	
	return ret

@news2.metodo("CategorieNews")
def CategorieNews(request, token, lingua, id_news):
	ret = []
	try:
		n = News.objects.get(pk=id_news, codice_lingua=lingua)
	except:
		raise errors.XMLRPC['XRE_NO_NEWS']
	cs = n.categorie.all().filter(codice_lingua=lingua)
	for c in cs:
		ret.append({
					'id_categoria': c.id_categoria,
					'nome_categoria': c.nome,
					})
	
	return ret

@news2.metodo("PerCategoria")
def PerCategoria(request, token, lingua, id_categoria):
	ret = []
	try:
		c = Categoria.objects.get(pk=id_categoria, codice_lingua=lingua)
	except:
		return ret
	
	ns = News.objects.filter(categorie=c, codice_lingua=lingua).order_by('-data_pubblicazione')
	for n in ns:
		ret.append({
					'id_news': n.id_news,
					'id_categoria': id_categoria,
					'titolo': n.titolo,
					'contenuto': n.contenuto,
					'data_pubblicazione': n.data_pubblicazione,
					})
	return ret

@news2.metodo("Singola")
def Singola(request, token, lingua, id_news, id_categoria):
	ret = []
	try:
		c = Categoria.objects.get(pk=id_categoria, codice_lingua=lingua)
	except:
		return ret
	
	try:
		n = News.objects.get(pk=id_news, codice_lingua=lingua, categorie=c)
	except:
		errors.XMLRPC['XRE_NO_NEWS']
	
	try:
		n_succ = oggetto_con_max(News.objects.filter(data_pubblicazione__lt=n.data_pubblicazione, codice_lingua=lingua, categorie=c), 'data_pubblicazione').id_news
	except Exception as e:
		n_succ = ''
	try:
		n_prec = oggetto_con_min(News.objects.filter(data_pubblicazione__gt=n.data_pubblicazione, codice_lingua=lingua, categorie=c), 'data_pubblicazione').id_news
	except Exception as e:
		n_prec = ''
				
	ret.append({
				'id_news': n.id_news,
				'id_categoria': id_categoria,
				'titolo': n.titolo,
				'contenuto': n.contenuto,
				'data_pubblicazione': n.data_pubblicazione,
				'prec': n_prec,
				'succ': n_succ,
				})
	
	return ret

@news2.metodo("Tutte")
def Tutte(request, token, lingua):
	ret = []
	ns = News.objects.filter(codice_lingua=lingua).order_by('categorie__id_categoria', '-data_pubblicazione').distinct()
	
	for n in ns:
		ret.append({
					'id_news': n.id_news,
					'id_categoria': n.categorie.values()[0]['id_categoria'],
					'titolo': n.titolo,
					'contenuto': n.contenuto,
					'data_pubblicazione': n.data_pubblicazione,					
					})
		
	return ret

def default(request, categoria_selezionata=None):
	ctx = {}
	cs = Categoria.objects.filter(codice_lingua=request.lingua.codice).order_by('pk')
	ctx['categoria_selezionata'] = int(categoria_selezionata) if categoria_selezionata is not None else cs[0].id_categoria
	ctx['categorie']= cs
	return TemplateResponse(request, 'news.html', ctx)

def dettaglio(request, id_categoria, id_news):
	ctx = {}
	try:
		c = Categoria.objects.get(codice_lingua=request.lingua.codice, id_categoria=id_categoria)
	except Categoria.DoesNotExist:
		raise Exception(_("La categoria non esiste"))
	try:
		n = News.objects.get(codice_lingua=request.lingua.codice, id_news=id_news)
	except News.DoesNotExist:
		raise Exception(_("La notizia non esiste"))
	ctx['categoria'] = c
	ctx['sottotitolo'] = c.nome
	ctx['news'] = n
	ctx['precedente'] = n.precedente(c)
	ctx['successiva'] = n.successiva(c)
	ctx['categorie'] = Categoria.objects.filter(codice_lingua=request.lingua.codice).order_by('pk')
	return TemplateResponse(request, 'news-dettaglio.html', ctx)