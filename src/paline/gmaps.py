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

import cgpolyencode as gpolyenc
import uuid
import settings

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


class PolySplit(object):
	def __init__(self, min_x, max_x, min_y, max_y):
		self.min_x = min_x
		self.max_x = max_x
		self.min_y = min_y
		self.max_y = max_y
		self.pls = []
		self.inside = False

	def add(self, x, y):
		if self.min_x < x and x < self.max_x and self.min_y < y and y < self.max_y:
			if self.inside:
				self.pls[-1].append((x, y))
			else:
				self.pls.append([(x, y)])
				self.inside = True				
		else:
			self.inside = False
		
		
class Map(RPyCAllowRead):
	def __init__(self, type='google'):
		RPyCAllowRead.__init__(self)
		self.polylines = []
		self.markers = []
		self.center = (0, 0)
		self.zoom = 2
		self.type = type
		self.realtime_routes = []
		self.realtime_routes_icon = ''
		self.oscuramento = False
		
	def add_polyline(self, points, opacity=1, color='#000000', thickness=1, id_toggle=None, zIndex=0):
		self.polylines.append({
			'points': points,
			'opacity': float(opacity),
			'thickness': float(thickness),
			'color': color,
			'id_toggle': id_toggle,
			'zIndex': zIndex,
		})
				
	def add_marker(
		self,
		point,
		icon,
		icon_size=(20, 20),
		infobox=None,
		label=None,
		id_toggle=None,
		anchor=None,
		name=None,
		open=False,
		drop_callback='',
		desc='',
		distance=None,
		max_width=None,
	):
		self.markers.append({
			'point': point,
			'icon': icon,
			'infobox': infobox,
			'label': label,
			'iconSize': icon_size,
			'id_palina': None,
			'id_toggle': id_toggle,
			'anchor': anchor,
			'name': name,
			'open': open,
			'drop_callback': drop_callback,
			'desc': desc,
			'distance': distance,
			'max_width': max_width,
		})
		
	def add_marker_busstop(self, point, icon, id_palina, icon_size=(20, 20), infobox=None, label=None, capolinea=None, id_toggle=None, anchor=None, id_percorso=None, open=False, drop_callback='', desc='', distance=None):
		self.markers.append({
			'point': point,
			'icon': icon,
			'infobox': infobox,
			'label': label,
			'iconSize': icon_size,
			'id_palina': id_palina,
			'capolinea': capolinea,
			'id_toggle': id_toggle,
			'anchor': anchor,
			'name': None if id_palina is None else ('palina', (id_palina, id_percorso, capolinea)),
			'open': open,
			'drop_callback': drop_callback,
			'desc': desc,
			'distance': distance,	
		})
		
	def set_realtime_routes(self, routes, icon):
		self.realtime_routes = routes
		self.realtime_routes_icon = icon
		
	def add_realtime_route(self, route, icon=None):
		if icon is not None:
			self.realtime_routes_icon = icon
		self.realtime_routes.append(route)
		
	def center_and_zoom(self, point, zoom):
		self.center = point
		self.zoom = zoom
		
	def serialize(self):
		return {
			'markers': self.markers,
			'polylines': self.polylines,
		}
		

	def render(self, filename=None, url_tempi=None, nome_metodo=None, id_palina=None, id_percorso=None):
		
		out = ''
		
		if url_tempi and nome_metodo:
				out += """
				<script type="text/javascript">
				
					var map;
					var markers = new Array();
					var markers_bus = new Array();
					var bubbles = new Array();
					var toggles = new Array();
					var open_bubble = "";
				
						var service = new rpc.ServiceProxy("%(url_tempi)s", {
								methods: ["%(nome_metodo)s", "paline.Trovalinea.PercorsoMappa", "paline.Trovalinea.VeicoliPercorso"],
								protocol: "XML-RPC",
								sanitize: false
						});
						
						function get_veicoli_percorso(id_percorso, target_map, bounds) {
							for(var i=0; i<markers_bus.length;i++) {
								markers[markers_bus[i]].setMap(null);
							}
							service.paline.Trovalinea.VeicoliPercorso({
								params: [id_percorso],
								onSuccess: function(res) {
									var marker_veicoli = {};
									var info_veicoli = {};
									for(var i=0; i<res.length; i++) {
										v = res[i];
										
										args = {
											'x': v['lat'],
											'y': v['lon'],
											'label': v['id_veicolo'],
											'icon_path': '%(realtime_routes_icon)s',
											'codice': v['id_veicolo'],
											'testo': v['infobox'],
											'pixelOffsetX': null,
											'pixelOffsetY': null,
											'drag': null
										}
										addBubbleBus(target_map, bounds, args);
										
									}
								},
								onException: function(errorObj) {
									alert("Exception: " + errorObj);
								},
								onComplete: function(responseObj) {
									//any "final" logic
								}						
							})
						}
						
						
						function get_veicoli(id_palina, id_percorso, capolinea, bubble) {
								service.%(nome_metodo)s({
										params: [id_palina, id_percorso, capolinea],
										onSuccess:function(res){
											bubble.setContent(res);
										},
										onException:function(errorObj){
											alert("Exception: " + errorObj);
										},
										onComplete:function(responseObj){
											//any "final" logic
										}
						});
						}
						function get_toggle(id_toggle) {
								service.paline.Trovalinea.PercorsoMappa({
										params: [id_toggle],
										onSuccess:function(res) {
											for(var i=0; i<res['fermate'].length; i++) {
												add_fermata(res['fermate'][i]);
											}
											add_percorso(res['percorso']);
										},
										onException:function(errorObj){
											alert("Exception: " + errorObj);
										},
										onComplete:function(responseObj){
											//any "final" logic
										}
						});
						}
						
				
				""" % {
						'url_tempi': url_tempi,
						'nome_metodo': nome_metodo,
						'realtime_routes_icon': self.realtime_routes_icon,
				} 
			
		
		out += """
		</script>
		<script type="text/javascript">
				var map;
				var markers = new Array();
				var markers_bus = new Array();
				var bubbles = new Array();
				var toggles = new Array();
				var open_bubble = "";
				
				function addBubbleFermata(map, bounds, args) {
					m = addBubble(map, bounds, args);
					google.maps.event.addListener(m, "click", function() {
						openBubble(args.codice);
						%(func)s
					});
				}
				
				function addBubbleStandard(map, bounds, args) {
					m = addBubble(map, bounds, args);
					google.maps.event.addListener(m, "click", function() {
						openBubble(args.codice);
					});
				}
				
				function addBubbleBus(map, bounds, args) {
					m = addBubble(map, bounds, args);
					markers_bus.push(m.getTitle());
					google.maps.event.addListener(m, "click", function() {
						openBubble(args.codice);
					});
				}
				
				function addBubble(map, bounds, args) {
					if(args.testo==null) args.testo = "Caricamento in corso...";
					if(args.pixelOffsetX==null) args.pixelOffsetX = 0;
					if(args.pixelOffsetY==null) args.pixelOffsetY = 0;
					if(args.drag==null) args.drag = false;
				
					mImg = new google.maps.MarkerImage(args.icon_path, null, null, args.anchor);
					mOpt = {
						position: new google.maps.LatLng(args.x, args.y),
						title: args.label,
						icon: mImg,
						draggable: args.drag,
						map: map,
					};		
					m = new google.maps.Marker(mOpt);
					
					markers[args.codice] = m;
					
					mInfoOpt = {
						content: args.testo,
						position: new google.maps.LatLng(args.x, args.y),
						pixelOffset: new google.maps.Size(args.pixelOffsetX, args.pixelOffsetY),
						visible: true
					}
					mInfo = new google.maps.InfoWindow(mInfoOpt);
					
					bubbles[args.codice] = mInfo;
					
					bounds.extend(m.getPosition());
					
					return m;
				}
					
				function openBubble(codice) {
						if(open_bubble != "") {
								open_bubble.close();
						}
						bubble = bubbles[codice];
						anchor = markers[codice];
						open_bubble = bubble;
						
						bubble.open(map, anchor);
				}
				
				function bus_timer(id_percorso, map, bounds) {
					setInterval(function(){get_veicoli_percorso(id_percorso, map, bounds)}, 30000);
				}
				
				function mapCenter(id_palina) {
						map.panTo(markers[id_palina].getPosition());
						openBubble(bubbles[id_palina], markers[id_palina], id_palina, "%(id_percorso)s", 0);
				}
				
				function add_percorso(percorso) {
					var p = {
							strokeColor: percorso['color'],
							strokeOpacity: percorso['opacity'],
							strokeWeight: percorso['thickness'],
							visible: true,
					}
					var poly = new google.maps.Polyline(p);
					punti = Array();
					for(var i=0; i<percorso['punti']; i++) {
						punto = percorso['punti'][i];
						punti.push(new google.maps.LatLng(punto[1], punto[0]));
					}
					poly.setPath(punti);
					poly.setMap(map);
					id_toggle = percorso['id_toggle']; 
					if(!(id_toggle in toggles)) {
						toggles[id_toggle] = Array();
					}
					toggles[id_toggle].push(poly);					
				}
				
				function add_fermata(fermata) {
					mImg = new google.maps.MarkerImage({
						url: fermata['img'],
						anchor: fermata['anchor'],
					})
					mOpt = {
						position: new google.maps.LatLng(fermata['punto'][1], fermata['punto'][0]),
						title: fermata['name'],
						icon: mImg,
						draggable : false,
						map: map,
					};
					m = new google.maps.Marker(mOpt);
					id_toggle = fermata['id_toggle'];
					if(!(id_toggle in toggles)) {
						toggles[id_toggle] = Array();
					}
					toggles[id_toggle].push(m);	
				}
								
				function toggle(id_toggle) {
					if(id_toggle in toggles) {
						visible = !(toggles[id_toggle][0].getVisible());
						for(var i=0; i<toggles[id_toggle]; i++) {
							obj = toggles[id_toggle][i];
							obj.setVisible(visible);
						}
					} else {
						get_toggle(id_toggle);
					}
				}
					
				function initialize() {

				var myOptions = {
					center: new google.maps.LatLng(41.892055, 12.483559),
					zoom: 13,
					mapTypeId: google.maps.MapTypeId.ROADMAP
				};	
				map = new google.maps.Map(document.getElementById("map_canvas"), myOptions);
				
				var bounds = new google.maps.LatLngBounds();
		""" % ({
				'func': "get_veicoli(args.codice, args.id_percorso, args.capolinea, bubble);" if url_tempi and nome_metodo else '',
				'id_percorso': id_percorso if id_percorso else '',
		})
		
		# Oscuramento
		if self.oscuramento:
			out += """
				var oscuramentoCoords = [
					new google.maps.LatLng(40.0, 10),
					new google.maps.LatLng(40.0, 13.0),
					new google.maps.LatLng(43.0, 13.0),
					new google.maps.LatLng(43.0, 10.0)
				];
			
				oscuramento = new google.maps.Polygon({
					paths: oscuramentoCoords,
					strokeColor: "#000000",
					strokeOpacity: 0.8,
					strokeWeight: 2,
					fillColor: "#000000",
					fillOpacity: 0.35
				});
			
				oscuramento.setMap(map);
			"""
		
		# Polylines
		pi = 0
		for p in self.polylines:
			pi += 1
			poly = ["new google.maps.LatLng(%f, %f)" % (x[1], x[0]) for x in p['points']]
			out += """
				var myPolyOpt%(numero)d = {
						strokeColor: "%(color)s",
						strokeOpacity: %(opacity)f,
						strokeWeight: %(thickness)f,
						visible: true,
				}
				var myPoly%(numero)d = new google.maps.Polyline(myPolyOpt%(numero)d);
				myPoly%(numero)d.setPath(Array(%(punti)s));
				myPoly%(numero)d.setMap(map);
			""" % ({
				'punti': ", ".join(poly),
				'numero': pi,
				'color': p['color'],
				'opacity': p['opacity'],
				'thickness': p['thickness'],
			})
			if p['id_toggle'] is not None:
				out += """
					if(!('%(id_toggle)s' in toggles)) {
						toggles['%(id_toggle)s'] = Array();
					}
					toggles['%(id_toggle)s'].push(myPoly%(numero)d);
				""" % {
					'id_toggle': p['id_toggle'],
					'numero': pi,							
				}
			
		# Markers
		mi = 0

		for m in self.markers:
			mi += 1
			if m['id_palina'] > 0:
				out += """
					args = {
						'x': %(x)f,
						'y': %(y)f,
						'label': "%(label)s",
						'icon_path': "%(icon_path)s",
						'codice': "%(codice)s",
						'id_percorso': "%(id_percorso)s",
						'capolinea': %(capolinea)d,
						'testo': null,
						'pixelOffsetX': null,
						'pixelOffsetY': null,
						'drag': null,
						'anchor': %(anchor)s
					}
					addBubbleFermata(map, bounds, args);
				""" % {
					'label': '' if m['label'] is None else "%s" % m['label'],
					'icon_path': m['icon'],
					'x': m['point'][1],
					'y': m['point'][0],
					'codice': m['id_palina'] if m['id_palina'] else '',
					'id_percorso': id_percorso if id_percorso else '',
					'capolinea': m['capolinea'],
					'anchor': ('new google.maps.Point(%d, %d)' % (m['anchor'][0], m['anchor'][1])) if m['anchor'] is not None else 'null',
				}
			else:
				out += """
					args = {
						'x': %(x)f,
						'y': %(y)f,
						'label': "%(label)s",
						'icon_path': "%(icon_path)s",
						'codice': "%(codice)s",
						'testo': "%(testo)s",
						'pixelOffsetX': null,
						'pixelOffsetY': 6,
						'drag': false,
						'anchor': %(anchor)s						
					}
					addBubbleStandard(map, bounds, args);
				""" % {
					'label': '' if m['label'] is None else m['label'],
					'icon_path': m['icon'],
					'x': m['point'][1],
					'y': m['point'][0],
					'codice': uuid.uuid1().get_hex(),
					'testo': m['infobox'],
					'anchor': ('new google.maps.Point(%d, %d)' % (m['anchor'][0], m['anchor'][1])) if m['anchor'] is not None else 'null',
				}
			
			if m['id_toggle'] is not None:
				out += """
					if(!('%(id_toggle)s' in toggles)) {
						toggles['%(id_toggle)s'] = Array();
					}
					toggles['%(id_toggle)s'].push(m%(numero)d);
				""" % {
					'id_toggle': m['id_toggle'],
					'numero': mi,							
				}
		
		# Veicoli percorso
		for id_percorso in self.realtime_routes:
			out += """
				get_veicoli_percorso('%s', map, bounds);
				bus_timer('%s', map, bounds);
			""" % (id_percorso, id_percorso)
		
		if len(self.markers) > 0:
			out += """
					map.fitBounds(bounds);
			"""


		if id_palina:
				out += """
				
				mapCenter(%(id_palina)s);
				""" % ({
						'id_palina': id_palina,
						'id_percorso': id_percorso,
				})
				
		out += """
		}
		</script>
		"""
		
		if filename is None:
			return out;
		f = open(filename, 'w')
		f.write(out)
		f.close()
	
	def guess_zoom(self, scale_x, scale_y):
		factor = scale_x if scale_x > scale_y else scale_y
		if factor > 15000:
			return 11
		else:
			return 12
		

		
	def render_static(self, zoom, center_y, center_x, id_palina=None):
		params = []
		# Aggiunge i parametri necessari per la mappa statica
		params.append('size=200x150')
		bounds = {
			'min_x': 999,
			'min_y': 999,
			'max_x': 0,
			'max_y': 0,
		}
		markers_str = []
				
		for m in self.markers:
			if bounds['min_x'] > m['point'][1]:
				bounds['min_x'] = m['point'][1]
			if bounds['max_x'] < m['point'][1]:
				bounds['max_x'] = m['point'][1]
			if bounds['min_y'] > m['point'][0]:
				bounds['min_y'] = m['point'][0]
			if bounds['max_y'] < m['point'][0]:
				bounds['max_y'] = m['point'][0]
		
		if (zoom is None or zoom == '') and id_palina is not None:
			zoom = 16
			for m in self.markers:
				if m['id_palina'] == id_palina:
					center = (m['point'][1], m['point'][0]) 
					break
		elif center_x is None or center_y is None:
			center = ( bounds['min_x']+(bounds['max_x']-bounds['min_x'])/2, bounds['min_y']+(bounds['max_y']-bounds['min_y'])/2)
		else:
			center = (float(center_y), float(center_x))
		
		params.append('zoom=%s' % zoom)

		scale_x = (bounds['max_x']-bounds['min_x'])*288895.288400
		scale_y = (bounds['max_y']-bounds['min_y'])*288895.288400

		if zoom is None or zoom == '':
			zoom = self.guess_zoom(scale_x, scale_y)
		zoom = int(zoom)

		shift_v = 0.024 / pow(2, int(zoom) - 12)
		shift_h = 0.034 / pow(2, int(zoom) - 12)
		
		min_x = center[0] - 1.5 * shift_h
		max_x = center[0] + 1.5 * shift_h
		min_y = center[1] - 1.5 * shift_v
		max_y = center[1] + 1.5 * shift_v
		
		markers_str.append('size:small')
		encoder = gpolyenc.GPolyEncoder()
		
		mcount = 1
		for m in self.markers:
			x = m['point'][1]
			y = m['point'][0]
			if zoom >= 14 or mcount == 1 or mcount == len(self.markers):
				if min_x < x and x < max_x and min_y < y and y < max_y:
					markers_str.append("""%(x)f,%(y)f""" % ({
						#'icon': m['icon'],
						'x': x,
						'y': y,
						}))

			mcount += 1


	
		for pl in self.polylines:
			e = encoder.encode(pl['points'])
			params.append("""path=color:0x%(color)s|weight:%(weight)s|enc:%(enc)s""" % {
				'color': pl['color'][1:],
				'weight': pl['thickness'],
				'enc': e['points'],
			})
	
			
		params.append("""center=%(x)f,%(y)f""" % {'x': center[0], 'y': center[1]})
		params.append('%s=%s' % ('markers', '|'.join(markers_str)))
		params.append('sensor=false')
		params.append('key={}'.format(settings.GOOGLE_MAPS_API_KEY))
		
		
		return {
			'map': '&'.join(params),
			'zoom': zoom,
			'center_x': "%f" % center[1],
			'center_y': "%f" % center[0],
			'shift_h': float(shift_h),
			'shift_v': float(shift_v),
		}
		
class MapStandard(Map):
	def add_marker(self, point, icon, icon_size=(20, 20), infobox=None, label=None):
		return Map.add_marker(self, point, icon, 0, icon_size, infobox, label)
		
	def render(self):
		return Map.render(self, '', '')