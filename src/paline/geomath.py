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

from math import *
import pyproj
import math
import os, os.path, shutil
from servizi.utils import make_temp_directory
from contextlib import contextmanager
import shapefile

# Promemoria coordinate usate da:
# Nostro grafo: gbfe
# Infopoint: gbfe
# Rete TPL: gbfe
# Tele Atlas: gbfo
# osm: wgs84
# mapstraction: wgs84


gbfe = pyproj.Proj("+proj=tmerc +lat_0=0 +lon_0=15 +k=0.9996 +x_0=2520000 +y_0=0 +ellps=intl +units=m +no_defs")
gbfo = pyproj.Proj("+proj=tmerc +lat_0=0 +lon_0=9 +k=0.9996 +x_0=1500000 +y_0=0 +ellps=intl +units=m +no_defs")
corr_gbfe = (-16, 78)


def gbfe_to_wgs84(x, y):
	x, y = (x + corr_gbfe[0], y + corr_gbfe[1])
	return gbfe(x, y, inverse=True)


def wgs84_to_gbfe(x, y):
	x, y = gbfe(x, y)
	return (x - corr_gbfe[0], y - corr_gbfe[1])


def distance_proj(lat1, lon1, lat2, lon2):
	a = lat1 - lat2
	b = lon1 - lon2
	return sqrt(a * a + b * b)


def dot(A, B, C):
	AB = [0, 0]
	BC = [0, 0]
	AB[0] = B[0]-A[0]
	AB[1] = B[1]-A[1]
	BC[0] = C[0]-B[0]
	BC[1] = C[1]-B[1]
	dot = AB[0] * BC[0] + AB[1] * BC[1]
	return dot


def cross(A, B, C):
	AB = [0, 0]
	AC = [0, 0]
	AB[0] = B[0]-A[0]
	AB[1] = B[1]-A[1]
	AC[0] = C[0]-A[0]
	AC[1] = C[1]-A[1]
	cross = AB[0] * AC[1] - AB[1] * AC[0]
	return cross


def distance(A, B):
	d1 = A[0] - B[0]
	d2 = A[1] - B[1]
	return math.sqrt(d1*d1+d2*d2)


def segment_point_dist(A, B, C):
	d = distance(A,B)
	if d > 0:
		dist = cross(A,B,C) / d
		dot1 = dot(A,B,C)
		if dot1 > 0:
			return distance(B,C)
		dot2 = dot(B,A,C)
		if dot2 > 0:
			return distance(A,C)
		return abs(dist)
	else:
		return distance(A, C)


def azimuth_deg(p1, p2):
	"""
	Compute azimuth of segment p1p2, in degrees
	"""
	dx = p2[0] - p1[0]
	dy = p2[1] - p1[1]
	if dy == 0:
		if dx > 0:
			return 90
		elif dx < 0:
			return 270
		else:
			raise Exception('Cannot compute azimuth of null vector')

	a = math.atan(dx / dy) * 180 / math.pi
	if a < 0:
		a += 180
	if dx < 0 or (dx == 0 and dy < 0):
		a += 180
	return a


def piede_perpendicolare(A, B, P):
	Ax, Ay = A
	Bx, By = B
	Px, Py = P
	# Retta parallela all'asse x
	if Ax == Bx:
		return Ax, Py
	# Retta parallela all'asse y
	if Ay == By:
		return Px, By
	# Altri casi
	m = (By - Ay) / (Bx - Ax) # Coeff. angolare retta
	q = (Ax * By - Ay * Bx) / (Ax - Bx)
	mp = -1 / m # Coeff. angolare perpendicolare
	norm = sqrt(1 + m * m)
	d = abs(m * Px - Py + q) / norm # Distanza punto-retta
	# Posizione di P rispetto alla retta: se k e m sono concordi, P sta "a sinistra" della retta
	# e quindi mi avvicino alla retta seguendo il versore; altrimenti devo andare
	# in verso opposto
	k = m * Px - Py + q
	kv = -1 if k * m > 0 else 1
	# versore = (1, mp) / normp, restituisco P + d * versore:
	normp = sqrt(1 + mp * mp)
	q = (Px + kv * d / normp, Py + kv * mp * d / normp)
	return q


# class SegmentRepo(object):
# 	def __init__(self):
# 		object.__init__(self)
# 		self.s = []
#
# 	def add_segment(self, a, b, ref):
# 		self.s.append(((a[0], a[1]), (b[0], b[1]), ref))
#
# 	def find_nearest_segment(self, p):
# 		#p = self.proj(p[0], p[1])
# 		min = None
# 		minpoint = None
# 		for seg in self.s:
# 			a, b, ref = seg
# 			d = segment_point_dist(a, b, p)
# 			if min is None or d < min:
# 				minpoint = ref
# 				min = d
# 		e = minpoint
# 		#logging.info("Geocoding done, street name is: %s" % graph.streets.inverse_search(e.name))
# 		ds = distance(e.s.get_coordinate()[0], p)
# 		dt = distance(e.t.get_coordinate()[0], p)
# 		return (e, e.s if ds < dt else e.t)
#
#
# class ShapelySegmentRepo(object):
# 	def __init__(self):
# 		object.__init__(self)
# 		self.s = []
#
# 	def add_segment(self, a, b, ref):
# 		l = LineString([(a[0], a[1]), (b[0], b[1])])
# 		l.riferimento = ref
# 		self.s.append(l)
#
# 	def find_near_segments(self, p, hint=16):
# 		if len(self.s) == 0:
# 			return []
# 		res = []
# 		while len(res) == 0:
# 			buffer = PreparedGeometry(p.buffer(hint))
# 			res = filter(buffer.intersects, self.s)
# 			hint *= 2
# 			print hint
# 		return res
#
# 	def find_nearest_segment(self, p):
# 		pt = Point(p)
# 		near = self.find_near_segments(pt)
# 		min = None
# 		minpoint = None
# 		for seg in near:
# 			d = seg.distance(pt)
# 			if min is None or d < min:
# 				minpoint = seg
# 				min = d
# 		e = minpoint.riferimento
# 		#logging.info("Geocoding done, street name is: %s" % graph.streets.inverse_search(e.name))
# 		ds = distance(e.s.get_coordinate()[0], p)
# 		dt = distance(e.t.get_coordinate()[0], p)
# 		return (e, e.s if ds < dt else e.t)
#
#
# class Geocoder(object):
# 	def __init__(self, graph, edge_type_id=None):
# 		object.__init__(self)
# 		self.graph = graph
# 		self.repo = ShapelySegmentRepo()
# 		for eid in graph.archi:
# 			if edge_type_id is None or edge_type_id == eid[0]:
# 				e = graph.archi[eid]
# 				self.repo.add_segment(e.s.get_coordinate()[0], e.t.get_coordinate()[0], e)
#
# 	def find_nearest_edge_and_point(self, point):
# 		return self.repo.find_nearest_segment(point)


def generate_prj_file(base_file_name, gbfe=False):
	"""
	Generate .prj file for shapefile projection

	base_file_name: path and file name without extension (.prj is added by this function)
	"""
	with open("%s.prj" % base_file_name, "w") as prj:
		if gbfe:
			epsg = 'PROJCS["Monte_Mario_Italy_zone_2",GEOGCS["GCS_Monte Mario",DATUM["D_Monte_Mario",SPHEROID["International_1924",6378388,297]],PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",15],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",2520000],PARAMETER["false_northing",0],UNIT["Meter",1]]'
		else:
			epsg = 'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]'
		prj.write(epsg)


@contextmanager
def zipped_shapefile(type, path, base_name, gbfe=False):
	"""
	Generate zipped shapefile

	Generates a shapefile.Writer, that can be manipulated. After the generator block, file is actually created on disk

	base_name should not contain extension (neither .zip nor .shp)

	Usage example:
	with zipped_shapefile(shapefile.LINE, './roads') as shp:
		shp.field('ID', 'C', '10')
		shp.line(parts=[[[41, 12], [42, 13]],])
		shp.record(ID=1)
	"""
	shp = shapefile.Writer(type)
	yield shp
	with make_temp_directory() as tmpdir:
		base_path = os.path.join(tmpdir, base_name)
		shp.save(base_path)
		generate_prj_file(base_path, gbfe)
		zipfile = shutil.make_archive(base_name, 'zip', tmpdir)
		shutil.move(zipfile, os.path.join(path, base_name + ".zip"))

