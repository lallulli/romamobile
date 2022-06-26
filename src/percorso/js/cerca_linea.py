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

from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.ScrollPanel import ScrollPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.VerticalSplitPanel import VerticalSplitPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.FlowPanel import FlowPanel
from pyjamas.ui.DisclosurePanel import DisclosurePanel
from pyjamas.ui.TabPanel import TabPanel
from pyjamas.ui.DialogBox import DialogBox
from pyjamas.ui.Grid import Grid
from pyjamas.ui.Frame import Frame
from pyjamas.ui.TextBox import TextBox
from pyjamas.ui.TextArea import TextArea
from pyjamas.ui.HTML import HTML
from pyjamas.ui.HTMLPanel import HTMLPanel
from pyjamas.ui.Anchor import Anchor
from pyjamas.ui.Label import Label
from pyjamas.ui.CheckBox import CheckBox
from pyjamas.ui.ListBox import ListBox
from pyjamas.ui.Button import Button
from pyjamas.ui.RadioButton import RadioButton
from pyjamas.ui.PopupPanel import PopupPanel
from pyjamas.ui.KeyboardListener import KeyboardHandler
from pyjamas.ui.FocusListener import FocusHandler
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
from __pyjamas__ import JS

from prnt import prnt
from util import StyledFixedColumnFlexTable, HTMLFlowPanel, DP, VP, HP, GP, GPh, SP, DeferrablePanel, ScrollAdaptivePanel
from util import get_checked_radio, HidingPanel, ValidationErrorRemover, MyAnchor, LoadingButton
from util import FavSearchBox, wait_start, wait_stop, getdefault, _, get_lang, PausableTimer, PaginatedPanelPage
from util import PreferitiImage, LuogoPanel, CheckList, WebNotification, LocalNotification, DisturbingMessageDialog
from util import ButtonsPanel, addClickListener, WaitingHandler, JsonInteractiveHandler
from datetime import date, time, datetime, timedelta
from Calendar import Calendar, DateField, TimeField
from map import MapPanel, Layer, LayerPanel, Marker
from globals import base_url, make_absolute, flavor


from DissolvingPopup import DissolvingPopup
from util import JsonHandler, redirect


client = JSONProxy(base_url + '/json/', [
	'paline_smart_search',
	'urldecode',
	'paline_percorso_fermate',
	'paline_orari',
	'servizi_autocompleta_indirizzo',
	'paline_previsioni',
	'paline_preferiti',
	'paline_refresh_notifica_arrivo_bus',
	'paline_imposta_notifica_arrivo_bus',
])

INTERVALLO_TIMER = 30000

class CLLuogoPanel(LuogoPanel):
	def activateMarker(self):
		self.owner.setActiveMarker(None)

class PalinaPanel(HorizontalPanel):
	def __init__(self, owner, p, img='/paline/s/img/palina.png'):
		HorizontalPanel.__init__(self)
		self.id_palina = p['id_palina']
		self.setWidth('100%')
		self.addStyleName('palina')
		self.owner = owner
		i = Image(make_absolute(img))
		i.addStyleName('palina-img')
		self.add(i)
		vp = VerticalPanel()
		self.add(vp)
		titolo = HTMLFlowPanel()
		vp.add(titolo)
		if 'nascosta' in p and p['nascosta']:
			self.nascosta = True
			self.setVisible(False)
		else:
			self.nascosta = False
		distanza = getdefault(p, 'distanza_arrotondata', '')
		if distanza != '':
			distanza = _('a %s') % distanza
		titolo.addHtml("<b>%s</b><br />%s %s" % (p['nome'], self.id_palina, distanza), 'a')
		titolo.addStyleName('h2')
		titolo.addStyleName('clickable')
		titolo.getElement().onclick = owner.onPalinaFactory(self.id_palina, waiting_handler=WaitingHandler(widgets=[self]))
		if 'linee_info' in p:
			for l in p['linee_info']:
				linea = HTMLFlowPanel()
				linea.addStyleName('palinalinea')
				linea.addStyleName('clickable')
				linea.getElement().onclick = owner.onLineaFactory(l['id_linea'], self.id_palina, waiting_handler=WaitingHandler(widgets=[linea]))
				linea.add(Image(make_absolute('/paline/s/img/bus.png')))
				linea.addHtml(l['id_linea'], 'a x2')
				linea.addHtml(l['direzione'])
				vp.add(linea)
		if 'linee_extra' in p and len(p['linee_extra']) > 0:
			altre = HTMLFlowPanel()
			altre.addStyleName('palinalinea')
			altre.add(Image(make_absolute('/paline/s/img/bus.png')))
			vp.add(altre)
			altre.addHtml(_('Altre linee:&nbsp;'))
			for l in p['linee_extra']:
				altre.addAnchor(l, owner.onLineaFactory(l))
				altre.addHtml("&nbsp;")
				
	def mostra(self):
		self.setVisible(True)

class RiepilogoPalinaPanel(ScrollPanel, PaginatedPanelPage):
	def __init__(self, owner, id_palina, arrivi, direzioni):
		ScrollPanel.__init__(self)
		self.owner = owner
		self.id_palina = id_palina
		self.arrivi = arrivi
		self.direzioni = direzioni
		self.setHeight('136px')
		self.init_done = False
		self.marker = None

	def lazy_init(self):
		self.init_done = True
		self.base = VP(
			self,
			sub = [
				{
					'class': HP,
					'sub': [
						{
							'class': HTML,
							'name': 'direzioni',
							'style': 'vskip-s',
						},
						{
							'class': Image,
							'args': ['alert.png'],
							'width': '18px',
							'call_addClickListener': ([self.onAlert], {}),
							'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
						},
					]
				},
				{
					'class': GP,
					'column_count': 4,
					'name': 'linee',
					'sub': [],
					'width': None,
					'style': 'vskip-s',
				},
			],
			add_to_owner=True,
		)

		self.linee = {}
		self.base.by_name('direzioni').setHTML(_('<b>Direzioni:</b> ') + self.direzioni)
		gp = self.base.by_name('linee')
		for l in self.arrivi:
			a = MyAnchor()
			h = HTML()
			self.linee[l['linea']] = (a, h)
			gp.add(a, center=HasAlignment.ALIGN_RIGHT)
			gp.add(h, center=HasAlignment.ALIGN_LEFT)

	def onAlert(self):
		NotificaLineeDialog(self.owner, self.id_palina, self.linee.keys())

	def notifyShow(self):
		if not self.init_done:
			self.lazy_init()
		self.lazy_update()

	def lazy_update(self):
		arrivi = self.arrivi
		for l in arrivi:
			msg = l['linea']
			if msg in self.linee:
				a, html = self.linee[msg]
				h = HTML("<b>" + msg + "</b>")
				a.setWidget(h)
				if 'id_percorso' in l:
					a.addClickListener(self.owner.onPercorsoFactory(l['id_percorso'], l['id_veicolo'], id_palina=self.id_palina))
				else:
					a.addClickListener(self.owner.onLineaFactory(l['linea'], self.id_palina))
				if getdefault(l, 'disabilitata', False):
					msg = _("Non disp.")
				elif getdefault(l, 'non_monitorata', False):
					msg = _("Non monitor.")
				elif getdefault(l, 'nessun_autobus', False):
					msg = _("Nessun bus")
				else:
					msg = l['annuncio']
					# partenza = getdefault(l, 'partenza', '')
					# if partenza != '':
					# 	msg += _(" (p. %s)") % partenza
				html.setHTML(msg)

	def update(self, arrivi):
		self.arrivi = arrivi
		if self.isShown():
			self.lazy_update()

	def onDettagli(self):
		self.owner.cercaLinea(self.id_palina, set_tab=True)

	def setMarker(self, marker):
		self.marker = marker

	def activateMarker(self):
		self.owner.setActiveMarker(self.marker)

	def onPartiDa(self):
		self.owner.cercaPercorsoDa("fermata:%s" % self.id_palina)

	def onArrivaA(self):
		self.owner.cercaPercorsoA("fermata:%s" % self.id_palina)

	def onCercaLuogo(self):
		self.owner.cercaLuogo("fermata:%s" % self.id_palina)

	def getMenu(self):
		return [
			{
				'id': 'dettagli',
				'text': _('Dettagli fermata'),
				'listener': self.onDettagli,
			},
			{
				'id': 'parti_da',
				'text': _('Parti da questa fermata'),
				'listener': self.onPartiDa,
			},
			{
				'id': 'arriva_a',
				'text': _('Arriva a questa fermata'),
				'listener': self.onArrivaA,
			},
			{
				'id': 'cerca_luogo',
				'text': _('Cerca luoghi vicini'),
				'listener': self.onCercaLuogo,
			},
		]



class PercorsoPanel(HTMLFlowPanel):
	def __init__(self, owner, p):
		HTMLFlowPanel.__init__(self)
		self.owner = owner
		self.addStyleName('percorsolinea')
		self.add(Image(make_absolute('/paline/s/img/bus.png')))
		if 'arrivo' in p:
			p['direzione'] = p['arrivo']
		if p['descrizione'] is not None and p['descrizione'] != '':
			self.addAnchor(p['descrizione'], owner.onPercorsoFactory(p['id_percorso']))
		else:
			self.addHtml(p['id_linea'], 'x2')
			if p['carteggio_dec'] != '':
				self.addHtml('%s<br />(%s)' % (p['direzione'], p['carteggio_dec']))
			else:
				self.addHtml(p['direzione'])
		self.addStyleName('clickable-a')
		self.getElement().onclick =	owner.onPercorsoFactory(p['id_percorso'], waiting_handler=WaitingHandler(widgets=[self]))


class OrarioPanel(VerticalPanel):
	def __init__(self, owner, o, id_percorso):
		HorizontalPanel.__init__(self)
		self.owner = owner
		self.giorno = o['giorno']
		self.orari = None
		self.id_percorso = id_percorso
		a = MyAnchor()
		a.setWidget(HTML(o['nome']))
		a.addClickListener(self.onOrario)
		self.add(a)

	def onOrario(self):
		if self.orari is not None:
			self.remove(self.orari)
			self.removeStyleName('orari-open')
			self.orari = None
		else:
			client.paline_orari(self.id_percorso, self.giorno, get_lang(), JsonInteractiveHandler(self.onOrarioDone))
			self.addStyleName('orari-open')
			
	def onOrarioDone(self, res):
		self.orari = VerticalPanel()
		trovato = False
		for h in res['orari_partenza']:
			m = h['minuti']
			if len(m) > 0:
				self.orari.add(HTML(_('<b>%s:</b> %s') % (
					h['ora'],
					' '.join(m),
				)))
				trovato = True
		if not trovato:
			self.orari.add(HTML(_('Nella giornata selezionata il percorso non &egrave; attivo.')))
		self.add(self.orari)

class OrariPanel(VerticalPanel):
	def __init__(self, res):
		VerticalPanel.__init__(self)
		self.res = res
		if res['no_orari']:
			self.add(HTML(res['note_no_orari']))
		else:
			opv = res['orari_partenza_vicini']
			if len(opv) == 0:
				pp = "-"
			else:
				pp = opv = " ".join([o[11:16] for o in opv])
			self.add(HTML(_('<b>Prossime partenze</b>: ') + pp))
			self.tutti = MyAnchor()
			self.tutti.setWidget(HTML(_('Tutte le partenze')))
			self.tutti.addStyleName('vskip-s')
			self.tutti.addClickListener(self.onTutti)
			self.add(self.tutti)

	def onTutti(self):
		self.remove(self.tutti)
		skip = True
		for o in self.res['giorni']:
			op = OrarioPanel(self, o, self.res['id_percorso'])
			if skip:
				op.addStyleName('vskip-s')
				skip = False
			self.add(op)



class CercaLineaPanel(ScrollAdaptivePanel, KeyboardHandler, FocusHandler, DeferrablePanel):
	def __init__(self, owner):
		ScrollAdaptivePanel.__init__(self)
		DeferrablePanel.__init__(self)
		KeyboardHandler.__init__(self)
		self.owner = owner
		self.map = None
		self.base = VP(
			self,
			[
				{
					'class': VP,
					'style': 'indicazioni',
					'sub': [
	
						{
							'class': Label,
							'args': [_('Fermata, linea o indirizzo')],
							'style': 'indicazioni-h1',
							'height': None,
						},			
						{
							'class': HP,
							'sub': [
								{
									'class': HP,
									'width': '90%',
									'sub': [							
										{
												'class': FavSearchBox,
												'name': 'query',
												'call_addKeyboardListener': ([self], {}),
												'args': [client.servizi_autocompleta_indirizzo, self.onCerca, 0, 100, False],
										},
										{
											'class': HP,
											'call_setVisible': ([False], {}),
											'name': 'query_list_holder',
											'sub': [
												{
													'class': ListBox,
													'name': 'query_list',
													'width': '100%',
												},
											]
										},
									],
								},
								{
									'class': Button,
									'args': ['X', self.onChiudiQuery],
									'width': '40px',
									'style': 'close-button',
								},
								# {
								# 	'class': LoadingButton,
								# 	'args': [_('Cerca'), self.onCerca],
								# 	'width': '30%',
								# 	'name': 'button',
								# },
							]
						},								
		
					]
				},

		
						
				{
					'class': SP,
					'name': 'risultati_holder',
					'sub': [],
				},
			],
			add_to_owner=True,						
		)
		
		self.risultati = None
		self.cl_layer = None
		self.modo_realtime = None
		self.pannelli_real_time = None
		self.id_veicolo_selezionato = None
		self.id_veicolo_preselezionato = None
		self.id_percorso = None
		self.id_palina = None
		self.timer = PausableTimer(notify=self.onTimer)
		self.timer_riepilogo = PausableTimer(notify=self.onTimerRiepilogo)
		self.query_riepilogo = None
		self.query_riepilogo_chiusa = None
		self.pannello_riepilogo = None
		self.main_marker = None
		self.active_marker = None
		self.paline_riepilogo = {}
		self.jump_to_result = False
		
	def availableParams(self):
		return [
			'query',
			'id_percorso',			
			'cl',
		]
		
	def setParam(self, param, value):
		if param == 'query':
			self.base.by_name('query').setText(value)	
		if param == 'cl':
			self.owner.setTabMappaLinea()
			q = self.base.by_name('query').getText()
			if q is not None:
				self.cercaLinea(q, set_tab=True)
		if param == 'id_percorso':
			self.cercaPercorso(value, True)	
		
	def ripristinaWidgets(self):
		for x, x_list, x_holder in [self.getWidgets()]:
			x.removeStyleName('validation-error')
			if not x.getVisible():
				x.setText(x_list.getSelectedItemText()[0])
				x_holder.setVisible(False)
				x.setVisible(True)
		
	def onChange(self, el):
		el.removeStyleName('validation-error')

	def setMap(self, map):
		self.map = map
		self.map.addRightClickOption(_("Fermate vicine"), self.onRightClick)
		
	def onRightClick(self, lat, lng):
		query = self.base.by_name('query')
		q = 'punto:(%0.4f,%0.4f)' % (lat, lng)
		query.setText(q)
		self.owner.setTabMappaLinea()
		self.createClLayer()
		def add_marker():
			m = Marker(
				self.cl_layer,
				(lng, lat),
				make_absolute('/paline/s/img/arrivo_percorso.png'),
				anchor=(16, 32),
				icon_size=(32, 32),
			)
		self.owner.map_tab.do_or_defer(add_marker)
		self.cercaLinea(q, from_map=True)

	def onKeyDown(self, sender, keycode, modifiers):
		if keycode == 13:
			self.onCerca()
			
	def onPercorsoFactory(self, id_percorso, id_veicolo=None, waiting_handler=None, id_palina=None):
		def onPercorso(source):
			if id_palina is not None:
				self.id_palina = id_palina
			self.id_veicolo_selezionato = id_veicolo
			self.cercaPercorso(id_percorso, reset_palina=False, waiting_handler=waiting_handler)
		return onPercorso
	
	def onLineaFactory(self, id_linea, id_palina=None, waiting_handler=None):
		def onLinea(source):
			if id_palina is None:
				query = id_linea
			else:
				query = "percorsi:%s:%s" % (id_linea, id_palina)
			self.id_palina = id_palina
			self.cercaLinea(query, set_tab=True, waiting_handler=waiting_handler)
		return onLinea
	
	def onPalinaFactory(self, id_palina, waiting_handler=None):
		def onPalina(source):
			self.dettaglioPalina(id_palina, waiting_handler=waiting_handler)
		return onPalina

	def onCercaLineaFactory(self, query, set_tab=True):
		def onCercaLinea(source):
			self.cercaLinea(query, set_tab)
		return onCercaLinea

	def onMostraTuttePaline(self):
		for p in self.paline_nascoste:
			p.mostra()
		self.mostra_tutto.setVisible(False)
	
	def createClLayer(self):
		# self.owner.setTabMappaLinea()
		if self.cl_layer is not None:
			self.cl_layer.destroy()
		self.map.hideAllLayers()
		self.cl_layer = Layer('cp_layer', _('Fermate trovate'), self.map)
		
	def dettaglioPalina(self, id_palina, dettaglio=None, waiting_handler=None):
		wait_start()
		self.resetPannelliRealtime()
		self.modo_realtime = 'palina'
		self.id_palina = id_palina
		# self.owner.setTabMappa()
		def load_layer():
			self.map.loadNewLayer(id_palina, 'palina-singola', id_palina)
		self.owner.map_tab.do_or_defer(load_layer)
		if dettaglio is None:
			client.paline_previsioni(id_palina, get_lang(), JsonInteractiveHandler(self.onDettaglioPalinaDone, waiting_handler=waiting_handler))
		else:
			self.onDettaglioPalinaDone(dettaglio)


	def _converti_dotazioni_bordo(self, x, dotaz):
		if x[dotaz]:
			x[dotaz + 'alt'] = dotaz[0].upper()
			x[dotaz] = dotaz
		else:
			x[dotaz + 'alt'] = ' '
			x[dotaz] = 'blank'

	def onDettaglioPalinaDone(self, res):
		self.aggiornaArrivi(res)
		wait_stop()
		self.startTimer()

	def aggiornaArrivi(self, res):
		wait_stop()
		risultati_holder = self.base.by_name('risultati_holder')
		if self.risultati is not None:
			risultati_holder.remove(self.risultati)

		self.risultati = DP(
			None,
			[
				{
					'class': VP,
					'style': 'indicazioni',
					'name': 'dettaglio',
					'height': None,
					'sub': [
						{
							'class': HP,
							'sub': [
								{
									'class': Label,
									'args': ['%s (%s)' % (res['nome'], self.id_palina)],
									'style': 'indicazioni-h1',
									'height': None,
								},
								{
									'class': Image,
									'args': ['alert.png'],
									'width': '18px',
									'call_addClickListener': ([self.onAlert], {}),
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
								},
								{
									'class': HTML,
									'args': ['&nbsp;&nbsp;']
								},
								{
									'class': PreferitiImage,
									'args': ['P', self.id_palina, '%s (%s)' % (res['nome'], self.id_palina), res['esiste_preferito'], client.paline_preferiti],
									'width': '18px',
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
								},
								{
									'class': HTML,
									'args': ['&nbsp;&nbsp;']
								},
								{
									'class': Image,
									'args': ['reload.png'],
									'width': '18px',
									'call_addClickListener': ([self.onReload], {}),
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
								},
							]
						},
						{
							'class': HTML,
							'args': [_("Linee della fermata")],
							'style': 'indicazioni-h2',
							'height': None,
						},
						{
							'class': GP,
							'column_count': 2,
							'name': 'linee',
							'sub': [],
							'style': 'palinelinea',
						},
						{
							'class': HTML,
							'args': [_("Tutti gli arrivi")],
							'style': 'indicazioni-h2',
							'height': None,
							'name': 'arrivi_label'
						},
						{
							'class': VP,
							'name': 'arrivi',
							'sub': [],
						},
					]
				}
			],
			title=_('Risultati'),
			style='indicazioni'
		)

		risultati_holder.add(self.risultati)

		# Primi arrivi
		gp = self.risultati.by_name('linee')
		primi = res['primi_per_palina'][0]['arrivi']
		self.linee = []
		linee_count = 0
		formatter = gp.getRowFormatter()
		for l in primi:
			msg = l['linea']
			self.linee.append(msg)
			h = HTML(msg)
			h.addStyleName('x2')
			h.addStyleName('clickable-a')
			wh = WaitingHandler()
			if 'id_percorso' in l:
				clicklistener = self.onPercorsoFactory(l['id_percorso'], l['id_veicolo'], waiting_handler=wh)
			else:
				clicklistener = self.onLineaFactory(l['linea'], self.id_palina, waiting_handler=wh)
			h.getElement().onclick = clicklistener
			gp.add(h, center=HasAlignment.ALIGN_RIGHT)
			wh.addElements([formatter.getElement(linee_count)])
			if getdefault(l, 'disabilitata', False):
				msg = _("Non disponibile")
			elif getdefault(l, 'non_monitorata', False):
				msg = _("Non monitorata")
			elif getdefault(l, 'nessun_autobus', False):
				msg = _("Nessun autobus")
			else:
				msg = l['annuncio']
				# partenza = getdefault(l, 'partenza', '')
				# if partenza != '':
				# 	msg += _(" (partenza %s)") % partenza
			h = HTML(msg)
			h.addStyleName('clickable')
			h.getElement().onclick = clicklistener
			gp.add(h, center=HasAlignment.ALIGN_LEFT)
			linee_count += 1

		# Tutti gli arrivi
		tutti = res['arrivi']
		self.risultati.by_name('arrivi_label').setVisible(len(tutti) > 0)
		arrivi = self.risultati.by_name('arrivi')
		banda = 0
		for l in tutti:
			hp = HorizontalPanel()
			hp.setWidth('100%')
			hp.addStyleName('banda%d' % banda)
			hp.addStyleName('clickable')
			hp.getElement().onclick = self.onPercorsoFactory(l['id_percorso'], l['id_veicolo'], waiting_handler=WaitingHandler(widgets=[hp]))
			banda = (banda % 2) + 1
			h = HTML(l['linea'])
			h.addStyleName('x2')
			h.addStyleName('a')
			h.addStyleName('lineatutti')
			hp.add(h)
			h.setWidth('50px')
			hp.setCellWidth(h, '50px')
			vp = VerticalPanel()
			vp.setWidth('100%')
			msg = l['annuncio']
			# partenza = getdefault(l, 'partenza', '')
			# if partenza != '':
			# 	msg += _(" (partenza %s)") % partenza
			vp.add(HTML(msg))
			hp2 = HorizontalPanel()
			vp.add(hp2)
			hp.add(vp)
			for dotaz in ['pedana', 'meb', 'aria', 'moby']:
				self._converti_dotazioni_bordo(l, dotaz)
				hp2.add(Image(make_absolute('/paline/s/img/%s.gif' % l[dotaz])))
			c = getdefault(l, 'carteggi', '')
			if c != '':
				hp2.add(HTML("&nbsp;(%s)" % c))

			arrivi.add(hp)
			arrivi.setCellWidth(hp, '100%')


	def cercaLinea(self, query, set_input=False, set_tab=False, from_map=False, jump_to_result=False, waiting_handler=None):
		if set_tab:
			self.owner.setTabLineaMappa()
		if set_input:
			self.base.by_name('query').setText(query)
		# sb = self.base.by_name('button')
		# sb.start()
		# if waiting_handler is None:
		# 	waiting_handler = WaitingHandler()
		# waiting_handler.addStopCallbacks([sb.stop])
		wait_start()
		self.jump_to_result = jump_to_result
		if from_map:
			callback = self.onCercaDoneFromMap
		else:
			callback = self.onCercaDone
		client.paline_smart_search(query, get_lang(), JsonInteractiveHandler(callback, waiting_handler=waiting_handler))
			
	def onCerca(self):
		self.ripristinaWidgets()
		self.cercaLinea(self.base.by_name('query').getText())
		
	def cercaPercorso(self, id_percorso, set_tab=False, su_mappa=False, reset_palina=True, waiting_handler=None):
		wait_start()
		if reset_palina:
			self.id_palina = None
			self.id_veicolo_selezionato = None
		if su_mappa:
			self.owner.hide(False)
		else:
			self.owner.setTabLineaMappa()
		client.paline_percorso_fermate(
			id_percorso,
			self.id_veicolo_selezionato,
			get_lang(),
			JsonInteractiveHandler(self.onCercaPercorsoDone, waiting_handler=waiting_handler)
		)
		def load_layer():
			self.map.loadNewLayer(id_percorso, 'percorso', id_percorso)
		self.owner.map_tab.do_or_defer(load_layer)

		
	def onCercaPercorsoDone(self, res):
		wait_stop()
		self.resetPannelliRealtime()
		self.modo_realtime = 'percorso'
		risultati_holder = self.base.by_name('risultati_holder')
		if self.risultati is not None:
			risultati_holder.remove(self.risultati)

		p = res['percorso']
		if p['descrizione'] is not None and p['descrizione'] != '':
			desc = p['descrizione']
		else:
			desc = _('%(id_linea)s %(carteggio_dec)s direz. %(arrivo)s') % p
		
		self.risultati = DP(
			None,
			[ 
				{
					'class': VP,
					'style': 'indicazioni',
					'name': 'dettaglio',
					'sub': [
						{
							'class': HP,
							'sub': [
								{
									'class': Label,
									'args': [desc],
									'style': 'indicazioni-h1',
									'height': None,
								},
								{
									'class': Image,
									'args': ['reload.png'],
									'width': '20px',
									'call_addClickListener': ([self.onReload], {}),
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
								},
							]
						},
						{
							'class': Label,
							'args': [_('Partenze da capolinea')],
							'style': 'indicazioni-h2',
							'height': None,
						},
						{
							'class': OrariPanel,
							'name': 'orari',
							'args': [res],
						},
						{
							'class': Label,
							'args': [_('Fermate')],
							'style': 'indicazioni-h2',
							'height': None,
						},
						{
							'class': HTML,
							'args': [_("<b>Veicolo: </b>Seleziona un bus")],
							'style': 'indicazioni',
							'height': None,
							'name': 'veicolo_selezionato',
						},
						{
							'class': GPh,
							'column_count': 4,
							# Traffico, Icona Fermata/Bus, Tempo di arrivo, Nome fermata
							'name': 'paline',
							'row_id_prefix': 'palina-',
							'table_class': 'palinelinea',
						},
						{
							'class': Label,
							'name': 'altri_label',
							'args': [_('Altri percorsi della linea')],
							'style': 'indicazioni-h2',
							'height': None,
						},
						{
							'class': VP,
							'args': [],
							'name': 'altri',
							'height': None,
						},
						{
							'class': Label,
							'args': [_('Gestore')],
							'style': 'indicazioni-h2',
							'height': None,
						},
						{
							'class': HTML,
							'name': 'gestore',
							'args': [""],
							'height': None,
						},
					]
				}		
			],
			title=_('Risultati'),
			style='indicazioni'
		)
		risultati_holder.add(self.risultati)

		
		paline = self.risultati.by_name('paline')
		n = len(res['fermate'])

		self.pannelli_real_time = []
		self.id_percorso = res['id_percorso']

		ps = {}
		i = 0
		for p in res['fermate']:
			if not p['soppressa']:
				id_palina = p['id_palina']
				stp = 'stp-%s' % id_palina
				imgp = 'imgp-%s' % id_palina
				tap = 'tap-%s' % id_palina
				pal = 'pal-%s' % id_palina
				paline.add(td_id=stp)
				paline.add(td_id=imgp)
				paline.add(td_id=tap)
				paline.add(p['nome_ricapitalizzato'], td_id=pal, td_class='clickable-a')
				ps[id_palina] = [pal, "palina-%d" % i]
				i += 1

		paline.render()

		for id_palina in ps:
			els = ps[id_palina]
			if id_palina == self.id_palina:
				DOM.getElementById(els[1]).className += " palina-corrente"
			w = WaitingHandler(el_ids=[els[1]])
			addClickListener(els[0], self.onPalinaFactory(id_palina, waiting_handler=w))


		self.risultati.by_name('gestore').setHTML(_('La linea %s &egrave; gestita da %s.') % (
			res['percorso']['id_linea'],
			res['percorso']['gestore'],
		))

		altri = self.risultati.by_name('altri')
		self.risultati.by_name('altri_label').setVisible(len(res['percorsi']) > 1)
		for p in res['percorsi']:
			if p['id_percorso'] != self.id_percorso:
				percorso = PercorsoPanel(self, p)
				altri.add(percorso)

		self.onInfoRealtime(res)
		self.startTimer()

	def onInfoRealtime(self, res):
		wait_stop()
		i = 0
		n = len(res['fermate'])

		def onVeicolo(id_veicolo, waiting_handler=None):
			def f():
				wait_start()
				self.id_veicolo_preselezionato = id_veicolo
				client.paline_percorso_fermate(
					self.id_percorso,
					id_veicolo,
					get_lang(),
					JsonInteractiveHandler(self.onInfoRealtime, waiting_handler=waiting_handler)
				)

			return f

		if self.id_veicolo_preselezionato is not None:
			self.id_veicolo_selezionato = self.id_veicolo_preselezionato
			self.id_veicolo_preselezionato = None
			self.risultati.by_name('veicolo_selezionato').setHTML('<b>Veicolo:</b> %s' % self.id_veicolo_selezionato)

		for p in res['fermate']:
			if not p['soppressa']:
				id_palina = p['id_palina']
				stp = DOM.getElementById('stp-%s' % id_palina)
				imgp = DOM.getElementById('imgp-%s' % id_palina)
				tap = DOM.getElementById('tap-%s' % id_palina)
				if i > 0:
					stp.className = 'stato%s' % p['stato_traffico']
				else:
					stp.className = 'stato-none'
				if 'veicolo' in p:
					id_veicolo = p['veicolo']['id_veicolo']
					if id_veicolo == self.id_veicolo_selezionato:
						img = make_absolute('/paline/s/img/bus_hl.png')
					else:
						img = make_absolute('/paline/s/img/bus.png')
				else:
					img = make_absolute('/paline/s/img/%s_arrow.gif' % ('down' if i < n - 1 else 'stop'))

				DOM.setInnerHTML(imgp,'<img src="%s" />' % img)
				imgp.className = ''
				imgp.onclick = None
				if 'veicolo' in p and id_veicolo != self.id_veicolo_selezionato:
					imgp.className = 'clickable'
					imgp.onclick = onVeicolo(id_veicolo, waiting_handler=WaitingHandler(els=[imgp]))

				ta = ''
				if 'orario_arrivo' in p:
					ta = p['orario_arrivo']
				DOM.setInnerHTML(tap, ta)
				i += 1


				
	def onCercaErrore(self, el):
		x, x_list, x_holder = self.getWidgets()
		if el['tipo'] == 'Indirizzo ambiguo':
			x.setVisible(False)
			x_holder.setVisible(True)
			x_list.addStyleName('validation-error')
			x_list.clear()
			for i in el['indirizzi']:
				x_list.addItem(i)
		else:
			x.addStyleName('validation-error')
			
	def getWidgets(self):
		x = self.base.by_name('query')
		x_list = self.base.by_name('query_list')
		x_holder = self.base.by_name('query_list_holder')
		return x, x_list, x_holder			
			
	def onChiudiQuery(self):
		x, x_list, x_holder = self.getWidgets()
		x_holder.setVisible(False)
		x.setVisible(True)
		x.setText('')
		x.setFocus()

	def resetPannelliRealtime(self):
		self.modo_realtime = None
		self.timer.cancel()

	def onAlert(self):
		NotificaLineeDialog(self, self.id_palina, self.linee)

	def onReload(self):
		wait_start()
		self.aggiornaOra(interactive=True)

	def aggiornaOra(self, interactive=False):
		if self.modo_realtime is not None:
			if self.modo_realtime == 'percorso':
				client.paline_percorso_fermate(
					self.id_percorso,
					self.id_veicolo_selezionato,
					get_lang(),
					JsonHandler(self.onInfoRealtime) if not interactive else JsonInteractiveHandler(self.onInfoRealtime)
				)
			elif self.modo_realtime == 'palina':
				client.paline_previsioni(
					self.id_palina,
					get_lang(),
					JsonHandler(self.aggiornaArrivi) if not interactive else JsonInteractiveHandler(self.aggiornaArrivi)
				)
			else:
				wait_stop()
			self.timer.schedule(INTERVALLO_TIMER)

	def onTimer(self):
		self.aggiornaOra()

	def onTimerRiepilogo(self):
		if self.query_riepilogo is not None:
			client.paline_smart_search(self.query_riepilogo, get_lang(), JsonHandler(self.onTimerRiepilogoDone))
			self.timer_riepilogo.schedule(INTERVALLO_TIMER)

	def onTimerRiepilogoDone(self, res):
		for p in res['paline_extra']:
			id_palina = p['id_palina']
			if id_palina in self.paline_riepilogo:
				self.paline_riepilogo[id_palina].update(p['primi_arrivi'])

	def onRiepilogoClose(self):
		self.timer_riepilogo.cancel()
		self.query_riepilogo_chiusa = self.query_riepilogo
		self.query_riepilogo = None

	def startTimer(self):
		self.timer.schedule(INTERVALLO_TIMER)

	def onCercaDoneFromMap(self, res):
		self.onCercaDone(res, True)

	def paginatedSelectFactory(self, paginated, index):
		def callback():
			paginated.selectIndex(index)
		return callback

	def closePopups(self):
		if self.main_marker is not None:
			self.main_marker.closeBubble()

	def setActiveMarker(self, marker):
		if self.query_riepilogo is None:
			self.owner.setBottomWidget(self.pannello_riepilogo, self.onRiepilogoClose)
			self.pannello_riepilogo.setVisible(True)
			self.query_riepilogo = self.query_riepilogo_chiusa
			self.onTimerRiepilogo()
		if self.active_marker is not None:
			self.active_marker.setIcon('palina_off.png', (0, 27))
		self.active_marker = marker
		if marker is not None:
			self.active_marker.setIcon('palina_on.png', (0, 27))
			self.closePopups()
			self.map.centerMarkers([self.active_marker, self.main_marker])
		else:
			self.cl_layer.centerOnMap()

	def cercaPercorsoDa(self, da):
		self.owner.cercaPercorsoDa(da)

	def cercaPercorsoA(self, a):
		self.owner.cercaPercorsoA(a)

	def cercaLuogo(self, query):
		self.owner.cercaLuogo(query)

		
	def onCercaDone(self, res, from_map=False):
		if 'percorso' in res:
			self.owner.setTabLineaMappa()
			return self.onCercaPercorsoDone(res['percorso'])
		self.resetPannelliRealtime()
		wait_stop()
		risultati_holder = self.base.by_name('risultati_holder')
		if self.risultati is not None:
			risultati_holder.remove(self.risultati)
			
		if res['errore']:
			self.onCercaErrore(res)
			return
		
		tipo = res['tipo']
		if tipo == 'Palina':
			self.owner.setTabCercaLinea()
			# if from_map:
			# 	self.owner.setTabMappaLinea()
			# else:
			# 	self.owner.setTabCercaLinea()
			self.dettaglioPalina(res['id_palina'], dettaglio=res['dettaglio'])
			return
		
		elif tipo == 'Indirizzo ambiguo':
			self.onCercaErrore(res)
		self.risultati = DP(
			None,
			[ 
				{
					'class': VP,
					'style': 'indicazioni',
					'name': 'dettaglio',
					'sub': [			
					]
				}		
			],
			title=_('Risultati'),
			style='indicazioni'
		)
		self.map.hideAllLayers()
		self.risultati.setOpen(True)
		dettaglio = self.risultati.by_name('dettaglio')
		risultati_holder.add(self.risultati)
		
		self.paline_nascoste = []

		if len(res['paline_extra']) > 0 or len(res['paline_semplice']) > 0:
			h = HTML(_('Fermate trovate'))
			h.addStyleName('indicazioni-h1')
			dettaglio.add(h)

		for p in res['paline_semplice']:
			palina = PalinaPanel(self, p)
			dettaglio.add(palina)
			if palina.nascosta:
				self.paline_nascoste.append(palina)

		if 'lng' in res:
			self.pannello_riepilogo = self.owner.creaPannelloRiepilogo(height='150px', close_callback=self.onRiepilogoClose)
			self.createClLayer()

			def on_cpda():
				self.cercaPercorsoDa(res['ricerca'])
			def on_cpa():
				self.cercaPercorsoA(res['ricerca'])
			def on_cl():
				self.pannello_riepilogo.selectIndex(1)
			def on_cr():
				self.cercaLuogo(res['ricerca'])
			luogo_panel = CLLuogoPanel(self, on_cpda, on_cpa, on_cl, on_cr)
			self.pannello_riepilogo.add(luogo_panel, luogo_panel.activateMarker, title=res['ricerca'])
			self.paline_riepilogo = {}
			self.query_riepilogo = res['query']
			self.timer_riepilogo.schedule(INTERVALLO_TIMER)
			def add_marker():
				m = Marker(
					self.cl_layer,
					(res['lng'], res['lat']),
					make_absolute('/paline/s/img/partenza_percorso.png'),
					icon_size=(32, 32),
					anchor=(16, 32),
					drop_callback=self.onRightClick,
					click_callback=self.paginatedSelectFactory(self.pannello_riepilogo, 0),
				)
				self.main_marker = m
			self.owner.map_tab.do_or_defer(add_marker)

		elif len(res['paline_extra']) > 0:
			# Ricerca di fermate per nome, non per indirizzo: mostra i risultati in forma testuale
			self.owner.setTabLineaMappa()

		for p in res['paline_extra']:
			self.active_marker = None
			palina = None
			if not from_map or not 'lng' in p:
				palina = PalinaPanel(self, p)
				dettaglio.add(palina)
			if p['nascosta']:
				if palina is not None:
					self.paline_nascoste.append(palina)
			else:
				if 'lng' in p:
					rpp = RiepilogoPalinaPanel(self, p['id_palina'], p['primi_arrivi'], p['direzioni'])
					indice = self.pannello_riepilogo.add(
						rpp,
						rpp.activateMarker,
						'%s (%s) a %s' % (p['nome'], p['id_palina'], p['distanza_arrotondata']),
						menu_description=rpp.getMenu(),
					)
					self.paline_riepilogo[p['id_palina']] = rpp
					def add_marker():
						m = Marker(
							self.cl_layer,
							(p['lng'], p['lat']),
							'palina_off.png',
							icon_size=(20, 27),
							anchor=(0, 27),
							name=('palina', (p['id_palina'], '')),
							label=p['nome'],
							click_callback=self.paginatedSelectFactory(self.pannello_riepilogo, indice),
							relative=True,
						)
						rpp.setMarker(m)

					self.owner.map_tab.do_or_defer(add_marker)

		if len(res['percorsi']) > 0:
			if from_map:
				self.owner.setTabCercaLinea()
			h = HTML(_('Linee trovate'))
			h.addStyleName('indicazioni-h1')
			dettaglio.add(h)
		elif len(res['paline_semplice']) > 0 and from_map:
			self.owner.setTabCercaLinea()
			
		for p in res['percorsi']:
			percorso = PercorsoPanel(self, p)
			dettaglio.add(percorso)
			
		if len(self.paline_nascoste) > 0:
			self.mostra_tutto = HTMLFlowPanel()
			dettaglio.add(self.mostra_tutto)
			self.mostra_tutto.addHtml(_("Alcune fermate sono state nascoste perch&eacute; non vi transitano altre linee bus.&nbsp"))
			self.mostra_tutto.addAnchor(_("Mostra tutte le fermate"), self.onMostraTuttePaline)

		if 'lng' in res:
			self.owner.center_and_zoom(self.cl_layer)
			if self.jump_to_result:
				self.pannello_riepilogo.selectIndex(1)



class NotificaLineeDialog(DialogBox):
	counter = 0

	def __init__(self, owner, id_palina, linee):
		DialogBox.__init__(self, glass=True)
		self.owner = owner
		self.id_palina = id_palina
		self.linee = linee
		self.timer_refresh = Timer(notify=self.onTimer)
		if flavor == 'app':
			self.notification = LocalNotification(onNotification=self.onNotificationDone)
		else:
			self.notification = WebNotification(onNotification=self.onNotificationDone)
		self.distanza_tempo = None
		self.id_richiesta = None
		self.counter += 1
		self.id_notifica = "notifica_fermata_%d" % self.counter
		self.notifica_aggiunga = False

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Imposta notifica")],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [_('Notifica quando un veicolo sar&agrave; in arrivo tra circa&nbsp;')],
					'height': None,
				},
				{
					'class': HP,
					'sub': [
						{
							'class': TextBox,
							'name': 'minuti',
							'call_setVisibleLength': ([2], {}),
							'call_setText': (['5'], {}),
							'height': None,
							'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
						},
						{
							'class': HTML,
							'args': [_('&nbsp;minuti')],
							'height': None,
							'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
						},
					]
				},
				{
					'class': HTML,
					'args': [_("Linee:")],
					'style': 'indicazioni-h1',
				},
				{
					'class': CheckList,
					'args': [[(x, x, True) for x in linee]],
					'name': 'linee_list',
				},
				{
					'class': ButtonsPanel,
					'args': [[
						(_('Notifica'), self.onNotifica),
						(_('Annulla'), self.onChiudi),
					]],
				}
			],
			add_to_owner=True,
		)
		self.addStyleName('indicazioni')
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)

	def onNotificaErrore(self):
		self.timer_refresh.schedule(20000)

	def onNotificaRisultati(self, res):
		if 'status' in res and res['status'] != 'OK':
			return

		self.id_richiesta = res['id_richiesta']

		if res['scheduling'] >= 0:
			self.notification.schedule(
				res['scheduling'] * 1000,
				_("Linea %s in arrivo tra circa %d minuti") % (res['id_linea'], self.distanza_tempo),
				_("Veicolo in arrivo"),
			)
		else:
			self.notification.cancel()

		if res['refresh'] > 0:
			self.timer_refresh.schedule(res['refresh'] * 1000)

	def onNotificationDone(self):
		self.onElimina()

	def onTimer(self):
		client.paline_refresh_notifica_arrivo_bus(self.id_richiesta, JsonHandler(self.onNotificaRisultati, self.onNotificaErrore))

	def onNotifica(self):
		minuti = -1
		try:
			minuti = int(self.base.by_name('minuti').getText())
		except:
			pass
		linee_notifica = self.base.by_name('linee_list').getSelectedItems()
		if len(linee_notifica) == 0 or minuti == -1:
			return
		self.notification.cancel()
		self.timer_refresh.cancel()
		self.distanza_tempo = minuti
		client.paline_imposta_notifica_arrivo_bus({
			'id_palina': self.id_palina,
			'linee': linee_notifica,
			'tempo': minuti * 60,
		}, JsonHandler(self.onNotificaRisultati, self.onNotifica))
		if not self.notifica_aggiunga:
			self.owner.owner.aggiungiNotifica(self.id_notifica, _("Notifica fermata %s") % self.id_palina, self.onModifica, self.onElimina)
			self.notifica_aggiunga = True
		self.hide()
		if flavor == 'app':
			DisturbingMessageDialog(
				_("Non chiudere l'app. Puoi porla in background e bloccare lo schermo, se lo desideri."),
				_("Notifica impostata"),
				'notifica_impostata',
			)

	def onChiudi(self):
		self.hide()

	def onElimina(self):
		self.timer_refresh.cancel()
		self.notification.cancel()
		self.owner.owner.rimuoviNotifica(self.id_notifica)

	def onModifica(self):
		self.show()

