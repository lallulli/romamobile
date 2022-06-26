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
from servizi.utils import oggetto_con_max, oggetto_con_min, datetime2mysql
import json

class AssNewsCategoria(models.Model):
	id_news = models.ForeignKey('News', db_column='id_news')
	id_categoria = models.ForeignKey('Categoria', db_column='id_categoria')

class Categoria(models.Model):
	id_categoria = models.IntegerField(primary_key=True)
	codice_lingua = models.CharField(max_length=6)
	nome = models.CharField(max_length=93)
	posizione = models.IntegerField(null=True, blank=True)
	
		
	def news_by_date(self):
		return self.news_set.order_by('-data_pubblicazione')

class News(models.Model):
	id_news = models.IntegerField(primary_key=True)
	codice_lingua = models.CharField(max_length=6)
	titolo = models.CharField(max_length=765)
	contenuto = models.TextField()
	data_pubblicazione = models.DateTimeField()
	primo_piano = models.IntegerField()
	categorie = models.ManyToManyField(Categoria, through='AssNewsCategoria')
	
	def prima_categoria(self):
		cs = self.categorie.all()
		if len(cs) > 0:
			return cs[0]
		# Ogni news deve avere almeno una categoria. Se per qualche motivo non ne ha una,
		# restituiamo una categoria arbitraria per soddisfare i prerequisiti dei clienti
		return Categoria.objects.all()[0]
	
		
	def precedente(self, categoria):
		try:
			return oggetto_con_min(News.objects.filter(data_pubblicazione__gt=self.data_pubblicazione, codice_lingua=self.codice_lingua, categorie=categoria), 'data_pubblicazione')
		except News.DoesNotExist as e:
			return None
		
	def successiva(self, categoria):
		try:
			return oggetto_con_max(News.objects.filter(data_pubblicazione__lt=self.data_pubblicazione, codice_lingua=self.codice_lingua, categorie=categoria), 'data_pubblicazione')
		except News.DoesNotExist as e:
			return None

def genera_json():
	news = []
	ns = News.objects.all().order_by('categorie__id_categoria', '-data_pubblicazione').distinct()

	for n in ns:
		news.append({
			'id_news': n.id_news,
			'codice_lingua': n.codice_lingua,
			'categorie': [c.id_categoria for c in n.categorie.all()],
			'titolo': n.titolo,
			'contenuto': n.contenuto,
			'data_pubblicazione': datetime2mysql(n.data_pubblicazione),
			'primo_piano': n.primo_piano,
		})

	cat = []

	cs = Categoria.objects.all()
	for c in cs:
		cat.append({
			'id_categoria': c.id_categoria,
			'codice_lingua': c.codice_lingua,
			'nome': c.nome,
			'posizione': c.posizione,
		})

	return json.dumps({
		'categorie': cat,
		'news': news,
	})
