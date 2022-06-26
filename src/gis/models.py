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

from django.contrib.gis.db import models
from servizi.utils import dictfetchall, model2contenttype
from pprint import pprint
from django.db import connections
from django.contrib.gis.geos import Point, GEOSGeometry, LineString
from django.contrib.gis.gdal import DataSource
import traceback

# Create your models here.

def geos2sql(f):
	return "ST_GeomFromText('%s', %d)" % (f.wkt, f.srid)

def punti2linestring(punti, srid=3004):
	ls = LineString(punti)
	ls.srid = srid
	return ls

class Punto(models.Model):
	# Regular Django fields corresponding to the attributes in the
	# world borders shapefile.
	parent_id = models.CharField(max_length=50)
	parent_type = models.IntegerField()
	geom = models.PointField(srid=3004)
	
	objects = models.GeoManager()
	
	def __unicode__(self):
		return self.parent_id

	
class Polilinea(models.Model):
	# Regular Django fields corresponding to the attributes in the
	# world borders shapefile.
	parent_id = models.CharField(max_length=50)
	parent_type = models.IntegerField()
	geom = models.LineStringField(srid=3004)
	
	objects = models.GeoManager()
	
	def __unicode__(self):
		return self.parent_id
		
class Poligono(models.Model):
	# Regular Django fields corresponding to the attributes in the
	# world borders shapefile.
	parent_id = models.CharField(max_length=50)
	parent_type = models.IntegerField()
	geom = models.PolygonField(srid=3004)
	
	objects = models.GeoManager()

class Multipoligono(models.Model):
	# Regular Django fields corresponding to the attributes in the
	# world borders shapefile.
	parent_id = models.CharField(max_length=50)
	parent_type = models.IntegerField()
	geom = models.MultiPolygonField(srid=3004)

	objects = models.GeoManager()
	
	def __unicode__(self):
		return self.parent_id


class Punto(models.Model):
	# Regular Django fields corresponding to the attributes in the
	# world borders shapefile.
	parent_id = models.CharField(max_length=50)
	parent_type = models.IntegerField()
	geom = models.PointField(srid=3004)
	
	objects = models.GeoManager()
	
	def __unicode__(self):
		return self.parent_id

def geocode(point, polyline_model, max_distance=50):
	polyline_type = model2contenttype(polyline_model)
	cursor = connections['gis'].cursor()
	while True:
		sql = """
			select parent_id, geom, foot, st_split(st_snap(geom, foot, 1), foot) as parts
			from (
				select  b.parent_id, b.geom, st_closestpoint(b.geom, %(point)s) as foot
				from "gis_polilinea" b
				where st_dwithin(%(point)s, b.geom, 50)
				and b.parent_type = %(type)d
				and st_distance(%(point)s, b.geom) = (
					select min(dist) as mindist
					from (
						select b.parent_id, b.geom as bgeom, st_distance(%(point)s, b.geom) as dist
						from  "gis_polilinea" b
						where st_dwithin(%(point)s, b.geom, %(dist)s)
						and b.parent_type = %(type)d
					) as near
				)
			) as feat
		""" % {
			'point': geos2sql(point),
			'dist': max_distance,
			'type': polyline_type,
		}
		
		#print sql
		cursor.execute(sql)
		res = dictfetchall(cursor)
		#pprint(res)
		if len(res) > 0:
			break
		max_distance = max_distance * 2
	
	r = res[0]
	out = {
		'elem': polyline_model.objects.get(luogo_ptr_id=r['parent_id']),
		'geom': GEOSGeometry(r['geom']),
		'foot': GEOSGeometry(r['foot']),
		'parts': GEOSGeometry(r['parts'])
	}
	pprint(out)
	return out

def load_shapefile(name, source_srid):
	ds = DataSource(name)
	layer = ds[0]
	geom_gdal = layer.get_geoms()[0]
	geom_geos = GEOSGeometry(geom_gdal.wkb, srid=source_srid)
	return geom_geos
