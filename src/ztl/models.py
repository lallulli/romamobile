# coding: utf-8

#
#    Copyright 2013-2016 Roma servizi per la mobilit� srl
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


from collections import defaultdict
from django.db import models
from servizi.models import GiornoSettimana, Luogo
from gis.models import Multipoligono
from django.contrib.gis.geos import MultiPolygon, GEOSGeometry
from django.contrib.gis.gdal import DataSource
from datetime import datetime

class ZTL(Luogo):
	codice = models.CharField(max_length=15, unique=True, db_index=True)
	descrizione = models.CharField(max_length=100)
	ordinamento = models.IntegerField()
	
	GeoModel = Multipoligono
	
	def __unicode__(self):
		return self.descrizione
	
	class Meta:
		ordering = ['ordinamento']
		verbose_name = u'ZTL'
		verbose_name_plural = u'ZTL'

class Varco(models.Model):
	ztl = models.ForeignKey('ZTL')
	toponimo = models.CharField(max_length=100)
	descrizione = models.CharField(max_length=100)
	ordinamento = models.IntegerField()

	def __unicode__(self):
		return u"%s - %s" % (self.ztl.descrizione, self.toponimo)
	
	class Meta:
		ordering = ['ordinamento']
		verbose_name = u'Varco'
		verbose_name_plural = u'Varchi'

class Calendario(models.Model):
	ztl = models.ForeignKey('ZTL')
	giorno = models.ForeignKey(GiornoSettimana)
	ora_inizio = models.TimeField(default=datetime.now())
	ora_fine = models.TimeField(default=datetime.now())
	fine_domani = models.BooleanField(default=False)

	def __unicode__(self):
		return u"%s - %s" % (self.ztl.descrizione, self.giorno.nome)

	class Meta:
		verbose_name = u'Calendario'
		verbose_name_plural = u'Calendario'
		ordering = ['giorno']

class ModificaStraordinaria(models.Model):
	ztl = models.ForeignKey('ZTL')
	giorno = models.DateField()
	ora_inizio = models.TimeField(blank=True, null=True)
	ora_fine = models.TimeField(blank=True, null=True)
	fine_domani = models.BooleanField()
	attiva = models.BooleanField()
	
	def __unicode__(self):
		return u"%s - %s" % (self.ztl.descrizione, self.giorno)
	
	class Meta:
		verbose_name = u'Modifica Straordinaria'
		verbose_name_plural = u'Modifiche Straordinarie'
	
def load_shapefile():
	name = 'ztl/shp/ztl.shp'
	source_srid = 4326 # WGS84
	ds = DataSource(name)
	layer = ds[0]
	gs = layer.get_geoms()
	fs = layer.get_fields('codice')
	n = len(gs)
	d = defaultdict(set)
	for i in range(n):
		g = gs[i]
		f = fs[i]
		d[f].add(GEOSGeometry(g.wkb, srid=source_srid))
	for codice in d:
		try:
			z = ZTL.objects.get(codice=codice)
			z.geom = MultiPolygon(list(d[codice]), srid=source_srid)
			z.save()
		except ZTL.DoesNotExist:
			print "ZTL %s non trovata" % codice

