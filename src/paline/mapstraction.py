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

class BoundingBox(object):
	def __init__(self):
		object.__init__(self)
		self.min_x = None
		self.max_x = None
		self.min_y = None
		self.max_y = None
		
	def update(self, x, y):
		if self.min_x is None:
			self.min_x = x
			self.max_x = x
			self.min_y = y
			self.max_y = y
		else:
			self.min_x = min(x, self.min_x)
			self.min_y = min(y, self.min_y)
			self.max_x = max(x, self.max_x)
			self.max_y = max(y, self.max_y)
			
	def get_center(self):
		return ((self.max_x + self.min_x) / 2.0,  (self.max_y + self.min_y) / 2.0)

class RPyCAllowRead(object):
	def _rpyc_getattr(self, name):
		return getattr(self, name)
	
class RPycAllowWrite(object):
	def _rpyc_setattr(self, name, value):
		setattr(self, name, value)


class Map(RPyCAllowRead):
	def __init__(self, type='google'):
		RPyCAllowRead.__init__(self)
		self.polylines = []
		self.markers = []
		self.center = (0, 0)
		self.zoom = 2
		self.type = type
		self.bb = BoundingBox()
		
	def add_polyline(self, points, opacity=1, color='#000000', thickness=1):
		self.polylines.append({
			'points': points,
			'opacity': opacity,
			'thickness': thickness,
			'color': color,
		})
		for p in points:
			self.bb.update(*p)
		
	def add_marker(self, point, icon, icon_size=(20, 20), infobox=None, label=None):
		self.markers.append({
			'point': point,
			'icon': icon,
			'infobox': infobox,
			'label': label,
			'iconSize': icon_size,
		})
		self.bb.update(*point)
		
		
	def center_and_zoom(self, point, zoom):
		self.center = point
		self.zoom = zoom
		

	def render(self, filename=None):
		self.center_and_zoom(self.bb.get_center(), 13)
		out = ''
		out += """
			map = new mxn.Mapstraction('map_canvas','%s');
			map.addControls({
				pan: true,
				zoom: 'large',
				map_type: false
			});
		""" % self.type
		
		# Polylines
		pi = 0
		for p in self.polylines:
			pi += 1
			poly = ["new mxn.LatLonPoint(%f, %f)" % (x[1], x[0]) for x in p['points']]
			out += """
				var myPoly%(numero)d = new mxn.Polyline([%(punti)s]);
				myPoly%(numero)d.setColor('%(color)s');
				myPoly%(numero)d.setOpacity(%(opacity)f);
				myPoly%(numero)d.setWidth(%(thickness)f);
				map.addPolyline(myPoly%(numero)d);				
			""" % ({
				'punti': ", ".join(poly),
				'numero': pi,
				'color': p['color'],
				'opacity': p['opacity'],
				'thickness': p['thickness'],
			})
			
		# Markers
		mi = 0
		for m in self.markers:
			mi += 1
			out += """
				m%(numero)d = new mxn.Marker( new mxn.LatLonPoint(%(x)f, %(y)f));
				m%(numero)d.addData({
					%(infoBubble)s
					%(label)s
					marker : 4,
					icon : "%(icon)s",
					iconSize : [%(iconWidth)d, %(iconHeight)d],
					draggable : false,
					hover : false
				});		
				map.addMarkerWithData(m%(numero)d);
				map.setCenterAndZoom(new mxn.LatLonPoint(%(center_x)f, %(center_y)f), %(zoom)d);

			""" % {
				'infoBubble': '' if m['infobox'] is None else ('infoBubble: "%s",' % m['infobox']),
				'label': '' if m['label'] is None else 'label: "%s",' % m['label'],
				'icon': m['icon'],
				'x': m['point'][1],
				'y': m['point'][0],
				'numero': mi,
				'iconWidth': m['iconSize'][0],
				'iconHeight': m['iconSize'][1],
				'center_x': self.center[1],
				'center_y': self.center[0],
				'zoom': self.zoom,
			}
		
		if filename is None:
			return out;
		f = open(filename, 'w')
		f.write(out)
		f.close()
		
