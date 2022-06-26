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


from pyjamas.ui.ScrollPanel import ScrollPanel
from pyjamas.ui.Calendar import Calendar, DateField
from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.FlowPanel import FlowPanel
from pyjamas.ui.DisclosurePanel import DisclosurePanel
from pyjamas.ui.TabPanel import TabPanel
from pyjamas.ui.Grid import Grid
from pyjamas.ui.Frame import Frame
from pyjamas.ui.TextBox import TextBox
from pyjamas.ui.TextArea import TextArea
from pyjamas.ui.HTML import HTML
from pyjamas.ui.Label import Label
from pyjamas.ui.CheckBox import CheckBox
from pyjamas.ui.ListBox import ListBox
from pyjamas.ui.Button import Button
from pyjamas.ui.PopupPanel import PopupPanel
from pyjamas.ui.KeyboardListener import KeyboardHandler
from pyjamas.ui.Tree import Tree, TreeItem
from pyjamas.ui.Image import Image
from pyjamas.ui import HasAlignment
from pyjamas.ui.MenuBar import MenuBar
from pyjamas.ui.MenuItem import MenuItem
from pyjamas.ui.Widget import Widget
from pyjamas.ui.Hyperlink import Hyperlink
from pyjamas import Window
from pyjamas.Timer import Timer
from pyjamas.JSONService import JSONProxy
from pyjamas import History
from pyjamas import DOM
from prnt import prnt
from pyjamas.ui.ContextMenuPopupPanel import ContextMenuPopupPanel
from datetime import date, time, datetime, timedelta
from __pyjamas__ import JS

from DissolvingPopup import DissolvingPopup
from util import JsonHandler, redirect, MenuCmd, HTMLFlowPanel, SearchPopup, DeferrablePanel, MyAnchor
from util import _, get_lang, PaginatedPanelPage
from globals import base_url, make_absolute


client = JSONProxy(base_url + '/json/', ['mappa_layer'])

def list_to_point_array(l):
	JS("""punti = Array();""")
	for y, x in l:
		JS("""punti.push(new $wnd['L'].latLng(x, y));""")
	return punti

class MapPanel(SimplePanel, DeferrablePanel):
	def __init__(self, owner, display_callback=None):
		SimplePanel.__init__(self)
		DeferrablePanel.__init__(self)
		self.owner = owner
		self.setSize('100%', '100%')
		self.layers = []
		self.layer_panels = []
		self.right_click_options = []
		self.setID('map-container')
		self.display_callback=display_callback
		self.open_bubble = None
		self.animation_enabled = True
		
	def addRightClickOption(self, option, callback):
		self.right_click_options.append((option, callback))
		
	def rightClickHandlerFactory(self, cb, lat, lng):
		def handler():
			cb(lat, lng)
		return handler
		
	def onRightClick(self, lat, lng, x, y):
		mx = DOM.getAbsoluteLeft(self.getElement())
		my = DOM.getAbsoluteTop(self.getElement())
		menu = MenuBar(vertical=True)
		for opt, cb in self.right_click_options:
			menu.addItem(opt, MenuCmd(self.rightClickHandlerFactory(cb, lat, lng)))
		popup = ContextMenuPopupPanel(menu)
		popup.addStyleName('context-menu-popup')
		popup.showAt(x + mx, y + my)


	def create_map_new(self):
		func = self.onRightClick
		JS("""
			this.map = $wnd['L'].map(
				'map-container', {
					zoomControl: false
				}
			).setView([41.892055, 12.483559], 12);
			zoom_ctrl = $wnd['L'].control.zoom({position: 'topright'});
			this.map.addControl(zoom_ctrl);
			$wnd['L'].esri.basemapLayer("Streets", {detectRetina: false}).addTo(this.map);
			this.map.addEventListener('contextmenu', function(e) {
				func(e.latlng.lat, e.latlng.lng, e.containerPoint.x, e.containerPoint.y)
			});
		""")


	def create_map_old(self):
		mapquestAttrib = """Tiles Courtesy of <a href="http://www.mapquest.com/" target="_blank">MapQuest</a>
		<img src="http://developer.mapquest.com/content/osm/mq_logo.png">,
		&copy; <a href="http://www.openstreetmap.org/" target="_blank">OpenStreetMap</a>"""
		func = self.onRightClick
		JS("""
			this.map = $wnd['L'].map(
				'map-container', {
					zoomControl: false
				}
			).setView([41.892055, 12.483559], 12);
			zoom_ctrl = $wnd['L'].control.zoom({position: 'topright'});
			this.map.addControl(zoom_ctrl);
			osm = $wnd['L'].tileLayer('http://{s}.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.png', {
				attribution: mapquestAttrib,
				detectRetina: false,
				maxZoom: 18,
				subdomains: ['otile1', 'otile2', 'otile3', 'otile4']
			});
			osm.addTo(this.map);
			/*
				pcn = $wnd['L'].tileLayer.wms("http://wms.pcn.minambiente.it/ogc?map=/ms_ogc/WMS_v1.3/raster/ortofoto_colore_08.map", {
					layers: 'OI.ORTOIMMAGINI.2008',
					minZoom: 16,
					format: 'image/png',
					attribution: '<a href="http://www.pcn.minambiente.it/GN/" target="_blank">Geoportale Nazionale</a>'
				});
				var baseMaps = {
					"Cartografia": osm,
				};
				var overlayMaps = {
					"Immagini aeree (zoom in)": pcn
				};
				var layersControl = new $wnd['L'].Control.Layers(baseMaps, overlayMaps);
				this.map.addControl(layersControl);
			*/
			this.map.addEventListener('contextmenu', function(e) {
				func(e.latlng.lat, e.latlng.lng, e.containerPoint.x, e.containerPoint.y)
			});
		""")

	def create_map(self):
		return self.create_map_new()

	def relayout(self):
		JS("""self.map.invalidateSize();""")
			
	def replace_bubble(self, new_bubble):
		if self.open_bubble is not None:
			self.open_bubble.closeBubble()
		self.open_bubble = new_bubble
		
	def display(self):
		if self.display_callback is not None:
			self.display_callback()
		
	def addLayerPanel(self, lp):
		self.layer_panels.append(lp)
		
	def addLayer(self, l):
		self.layers.append(l)
		self.notifyLayerPanels()
	
	def removeLayer(self, l):
		self.layers.remove(l)
		self.notifyLayerPanels()
		
	def notifyLayerPanels(self):
		for l in self.layer_panels:
			l.redraw()
			
	def notifyLayerPanelsChecked(self, name, checked):
		for l in self.layer_panels:
			l.setChecked(name, checked)
			
	def layerByName(self, name):
		for l in self.layers:
			if l.name == name:
				return l
		return None
			
	def onLoadNewLayerFactory(self, layer_name, onDone, info_panel, on_error):
		def onLoadLayer(res):
			if 'errore' in res:
				if on_error is not None:
					on_error(res['errore'])
				return
			l = Layer(layer_name, res['descrizione'], self)
			l.deserialize(res, info_panel=info_panel)
			self.owner.center_and_zoom(l)
			if onDone is not None:
				onDone(l)

		return onLoadLayer
			
	def loadNewLayer(self, layer_name, func_name, func_id, onDone=None, toggle=None, reload=False, info_panel=None, on_error=None):
		self.display()
		l = self.layerByName(layer_name)
		if l is not None:
			if reload:
				l.destroy()
			else:
				if toggle is None:
					l.toggleVisible()
				else:
					l.setVisible(toggle)
				if onDone is not None:
					onDone(l)
				return
		client.mappa_layer((func_name, func_id), get_lang(), JsonHandler(self.onLoadNewLayerFactory(layer_name, onDone, info_panel, on_error)))
		
	def hideAllLayers(self):
		for l in self.layers:
			l.setVisible(False)

	def centerMarkers(self, markers):
		JS("""bounds = new $wnd['L'].latLngBounds([]);""")
		for m in markers:
			JS("""bounds.extend(m.marker.getLatLng());""")
		JS("""self.map.fitBounds(bounds.pad(.25), {animate: self.animation_enabled});""")

	def setBoundingBox(self, nw, se, pad=0.25):
		n = nw[1]
		w = nw[0]
		e = se[0]
		s = se[1]
		JS("""
			nw = new $wnd['L'].latLng(n, w);
			se = new $wnd['L'].latLng(s, e);
			bounds = new $wnd['L'].latLngBounds(nw, se);
			self.map.fitBounds(bounds.pad(pad), {animate: self.animation_enabled});
		""")

			
class InfoPanel(PaginatedPanelPage, ScrollPanel):
	def __init__(self, owner, icon, name, desc, distance, onClic=None):
		PaginatedPanelPage.__init__(self)
		ScrollPanel.__init__(self)
		self.setHeight('126px')
		self.hp = HorizontalPanel()
		self.add(self.hp)
		self.addStyleName('palina')
		icon = make_absolute(icon)
		self.image = Image(icon)
		self.hp.add(self.image)
		self.hfp = HTMLFlowPanel()
		# self.hfp.addAnchor(name, self.onClic)
		# if distance is not None:
		# 	self.hfp.addHtml('&nbsp;a %s' % distance)
		# self.hfp.addBr()
		self.hfp.addHtml(desc)
		self.hp.add(self.hfp)
		self.onClicCallback = onClic
		
	def onClic(self):
		if self.onClicCallback is not None:
			self.onClicCallback()


class Layer(object):
	def __init__(self, name, label, map_panel, owner=None, add_layer=None, function=None):
		self.name = name
		self.label = label
		self.map_panel = map_panel
		self.owner = owner
		self.features = []
		self.visible = True
		self.sub = []
		self.owner = owner
		self.destroyed = False
		self.function = function
		map = map_panel.map
		JS("""
			self.group = new $wnd['L'].featureGroup();
			self.group.addTo(map);
		""")
		if add_layer == True or (self.owner is None and add_layer != False):
			map_panel.addLayer(self)
		if self.owner is not None:
			client.mappa_layer(function, get_lang(), JsonHandler(self.onMappaLayerDone))

			
	def onMappaLayerDone(self, res):
		self.deserialize(res)
		
	def getMap(self):
		return self.map_panel.map
	
	def deserialize(self, res, callbacks=None, info_panel=None):
		for f in self.features:
			f.setVisible(False)
		self.features = []		
		if 'markers' in res:
			for m in res['markers']:
				name = m['name'] if 'name' in m else None
				open = m['open'] if 'open' in m else False
				dc = None
				if callbacks is not None and 'drop_callback' in m and m['drop_callback'] != '':
					dc = callbacks[m['drop_callback']]
				infobox = "<b>%s</b>" % m['infobox']
				if m['desc'] != '':
					infobox += "<br /><br />%s" % m['desc']
				marker = Marker(self, m['point'], m['icon'], m['iconSize'], infobox, m['label'], m['anchor'], visible=self.visible, name=name, open=open, drop_callback=dc)
				if info_panel is not None and m['infobox'] != "Sono qui":
					title = m['infobox']
					if m['distance'] is not None:
						title += _(" a ") + m['distance']
					ip = InfoPanel(info_panel, m['icon'], m['infobox'], m['desc'], m['distance'], onClic=marker.openBubble)
					info_panel.add(ip, title=title)
		if 'polylines' in res:		
			for p in res['polylines']:
				Polyline(self, p['points'], p['opacity'], p['color'], p['thickness'], p['zIndex'], visible=self.visible)
		if 'sublayers' in res:
			for s in res['sublayers']:
				sl = Layer('sublayer', None, self.map_panel, self, function=s)
				self.sub.append(sl)
		if 'refresh' in res:
			self.refresh = res['refresh'] * 1000
			Timer(self.refresh, self.onRefresh)
			
	def onRefresh(self):
		client.mappa_layer(self.function, get_lang(), JsonHandler(self.onMappaLayerDone, self.onRefreshError))

	def onRefreshError(self):
		Timer(self.refresh, self.onRefresh())

	def setVisible(self, visible=True):
		self.visible = visible
		if self.owner is None:
			self.map_panel.notifyLayerPanelsChecked(self.name, visible)
		for f in self.features:
			f.setVisible(visible)
		for s in self.sub:
			s.setVisible(visible)
			
	def toggleVisible(self):
		self.setVisible(not self.visible)
		
	def destroy(self):
		if not self.destroyed:
			self.destroyed = True
			for s in self.sub:
				s.destroy()
			self.sub = []
			self.setVisible(False)
			self.features = []
			if self.owner is None:
				self.map_panel.removeLayer(self)
			else:
				self.owner = None
		
	def centerOnMap(self):
		map = self.map_panel.map
		n = len(self.features)
		animate = self.map_panel.animation_enabled
		if n > 0:
			if n == 1:
				JS("""
					latlng = self.group.getBounds().getCenter();
					map.setView(latlng, 16, {animate: animate});
				""")
			else:
				JS("""map.fitBounds(self.group.getBounds(), {animate: animate});""")

	def addGeoJson(self, data):
		"""
		Sets layer geojson data.

		data is a geojson string
		"""
		map = self.map_panel.map
		JS("""
			self.geojson = $wnd['L'].geoJson(JSON.parse(data));
			self.geojson.addTo(map);
		""")


class LayerPanel(VerticalPanel):
	def __init__(self, map):
		VerticalPanel.__init__(self)
		self.map = map
		self.cbs = []
		self.names = {}
		self.map.addLayerPanel(self)
		self.no_layers = HTML(_("Cerca un percorso, una linea o una fermata per mostrarla sulla mappa."))
		self.add(self.no_layers)
		self.setWidth('100%')
		
	def redraw(self):
		if self.no_layers is not None:
			self.remove(self.no_layers)
			self.no_layers = None
		for c in self.cbs:
			self.remove(c)
		self.cbs = []
		self.names = {}
		for l in self.map.layers:
			hp = HorizontalPanel()
			cb = CheckBox(l.label)
			cb.setChecked(l.visible)
			cb.addClickListener(self.onCB)
			cb.layer = l
			hp.add(cb)
			i = Image('close.png')
			i.addClickListener(self.onCloseLayerFactory(l))
			hp.add(i)
			hp.setCellHorizontalAlignment(i, HasAlignment.ALIGN_RIGHT)
			hp.setCellVerticalAlignment(i, HasAlignment.ALIGN_MIDDLE)
			hp.setWidth('100%')
			self.add(hp)
			self.setCellWidth(hp, '100%')
			self.names[l.name] = cb
			self.cbs.append(hp)
			
	def onCloseLayerFactory(self, layer):
		def onCloseLayer():
			layer.destroy()
			
		return onCloseLayer
		
	def onCB(self, source):
		source.layer.setVisible(source.isChecked())
		
	def setChecked(self, name, checked):
		if name in self.names:
			cb = self.names[name]
			cb.setChecked(checked)


class GeoJson:
	def __init__(self, layer, data, visible=True, color='#0000ff'):
		self.layer = layer
		self.visible = False
		JS("""
			var gjstyle = {
				"color": color
			}
			self.geojson = $wnd['L'].geoJson(JSON.parse(data), {style: gjstyle});
			layer.group.addLayer(self.geojson);
		""")
		self.layer.features.append(self)
		if visible:
			self.setVisible(True)

	def setVisible(self, visible):
		self.visible = visible
		map = self.layer.getMap()
		if visible:
			self.geojson.addTo(map)
		else:
			map.removeLayer(self.geojson)



class Marker:
	def __init__(
		self,
		layer,
		point,
		icon_path,
		icon_size=(20, 20),
		infobox=None,
		label=None,
		anchor=None,
		infobox_listener=None,
		visible=True,
		name=None,
		open=False,
		drop_callback=None,
		click_callback=None,
		relative=False,
	):
		self.layer = layer
		self.visible = visible
		self.name = name
		layer.features.append(self)
		map = layer.getMap() if visible else None
		lb = label
		x = point[1]
		y = point[0]
		self.bubble = None
		if anchor is not None:
			ax = anchor[0]
			ay = anchor[1]
			JS("""ajs = new $wnd['L'].point(ax, ay);""")
		else:
			ajs = None
		draggable = False if drop_callback is None else True
		if not relative:
			icon_path = make_absolute(icon_path)
		JS("""
			self.point = new $wnd['L'].latLng(x, y);
			mImg = new $wnd['L'].icon({
				iconUrl: icon_path,
				iconAnchor: ajs
			});
			mOpt = {
				title: lb,
				icon: mImg,
				draggable: draggable,
			};
			self.marker = new $wnd['L'].marker(self.point, mOpt);
			self.marker.addTo(map);
			layer.group.addLayer(self.marker);
		""")
		marker = self.marker
		if drop_callback is not None:
			JS("""
				marker.addEventListener('dragend', function() {
					var latlng = marker.getLatLng();
					drop_callback(latlng.lat, latlng.lng);
				});
			""")
		if infobox is not None or infobox_listener is not None:
			if infobox_listener is None and self.name is not None:
				infobox_listener = self.openBubbleListener
			if infobox_listener is not None:
				infobox = infobox + _('<br/>Caricamento...')
			JS("""
				marker.bindPopup(infobox);
			""")
			self.bubble = marker.getPopup()
			if infobox_listener is not None:
				JS("""
					marker.addEventListener('click', function() {
						infobox_listener(self);
					});
				""")
			if open:
				if infobox_listener is not None:
					infobox_listener(self)
				else:
					marker.openPopup()
		if click_callback is not None:
			JS("""marker.on('click', click_callback);""")

	def openBubbleListener(self, marker):
		self.openBubble()

	def openBubble(self, new_content=None):
		if new_content is not None:
			self.bubble.setContent(new_content)
		elif self.name is not None:
			client.mappa_layer(self.name, get_lang(), JsonHandler(self.onMappaLayerDone))
		self.marker.openPopup()

		
	def onMappaLayerDone(self, res):
		self.bubble.setContent(res)
		
	def closeBubble(self):
		JS("""self.marker.closePopup();""")

	def setVisible(self, visible):
		self.visible = visible
		map = self.layer.getMap()
		if visible:
			self.marker.addTo(map)
		else:
			map.removeLayer(self.marker)

	def setIcon(self, icon_path, anchor=None):
		if anchor is not None:
			ax = anchor[0]
			ay = anchor[1]
			JS("""ajs = new $wnd['L'].point(ax, ay);""")
		else:
			ajs = None
		JS("""
			icon = new $wnd['L'].icon({
				iconUrl: icon_path,
				iconAnchor: ajs
			});
			self.marker.setIcon(icon);
		""")


class Polyline:
	def __init__(self, layer, points, opacity=1, color='#000000', thickness=1, zIndex=0, visible=True):
		pt = list_to_point_array(points)
		self.visible = visible
		self.layer = layer
		layer.features.append(self)
		map = layer.getMap() if visible else None
		JS("""
			var myPolyOpt = {
				color: color,
				opacity: opacity,
				weight: thickness,
			}
			self.myPoly = new $wnd['L'].polyline(pt, myPolyOpt);
			self.myPoly.addTo(map);
			layer.group.addLayer(self.myPoly);
		""")
		
	def setVisible(self, visible):
		self.visible = visible
		map = self.layer.getMap()
		if visible:
			self.myPoly.addTo(map)
		else:
			map.removeLayer(self.myPoly)


class Polygon:
	def __init__(self, layer, points, opacity=1, color='#000000', thickness=1, zIndex=0, visible=True):
		pt = list_to_point_array(points)
		self.visible = visible
		self.layer = layer
		layer.features.append(self)
		map = layer.getMap() if visible else None
		JS("""
			var myPolyOpt = {
				color: color,
				opacity: opacity,
				weight: thickness,
			}
			self.myPoly = new $wnd['L'].polygon(pt, myPolyOpt);
			self.myPoly.addTo(map);
			layer.group.addLayer(self.myPoly);
		""")

	def setVisible(self, visible):
		self.visible = visible
		map = self.layer.getMap()
		if visible:
			self.myPoly.addTo(map)
		else:
			map.removeLayer(self.myPoly)

		
class Geocoder(KeyboardHandler):
	def __init__(self, search, method, map=None, pin_url='partenza_percorso.png', pin_size=(32, 32), lngBox=None, latBox=None, callback=None, anchor=(16, 32)):
		self.search = search
		self.map = map
		self.search.addKeyboardListener(self)
		self.search.addChangeListener(self.onSearchChange)
		self.method = method
		self.lngBox = lngBox
		self.latBox = latBox
		if self.lngBox is not None:
			self.lngBox.addKeyboardListener(self)
			self.lngBox.addChangeListener(self.onLngLatChange)
			self.latBox.addKeyboardListener(self)
			self.latBox.addChangeListener(self.onLngLatChange)
		self.lat = None
		self.lng = None
		self.valid = False
		self.layer = None
		self.marker = None
		self.pin_url = pin_url
		self.pin_size = pin_size
		self.popup = None
		self.callback = callback
		self.anchor = anchor
		
	def onSearchChange(self):
		if not self.valid:
			self.disambiguate()
			
	def onLngLatChange(self):
		self.parseLngLatFromBoxes()
		
	def onKeyUp(self, sender, keycode, modifiers):
		self.search.removeStyleName('validation-error')
		if sender == self.search:
			self.valid = False
			if keycode == 40 and self.popup is not None:
				self.popup.setFocus()
			elif self.popup is not None:
				self.popup.hide()
			if keycode == 13:
				self.disambiguate()
		else:
			self.parseLngLatFromBoxes()
				
	def parseLngLatFromBoxes(self):
		try:
			lat = float(self.latBox.getText())
			self.lng = float(self.lngBox.getText())
			self.lat = lat
			self.valid = True
			self.updateMap()
		except Exception:
			self.valid = False		
			
	def onSearchPopupSelected(self, pk, address):
		self.search.setText(address)
		self.popup.hide()
		self.disambiguate()
			
	def onDisambiguateDone(self, res):
		if res['stato'] == 'OK':
			self.valid = True
			self.lat = res['lat']
			self.lng = res['lng']
			self.search.setText(res['indirizzo'])
			self.updateCoordBoxes()
			self.updateMap()
		elif res['stato'] == 'Ambiguous':
			self.valid = False
			res = [(x, x) for x in res['indirizzi']]
			if self.popup is not None:
				self.popup.update(res)
			else:
				self.popup = SearchPopup(res, self.onSearchPopupSelected)
			self.popup.setPopupPosition(self.search.getAbsoluteLeft(), self.search.getAbsoluteTop() + 20)
			self.popup.show()
		else:
			self.valid = False
			
	def disambiguate(self):
		place = self.search.getText()
		if len(place) >= 3:
			self.method(place, JsonHandler(self.onDisambiguateDone))
	
	def coordToString(self, coord):
		if coord is None:
			return ''
		return "%f" % coord
	
	def updateCoordBoxes(self):
		if self.lngBox is not None:
			self.lngBox.setText(self.coordToString(self.lng))
			self.latBox.setText(self.coordToString(self.lat))
			
	def updateMap(self):
		if self.map is not None:
			if self.layer is not None:
				self.layer.destroy()
			self.layer = Layer('geocoder_layer', 'Indirizzo trovato', self.map)
			m = Marker(
				self.layer,
				(self.lng, self.lat),
				self.pin_url,
				icon_size=self.pin_size,
				drop_callback=self.onDrop,
				anchor=self.anchor,
			)
			self.layer.centerOnMap()
		if self.callback is not None:
			self.callback()
			
	def onDrop(self, lat, lng):
		self.lng = lng
		self.lat = lat
		self.updateCoordBoxes()
		if self.callback is not None:
			self.callback()
		
	def setAddress(self, address, lng, lat):
		self.search.setText(address)
		self.lng = lng
		self.lat = lat
		self.valid = True
		self.updateCoordBoxes()
		self.updateMap()
		
	def getAddress(self):
		if self.valid:
			return self.search.getText(), self.lng, self.lat
		else:
			return None
		
	def setValidationError(self):
		self.search.addStyleName('validation-error')
		
	def destroy(self):
		if self.layer is not None:
			self.layer.destroy()

def get_location(callback, callback_error=None):
	JS("""
		if (navigator.geolocation) {
			navigator.geolocation.getCurrentPosition(function(position) {
				lng = position.coords.longitude;
				lat = position.coords.latitude;
				callback(lng, lat);
			}, callback_error);
		}
  """)
