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

from pyjamas.Cookies import setCookie, getCookie
from pyjamas.ui.FocusListener import FocusHandler
from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.ScrollPanel import ScrollPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.VerticalSplitPanel import VerticalSplitPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.FlowPanel import FlowPanel
from pyjamas.ui.DisclosurePanel import DisclosurePanel
from pyjamas.ui.TabPanel import TabPanel
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
from pyjamas.ui.DialogBox import DialogBox
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
from util import StyledFixedColumnFlexTable, HTMLFlowPanel, DP, VP, HP, GP, SP, DeferrablePanel, DeferrableTabPanel
from util import storage_get, storage_set, ScrollAdaptivePanel, QuestionDialogBox
from util import get_checked_radio, HidingPanel, MyAnchor, LoadingButton, SearchBox, setAttribute
from util import wait_init, wait_start, wait_stop, _, set_lang, get_lang, MenuPanel, GeneralMenuPanel
from util import PaginatedPanel, MenuPanelItem, pause_all_timers, resume_all_timers, PaginatedPanelPage
from util import PausableTimer, ImageTextButton, MessageDialog, storage_web
from datetime import date, time, datetime, timedelta
from Calendar import Calendar, DateField, TimeField
from map import MapPanel, Layer, LayerPanel, get_location
from cerca_percorso import CercaPercorsoPanel
from cerca_linea import CercaLineaPanel
# from cerca_luogo import CercaLuogoPanel
from info_traffico import InfoTraffico
from news import NewsPanel
from globals import base_url, make_absolute, flavor, set_user, set_control, ios, version, android, old_android, get_os
from __pyjamas__ import JS, wnd

from DissolvingPopup import DissolvingPopup
from util import JsonHandler, JsonInteractiveHandler, WaitingHandler, redirect

client = JSONProxy(base_url + '/json/', [
	'paline_percorso',
	'servizi_autocompleta_indirizzo',
	'paline_smart_search',
	'servizi_app_init_2',
	'servizi_app_login',
	'servizi_delete_fav',
	'servizi_storage_init',
	'lingua_set',
])

INTERVALLO_LOCALIZZAZIONE_SEC = 30
INTERVALLO_LOCALIZZAZIONE = INTERVALLO_LOCALIZZAZIONE_SEC * 1000


class AboutPanel(VerticalPanel):
	def __init__(self, owner):
		VerticalPanel.__init__(self)
		self.owner = owner
		self.header = MenuPanelItem(
			self,
			id='header',
			text=_('Roma mobile'),
			icon='toolbar/back.png',
		)
		self.header.addStyleName('menu-header')
		self.add(self.header)
		self.html = HTMLPanel(_("""
			<p><b>Roma mobile %(version)s</b><br />
			&copy; %(year)d Roma mobile</p>
			<p>
				Roma mobile &egrave; un progetto open source derivato da Muoversi a Roma.
				Muoversi a Roma &egrave; stato sviluppato da Roma Servizi per la Mobilit&agrave;,
				Agenzia per la Mobilit&agrave;
				di Roma Capitale. I dati che alimentano il servizio sono open data di
				Roma Servizi per la Mobilit&agrave;.
			</p>
		""") % {'version': version, 'year': datetime.now().year})
		self.html.addStyleName('about')
		self.add(self.html)
		self.html.setSize('100%', '100%')
		self.setCellHeight(self.html, '100%')
		self.setSize('100%', '100%')

	def hide(self):
		self.owner.display_menu(False)

	def onClick(self):
		self.hide()


class TipBalloon(SimplePanel):
	def __init__(self, html, close, onClose):
		SimplePanel.__init__(self)
		self.vp = VerticalPanel()
		self.vp.addStyleName('tip-balloon-vp')
		self.add(self.vp)
		self.punta = Image('FumettoNNW.png', Width='16px', Height='16px')
		self.punta.addStyleName('tip-balloon-punta')
		self.vp.add(self.punta)
		self.vp2 = VerticalPanel()
		self.vp.add(self.vp2)
		self.vp.setCellHeight(self.vp2, '100%')
		self.addStyleName('tip-balloon-sp')
		self.vp2.addStyleName('tip-balloon-vp2')
		self.vp2.add(HTML(html))
		a = MyAnchor()
		a.setWidget(HTML(close))
		a.addClickListener(onClose)
		self.vp2.add(a)


class SearchMapPanel(VerticalPanel, KeyboardHandler, FocusHandler, DeferrablePanel):
	def __init__(self, owner, map, small=False):
		VerticalPanel.__init__(self)
		DeferrablePanel.__init__(self, deferred_interval=200)
		self.owner = owner
		self.base = VP(
			self,
			[
				{
					'class': HP,
					'style': 'over-map-hp',
					'sub': [
						{
							'class': HP,
							'width': '70%',
							'sub': [
								{
									'class': Image,
									'name': 'localizza',
									'args': ['gps.png'],
									'width': '25px',
									'height': None,
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
								},
								{
									'class': SearchBox,
									'name': 'query',
									'call_addKeyboardListener': ([self], {}),
									'args': [client.servizi_autocompleta_indirizzo, self.onCerca, 0, 100, False],
									'style': 'over-map',
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
											'style': 'over-map',
										},
									]
								},
								{
									'class': Button,
									'args': ['X', self.onChiudiQuery],
									'width': '40px',
									'style': 'over-map close-button',
								},
							],
						},
						# {
						# 	'class': LoadingButton,
						# 	'args': [_('Cerca'), self.onCerca],
						# 	'width': '30%',
						# 	'name': 'button',
						# 	'style': 'over-map',
						# },
					]
				},
			],
			add_to_owner=True,
		)
		self.base.addStyleName('search-fixed' if small else 'search-floating')
		self.base.setWidth('100%' if small else '460px')
		self.tip = TipBalloon(_("""
			Tocca per usare la posizione corrente. Altrimenti cerca una linea, una fermata
			(per nome o codice), oppure un indirizzo.
		"""), _("Capito, grazie."), self.onHoCapito)
		self.tip.setVisible(False)
		self.base.add(self.tip)
		self.map = map
		self.map.setSize('100%', '100%')
		self.add(map)
		self.setCellHeight(self.map, '100%')
		self.base.by_name('localizza').addClickListener(self.onLocalizza)
		self.bottom = SimplePanel()
		self.add(self.bottom)
		self.preferiti = None
		self.on_bottom_replace = None
		self.bottom_widget = None
		self.popup = None
		self.small = small
		setAttribute(self.base.by_name('query'), 'placeholder', _("Linea, fermata o indirizzo"))
		setAttribute(self.base.by_name('localizza'), 'title', _("Imposta posizione corrente"))

	def onHoCapito(self):
		self.tip.setVisible(False)
		storage_set('nascondiTip', True)

	def showTip(self):
		if not storage_get('nascondiTip', False):
			self.tip.setVisible(True)

	def do_or_defer(self, o, *args, **kwargs):
		if not self.owner.small:
			o(*args, **kwargs)
		else:
			DeferrablePanel.do_or_defer(self, o, *args, **kwargs)

	def setBottomWidget(self, w=None, on_replace=None):
		self.onBottomClose()
		self.on_bottom_replace = on_replace
		self.bottom_widget = w
		if w is None:
			self.bottom.clear()
			if not self.small:
				self.closePopup()
		else:
			if self.small:
				self.bottom.setWidget(w)
			else:
				self.openPopup()
				self.popup.add(w)
		self.map.relayout()

	def onBottomClose(self):
		if not self.small:
			self.closePopup()
		if self.on_bottom_replace is not None:
			self.on_bottom_replace()
		self.on_bottom_replace = None
		self.map.relayout()

	def onLocalizza(self):
		self.tip.setVisible(False)
		self.owner.localizza()

	def getWidgets(self):
		x = self.base.by_name('query')
		x_list = self.base.by_name('query_list')
		x_holder = self.base.by_name('query_list_holder')
		return x, x_list, x_holder

	def ripristinaWidgets(self):
		for x, x_list, x_holder in [self.getWidgets()]:
			x.removeStyleName('validation-error')
			if not x.getVisible():
				x.setText(x_list.getSelectedItemText()[0])
				x_holder.setVisible(False)
				x.setVisible(True)

	def onCerca(self):
		self.ripristinaWidgets()
		self.tip.setVisible(False)
		q = self.base.by_name('query')
		pk = q.pk
		if pk != -1 and not str(pk).startswith('A'):
			s = 'fav:' + pk
		else:
			s = q.getText()
		self.cercaLinea(s)

	def onCercaDone(self, res):
		# self.base.by_name('button').stop()
		if res['errore']:
			self.onCercaErrore(res)
			return

		tipo = res['tipo']
		if tipo == 'Indirizzo ambiguo':
			self.onCercaErrore(res)

		self.owner.cerca_linea.onCercaDone(res, True)

	def cercaLinea(self, query):
		# sb = self.base.by_name('button')
		# sb.start()
		# wh = WaitingHandler(custom_stop_callbacks=sb.stop)
		wait_start()
		client.paline_smart_search(query, get_lang(), JsonInteractiveHandler(self.onCercaDone))

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

	def onChiudiQuery(self):
		x, x_list, x_holder = self.getWidgets()
		x_holder.setVisible(False)
		x.setVisible(True)
		x.setText('')
		x.setFocus()

	def onChange(self, el):
		el.removeStyleName('validation-error')

	def onKeyDown(self, sender, keycode, modifiers):
		if keycode == 13:
			self.onCerca()

	def onTabSelected(self):
		self.owner.map.relayout()

	def setSmallLayout(self):
		self.small = True
		self.base.setWidth('100%')
		self.base.removeStyleName('search-floating')
		self.base.addStyleName('search-fixed')
		# self.base.by_name('button').setVisible(False)
		if self.bottom_widget is not None:
			self.popup.remove(self.bottom_widget)
			self.bottom.setWidget(self.bottom_widget)
			self.closePopup()

	def setLargeLayout(self):
		self.small = False
		self.base.setWidth('460px')
		self.base.removeStyleName('search-fixed')
		self.base.addStyleName('search-floating')
		# self.base.by_name('button').setVisible(True)
		if self.bottom_widget is not None:
			self.bottom.clear()
			self.openPopup()
			self.popup.add(self.bottom_widget)

	def openPopup(self):
		if self.popup is None:
			self.popup = PopupPanel(False, modal=False)
			self.popup.setSize('400px', '160px')
			self.popup.addStyleName('bottom-popup')
			self.popup.show()
		else:
			self.popup.clear()
			self.popup.show()

	def closePopup(self):
		if self.popup is not None:
			self.popup.hide()
			self.popup = None

	def onLocationStart(self):
		self.base.by_name('localizza').setUrl('gps.png')

	def onLocationStop(self):
		self.base.by_name('localizza').setUrl('gps_on.png')


class AggiornaDialog(DialogBox):
	def __init__(self):
		DialogBox.__init__(self)
		self.addStyleName('aggiorna-panel')

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Versione app non supportata")],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [_("""
						La versione della tua app &egrave; troppo vecchia. Per continuare,
						devi effettuare un aggiornamento.
					""")],
					'height': None,
					'name': 'main',
				},
				{
					'class': HP,
					'sub': [
						{
							'class': Button,
							'args': [_('Aggiorna'), self.onAggiorna],
							'height': None,
							'name': 'aggiorna',
						},
					]
				},
			],
			add_to_owner=True,
		)
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)

		# Workaround
		if ios():
			self.base.by_name('aggiorna').setVisible(False)

	def onAggiorna(self):
		if android():
			Window.setLocation('market://details?id=com.realtech.romamobilita')
		elif ios():
			Window.setLocation('itms-apps://itunes.apple.com/it/app/muoversi-a-roma/id820255342')


class PreferitiPanel(SimplePanel, DeferrablePanel):
	def __init__(self, owner):
		SimplePanel.__init__(self)
		DeferrablePanel.__init__(self, owner)
		self.owner = owner
		self.menu = None

	def aggiorna_preferiti(self):
		n = [
			{
				'id': p[0],
				'text': p[1],
				'listener': p[2],
				'action_listener': p[3],
				'action_icon': 'close.png',
				'icon': 'alert_off.png',
				'width': '18px',
				'height': '18px',
			} for p in self.owner.notifiche
		]
		d = [
			{
				'id': p[1],
				'text': p[2],
				'listener': self.onPreferitoClick,
				'action_listener': self.onPreferitoDelete,
				'action_icon': 'close.png',
			} for p in self.owner.preferiti
		]
		self.menu = MenuPanel(self.owner, n + d, title=None)
		self.setWidget(self.menu)

	def onPreferitoClick(self, mpi):
		query = self.owner.map_tab.base.by_name('query')
		query.setText(mpi.text)
		query.pk = mpi.id
		self.owner.setTabMappa()
		self.owner.map_tab.onCerca()

	def onPreferitoDeleteDone(self, res):
		pass

	def onPreferitoDeleteConferma(self, mpi):
		def f():
			mpi.setVisible(False)
			client.servizi_delete_fav(mpi.id, JsonHandler(self.onPreferitoDeleteDone))

		return f

	def onPreferitoDelete(self, mpi):
		QuestionDialogBox(_("Conferma"), _("Vuoi cancellare il preferito?"),
											[(_("S&igrave;"), self.onPreferitoDeleteConferma(mpi), None), (_("No"), None, None)]).show()


class ControlPanel(GeneralMenuPanel):
	def __init__(self, small=False):
		GeneralMenuPanel.__init__(self)
		set_control(self)
		self.owner = None
		self.user = None
		self.small = small
		self.posizione = None
		self.preferiti = []
		self.notifiche = []

		self.tab_holder = VerticalPanel()
		self.tab_holder.setSize('100%', '100%')
		self.setMainPanel(self.tab_holder)

		self.tab = DeferrableTabPanel(self)
		self.tab.setSize('100%', '100%')
		self.tab_holder.add(self.tab)
		self.tab_holder.setCellHeight(self.tab, '100%')
		p = DOM.getParent(self.tab.getElement())
		DOM.setStyleAttribute(p, 'overflow-x', 'hidden')

		self.cerca_percorso = CercaPercorsoPanel(self)
		# self.tab.add(self.cerca_percorso, HTML(_("Percorso")))
		self.tab.add(self.cerca_percorso, Image(_('toolbar/percorso.png'), Width='48px', Height='48px'))
		self.tab.selectTab(0)

		self.cerca_linea = CercaLineaPanel(self)
		self.cerca_linea.setSize('100%', '100%')
		self.tab.add(self.cerca_linea, Image(_('toolbar/linea.png'), Width='48px', Height='48px'))

		# self.cerca_luogo = CercaLuogoPanel(self)
		# self.cerca_luogo.setSize('100%', '100%')
		# self.tab.add(self.cerca_luogo, Image(_('toolbar/luogo.png'), Width='48px', Height='48px'))

		self.preferiti_tab = PreferitiPanel(self)
		self.preferiti_tab.setSize('100%', '100%')
		self.preferiti_tab_image = Image(_('toolbar/preferiti.png'), Width='48px', Height='48px')
		self.tab.add(self.preferiti_tab, self.preferiti_tab_image)

		self.old_width = Window.getClientWidth()
		self.old_height = Window.getClientHeight()
		self.waiting = wait_init(self.tab_holder)
		self.mp = MenuPanel(self, [
			# {
			# 'id': 'login',
			# 'text': _("Caricamento account utente"),
			# 'listener': self.onLogin,
			# },
			# {
			# 'id': 'news',
			# 'text': _("News"),
			# 'listener': self.onNews,
			# },
			# {
			# 'id': 'legacy',
			# 'text': _("Versione precedente"),
			# 'listener': self.onLegacy,
			# },
			# {
			# 'id': 'feedback',
			# 'text': _("Invia il tuo feedback"),
			# 'listener': self.onFeedback,
			# },
			{
				'id': 'language',
				'text': _("Language"),
				'listener': self.onLanguage,
			},
			# {
			# 'id': 'logout',
			# 'text': _("Esci"),
			# 'listener': self.onLogout,
			# },
			{
				'id': 'about',
				'text': _("Informazioni su Roma mobile"),
				'listener': self.onAbout,
			},
		], icon='toolbar/back.png', )
		# self.mp.by_id('logout').setVisible(False)
		# if flavor == 'app':
		# 	self.mp.by_id('legacy').setVisible(False)
		# if get_lang() != 'it':
		# 	self.mp.by_id('news').setVisible(False)
		self.setMenuPanel(self.mp)
		self.waiting.setGeneralMenuPanel(self)

		self.map = MapPanel(self)
		self.map.animation_enabled = True
		self.map_tab = SearchMapPanel(self, self.map, small)
		self.map_tab.setSize('100%', '100%')
		self.cerca_percorso.setMap(self.map)
		self.cerca_linea.setMap(self.map)
		# self.cerca_luogo.setMap(self.map)

		raw_params = getRawParams()

		# Geolocation

		# geolocation_status:
		# 0: normal mode (do nothing when ready)
		# 1: geolocating, will prefetch waiting times when ready
		# 2: loading waiting times stage 1 (location): trigger waiting times when ready
		# 3: loading waiting times stage 2 (waiting times): send to cerca_linea when read
		self.geolocation_status = 0
		self.prefetched_cerca_linea = None
		self.prefetched_cerca_linea_time = None

		# Non effettua la geolocalizzazione se è specificato un indirizzo di partenza per il cerca percorso,
		# oppure se richiesto esplicitamente di non geolocalizzare tramite il parametro geoloc=0
		if raw_params.find('geoloc=0') == -1:
			self.location_timer = PausableTimer(notify=self.onLocationTimer)
			self.location_timer.schedule(INTERVALLO_LOCALIZZAZIONE)
			self.geolocation_status = 1
			get_location(self.onLocation, self.onLocationError)

		control_panel[0] = self

		if small:
			self.tab.add(self.map_tab, Image(_('toolbar/mappa.png'), Width='48px', Height='48px'))
			self.map_tab.setSize('100%', '100%')  # self.tab.getClientHeight())

	def resume(self):
		# As soon as the app is resumed, self.location_timer will perform a new geolocation.
		# We set geolocation_status to 1 to prefetch waiting times as well.
		self.geolocation_status = 1

	def setBottomWidget(self, w=None, on_replace=None):
		self.map_tab.setBottomWidget(w, on_replace)

	def creaPannelloRiepilogo(self, height=None, close_callback=None):
		pp = PaginatedPanel(height, self.map_tab.onBottomClose)
		self.setBottomWidget(pp, close_callback)
		return pp

	def showSidePanel(self):
		if not self.small:
			self.owner.hide(False)

	def relayout(self):
		width = Window.getClientWidth()
		height = Window.getClientHeight()
		if width != self.old_width or height > self.old_height:
			self.cerca_percorso.do_or_defer(self.cerca_percorso.relayout)
			self.cerca_linea.do_or_defer(self.cerca_linea.relayout)
		# self.cerca_luogo.do_or_defer(self.cerca_luogo.relayout)
		# self.preferiti_tab.do_or_defer(self.preferiti_tab.relayout)
		self.old_width = width
		self.old_height = height
		if self.small:
			self.map_tab.do_or_defer(self.map.relayout)
		else:
			self.map.relayout()

	def aggiungiNotifica(self, id, titolo, edit_callback, delete_callback):
		"""
		Aggiungi una notifica al menu delle notifiche.

		La cancellazione dovrà essere richiesta invocando il metodo rimuoviNotifica, in ogni caso:
		anche se essa avviene perché l'utente ha chiesto di cancellare la notifica
		"""
		self.notifiche.append([id, titolo, edit_callback, delete_callback])
		self.preferiti_tab.aggiorna_preferiti()
		if len(self.notifiche) > 0:
			self.preferiti_tab_image.setUrl(_('toolbar/preferiti_not.png'))

	def rimuoviNotifica(self, id):
		self.notifiche = [n for n in self.notifiche if n[0] != id]
		self.preferiti_tab.aggiorna_preferiti()
		if len(self.notifiche) == 0:
			self.preferiti_tab_image.setUrl(_('toolbar/preferiti.png'))

	def setPreferiti(self, fav):
		self.preferiti = fav
		self.preferiti_tab.aggiorna_preferiti()

	def isSmall(self):
		return self.small

	def center_and_zoom(self, layer):
		if self.small:
			self.map_tab.do_or_defer(layer.centerOnMap)
		else:
			layer.centerOnMap()

	def onAppInit(self, res):
		# Session
		if flavor != 'web':
			storage_set('session_key', res['session_key'])

		# # User
		# self.user = res['user']
		# set_user(self.user)
		# if self.user is not None:
		# 	l = self.mp.by_id('login')
		# 	l.setText(_("Ciao, %s (Gestisci account)") % self.user['nome'])
		# 	l.setListener(self.onGestisciAccount)
		# 	self.mp.by_id('logout').setVisible(True)
		# else:
		# 	l = self.mp.by_id('login')
		# 	l.setText(_("Accedi"))
		# 	l.setListener(self.onLogin)
		# 	self.mp.by_id('logout').setVisible(False)

		self.setPreferiti(res['fav'])

		# Version
		p_andorid = android()
		p_ios = ios()

		if p_andorid or p_ios:
			if res['deprecata']:
				AggiornaDialog()
				return
			elif res['messaggio_custom'] is not None and res['messaggio_custom'] != '':
				DissolvingPopup(res['messaggio_custom'])
			elif res['aggiornamento']:
				DissolvingPopup(_("E' disponibile un aggiornamento"))
			else:
				self.proponiVoto()

		# Utente cambiato, apri pagina web per impostare cookie (in app)
		if flavor == 'app' and res['utente_cambiato']:
			DissolvingPopup(_("Bentornato!"))
			url = 'http://muovi.roma.it/servizi/app_login_by_token/%s' % res['session_key']
			JS("""
				try {
					ref = $wnd.open(url, '_blank', 'location=no');
					ref.addEventListener('loadstop', function(event) {
						ref.close();
					});
				}
				catch (err) {
					alert("Generic error: " + err);
				}
			""")

		# Parameters
		params = res['params']
		cp_params = self.cerca_percorso.availableParams()
		for p in cp_params:
			if p in params:
				self.cerca_percorso.setParam(p, params[p])
		cl_params = self.cerca_linea.availableParams()
		for p in cl_params:
			if p in params:
				self.cerca_linea.setParam(p, params[p])
		# cr_params = self.cerca_luogo.availableParams()
		# for p in cr_params:
		# 	if p in params:
		# 		self.cerca_luogo.setParam(p, params[p])
		if 'cl' in params and not ('query' in params or 'id_percorso' in params):
			self.tab.selectTab(1)
		# if ('cr' in params or 'cr_da' in params or 'cr_lista_tipi' in params) and not 'cr_a' in params:
		# 	if 'cr' in params and 'cr_da' in params and not 'cr_a' in params:
		# 		self.setTabMappaLuogo()
		# 	else:
		# 		self.tab.selectTab(2)

	def setTabCercaPercorso(self):
		self.tab.selectTab(0)
		if not self.small:
			self.owner.hide(False)

	def setTabCercaLinea(self):
		self.tab.selectTab(1)
		if not self.small:
			self.owner.hide(False)

	# def setTabCercaLuogo(self):
	# 	self.tab.selectTab(2)
	# 	if not self.small:
	# 		self.owner.hide(False)

	def setTabMappaPercorso(self):
		if self.small:
			self.tab.selectTab(3)
			self.tab.star_tab(0)
		else:
			self.tab.selectTab(0)

	def setTabPercorsoMappa(self):
		if self.small:
			self.tab.selectTab(0)
			self.tab.star_tab(3)
		else:
			self.tab.selectTab(0)
			self.owner.hide(False)

	def setTabMappaLinea(self):
		if self.small:
			self.tab.selectTab(3)
			self.tab.star_tab(1)
		else:
			self.tab.selectTab(1)

	def setTabLineaMappa(self):
		if self.small:
			self.tab.selectTab(1)
			self.tab.star_tab(3)
		else:
			self.tab.selectTab(1)
			self.owner.hide(False)

	# def setTabMappaLuogo(self):
	# 	if self.small:
	# 		self.tab.selectTab(3)
	# 		self.tab.star_tab(2)
	# 	else:
	# 		self.tab.selectTab(2)

	def setTabMappa(self):
		if self.small:
			self.tab.selectTab(3)

	def cercaPercorsoRisorse(self, da, tipi, a=None):
		self.setTabCercaPercorso()
		self.cerca_percorso.cercaPercorsoRisorse(da, tipi, a)

	def cercaLineaPercorso(self, id_percorso, su_mappa=False):
		if su_mappa:
			self.setTabMappaLinea()
		else:
			self.setTabLineaMappa()
		self.cerca_linea.cercaPercorso(id_percorso, su_mappa=su_mappa)

	def cercaLinea(self, query, su_mappa=False, jump_to_result=False):
		if su_mappa:
			self.setTabMappaLinea()
		else:
			self.setTabLineaMappa()
		self.cerca_linea.cercaLinea(query, True, from_map=su_mappa, jump_to_result=jump_to_result)

	def localizza(self):
		if self.prefetched_cerca_linea_time is not None and (
			datetime.now() - self.prefetched_cerca_linea_time).seconds < INTERVALLO_LOCALIZZAZIONE_SEC:
			self.cerca_linea.onCercaDone(self.prefetched_cerca_linea, True)
		else:
			wait_start()
			if self.geolocation_status == 1:
				# Location init in progress. Go on with retreiving waiting times
				self.geolocation_status = 2
			elif self.geolocation_status == 0:
				# Use last location
				if self.posizione is None:
					self.erroreGeolocalizzazione()
				else:
					self.geolocation_status = 3
					client.paline_smart_search(self.posizione, get_lang(), JsonInteractiveHandler(self.onWaitingTimesDone))
				# Else, geolocation_status in [2, 3]. We are already getting location or waiting times, nothing to do.

	def onWaitingTimesDone(self, res):
		self.map_tab.onLocationStop()
		self.prefetched_cerca_linea = res
		self.prefetched_cerca_linea_time = datetime.now()
		if self.geolocation_status > 0:
			self.geolocation_status = 0
			wait_stop()
			self.cerca_linea.onCercaDone(res, True)

	def erroreGeolocalizzazione(self):
		wait_stop()
		DissolvingPopup(_('Impossibile determinare la posizione'), error=True)

	def onLocationError(self):
		self.posizione = None
		if self.geolocation_status == 1:
			self.geolocation_status = 0
		if self.geolocation_status == 2:
			self.geolocation_status = 0
			self.erroreGeolocalizzazione()

	def onLocation(self, lng, lat):
		self.posizione = _('Posizione attuale <punto:(%f,%f)>') % (lat, lng)
		if self.geolocation_status == 1:
			# initing: prefetch waiting times
			self.geolocation_status = 0
			client.paline_smart_search(self.posizione, get_lang(), JsonHandler(self.onWaitingTimesDone))
			self.map_tab.showTip()
		elif self.geolocation_status == 2:
			# waiting for waiting times
			self.geolocation_status = 3
			client.paline_smart_search(self.posizione, get_lang(), JsonInteractiveHandler(self.onWaitingTimesDone))
		else:
			self.map_tab.onLocationStop()

	def onLocationTimer(self):
		self.map_tab.onLocationStart()
		self.location_timer.schedule(INTERVALLO_LOCALIZZAZIONE)
		get_location(self.onLocation, self.onLocationError)

	def cercaPercorsoDa(self, da):
		self.cerca_percorso.impostaDa(da)
		self.setTabCercaPercorso()

	def cercaPercorsoA(self, a):
		self.cerca_percorso.impostaA(a)
		if self.posizione is not None:
			self.cerca_percorso.impostaDa(self.posizione)
			self.cerca_percorso.cercaPercorso(su_mappa=True)
		else:
			self.setTabCercaPercorso()

	# def cercaLuogo(self, luogo):
	# 	self.cerca_luogo.cercaLuogo(luogo, set_input=True)
	# 	self.setTabCercaLuogo()

	def onBeforeTabSelected(self, sender, index):
		return True

	def setSmallLayout(self):
		self.small = True
		self.tab.add(self.map_tab, Image(_('toolbar/mappa.png'), Width='48px', Height='48px'))
		self.map_tab.setSize('100%', '100%')  # self.tab.getClientHeight())
		# self.tab.add(self.layers, "Layer")
		self.map_tab.do_or_defer(self.map.relayout)
		self.map_tab.setSmallLayout()
		self.relayout()
		self.setTabCercaPercorso()
		self.setTabCercaLinea()
		# self.setTabCercaLuogo()
		self.setTabMappa()

	def setLargeLayout(self):
		self.small = False
		if self.tab.getTabBar().getSelectedTab() == 3:  # Map
			self.setTabCercaPercorso()
		self.tab.remove(self.map_tab)
		self.map_tab.setLargeLayout()

	def onLoginWsDone(self, res):
		if flavor != 'web':
			storage_set('session_key', '')
		self.restartApp()

	def loginWs(self, url, ref):
		if url.find('login_app_landing') != -1:
			JS("""ref.close();""")
			t = url.find('Token=')
			token = url[t + 6:]
			client.servizi_app_login(token, JsonHandler(self.onLoginWsDone))

	def hide(self, hide=True):
		self.owner.hide(hide)

	def onLogin(self):
		wait_start()
		if flavor == 'web':
			storage_set('session_key', '')
			Window.setLocation('/servizi/login?IdSubSito=3')
		else:
			url = 'http://login.muoversiaroma.it/Login.aspx?IdSito=13'
			JS("""
				try {
					ref = $wnd.open(url, '_blank', 'location=no');
					ref.addEventListener('loadstop', function(event) {
						self.loginWs(event.url, ref);
					});
				}
				catch (err) {
					alert("Generic error: " + err);
				}
			""")

	def onNews(self):
		news = NewsPanel(self)
		self.display_menu(alternative_menu=news)

	def onAbout(self):
		about = AboutPanel(self)
		self.display_menu(alternative_menu=about)

	def onLegacy(self):
		if flavor == 'web':
			Window.setLocation('/base')

	def onFeedback(self):
		if flavor == 'app' and not old_android():
			self.proponiVoto(True)
		else:
			Window.setLocation('http://muovi.roma.it/facebook')

	def onLinguaSetDone(self):
		self.restartApp()

	def onLanguageSet(self, mpi):
		client.lingua_set(mpi.id, JsonHandler(self.onLinguaSetDone))
		storage_set('hl', mpi.id)
		wait_start()

	def onLanguage(self):
		lmp = MenuPanel(self, [
			{
				'id': 'it',
				'text': _("Italiano"),
				'listener': self.onLanguageSet,
			},
			{
				'id': 'en',
				'text': _("English"),
				'listener': self.onLanguageSet,
			}, ],
										icon='toolbar/back.png',
										title='Language',
										)
		self.display_menu(alternative_menu=lmp)

	def onLogout(self):
		if flavor == 'web':
			Window.setLocation('/servizi/logout?IdSubSito=3')
		else:
			client.servizi_app_init_2({
				'session_or_token': '-',
				'versione': version,
				'os': get_os(),
			}, '', JsonHandler(self.onAppInit))

	def onGestisciAccount(self):
		url = 'http://login.muoversiaroma.it/GestioneAccount.aspx'
		if flavor == 'web':
			Window.setLocation(url)
		else:
			JS("""
				try {
					$wnd.open(url, '_blank', 'location=yes');
				}
				catch (err) {
					alert("Generic error: " + err);
				}
			""")

	def restartApp(self):
		JS("""$wnd.location.reload();""")

	def proponiVoto(self, forza=False):
		d = datetime.now().hour
		if forza or (flavor == 'app' and d > 14 and not storage_get('voto_disabilitato', False) and not old_android()):
			counter = int(storage_get('voto_counter', 0))
			if not forza and counter < 9:
				storage_set('voto_counter', counter + 1)
			else:
				storage_set('voto_counter', 0)
				VotaDialog(self)


class LeftPanel(HidingPanel):
	def __init__(self, owner, control):
		HidingPanel.__init__(self, False)
		self.owner = owner
		self.small = False
		self.split = VerticalSplitPanel()
		self.split.setSize('100%', '100%')
		self.split.setSplitPosition('90%')
		self.control = control
		self.control.owner = self
		self.control.setSize('100%', '100%')
		self.split.setTopWidget(self.control)
		self.add(self.split)
		self.layers = LayerHolder(self.control.map)
		self.split.setBottomWidget(self.layers)

	def relayout(self):
		self.control.relayout()

	def setSmallLayout(self):
		self.small = True

	def setLargeLayout(self):
		self.small = False
		self.split.setTopWidget(self.control)

	def updateSplitter(self):
		if not self.small:
			self.split.setSplitPosition('90%')


class LayerHolder(SimplePanel):
	def __init__(self, map):
		SimplePanel.__init__(self)
		self.setSize('100%', '100%')
		self.addStyleName('indicazioni-bg')

		vp = VerticalPanel()
		vp.setWidth('100%')
		vp.addStyleName('indicazioni')

		titolo = HTML(_('Ora presenti sulla mappa'))
		titolo.addStyleName('indicazioni-h1')
		titolo.setWidth('100%')
		vp.add(titolo)

		layer_panel = LayerPanel(map)
		vp.add(layer_panel)
		vp.setCellWidth(layer_panel, '100%')

		self.add(vp)


class LargeLayoutPanel(HorizontalPanel):
	def __init__(self, control):
		HorizontalPanel.__init__(self)

		# left panel
		self.left = LeftPanel(self, control)
		self.left.setSize('0', '100%')
		self.add(self.left)
		self.setCellHeight(self.left, '100%')
		self.control = control

		# map panel
		self.map = self.control.map
		self.search_map = self.control.map_tab
		self.add(self.search_map)
		self.setCellWidth(self.search_map, '100%')
		self.setCellHeight(self.search_map, '100%')

		# the end
		self.left.addHideListener(self.onHide)
		self.setSize("100%", "100%")

	def onHide(self, source):
		self.map.relayout()
		self.left.split.setSplitPosition('90%')
		self.left.relayout()

	def setSmallLayout(self):
		pass

	def setLargeLayout(self):
		# self.add(self.left)
		self.left.setLargeLayout()
		self.setCellHeight(self.left, '100%')
		self.add(self.search_map)
		self.search_map.setVisible(True)
		self.setCellWidth(self.search_map, '100%')
		self.setCellHeight(self.search_map, '100%')

	def addVmsLayer(self):
		raw_params = getRawParams()
		if raw_params.find('vms=1') != -1:
			Layer('pannelli', 'Pannelli VMS', self.map, self, True, ['pannelli', 0])
		if raw_params.find('info_traffico=1') != -1:
			self.info_traffico = InfoTraffico(self, self.map)

	def getControlPanel(self):
		return self.left.control

	def updateSplitter(self):
		self.left.updateSplitter()


def getRawParams():
	return Window.getLocation().getSearch()[1:]


class GeneralPanel(VerticalPanel):
	def __init__(self, small=False):
		VerticalPanel.__init__(self)
		self.small = small
		self.has_header = False

		# raw_params = getRawParams()
		# if raw_params.find('iframe=0') == -1:
		# 	# header
		# 	self.has_header = True
		# 	self.header = HorizontalPanel()
		# 	self.header.setSize('100%', '58px')
		# 	self.add(self.header)
		# 	self.setCellHeight(self.header, '58px')
		#
		# 	self.header.add(Image('logo-sx.png'))
		# 	self.header.addStyleName('logo')
		#
		# 	self.copy = HTML('<a href="http://www.agenziamobilita.roma.it">&copy; %d Roma servizi per la mobilit&agrave; s.r.l.</a>' % datetime.now().year)
		# 	self.copy.addStyleName('copy')
		# 	self.header.add(self.copy)
		# 	self.header.setCellHorizontalAlignment(self.copy, HasAlignment.ALIGN_RIGHT)

		# main

		self.control = ControlPanel(small=small)

		if small:
			self.llp = None
			self.add(self.control)
		else:
			self.llp = LargeLayoutPanel(self.control)
			self.add(self.llp)
			self.setCellHeight(self.llp, '100%')
		self.setSize('100%', '100%')

	def onAppInit(self, res):
		# if datetime.now() < datetime(2015, 2, 17):
		# 	msg = """
		# 		<p>
		# 			Nella giornata di Marted&igrave; 17 febbraio il servizio non sar&agrave; disponibile
		# 			a causa di un intervento di manutenzione straordinaria dell'infrastruttura server.
		# 		</p>
		# 	"""
		# 	MessageDialog(msg, "Avviso")
		self.control.onAppInit(res)

	def onAppInitError(self, text, code):
		return
		if datetime.now() < datetime(2015, 2, 18):
			msg = """
				<p>
					Siamo spiacenti, il servizio momentaneamente non &egrave; disponibile.<br /><br />
					<b>Nella giornata di Marted&igrave; 17 febbraio il servizio non sar&agrave; disponibile
					a causa di un intervento di manutenzione straordinaria dell'infrastruttura server.</b>
				</p>
			"""
			MessageDialog(msg, "Servizio non disponibile")

	def setSmallLayout(self):
		if not self.small:
			self.small = True
			if self.has_header:
				self.remove(self.header)
			self.remove(self.llp)
			self.add(self.control)
			self.control.setSmallLayout()
			if self.llp is not None:
				self.llp.setSmallLayout()

	def setLargeLayout(self):
		if self.small:
			self.small = False
			self.remove(self.control)
			if self.llp is None:
				self.llp = LargeLayoutPanel(self.control)
			else:
				self.llp.setLargeLayout()
			self.control.setLargeLayout()
			self.add(self.llp)
			if self.has_header:
				self.insert(self.header, 0)
				self.setCellHeight(self.header, '58px')
			self.relayout()

	def doResize(self):
		if int(self.getClientWidth()) < 800:
			self.setSmallLayout()
		else:
			self.setLargeLayout()
		if self.llp is not None:
			self.llp.updateSplitter()
		self.relayout()

	def onWindowResized(self):
		self.doResize()

	def createMap(self):
		self.control.map.create_map()
		if self.small:
			self.control.setTabMappa()
		else:
			self.llp.addVmsLayer()

	def relayout(self):
		self.control.relayout()


class VotaDialog(DialogBox):
	def onVota(self):
		storage_set('voto_disabilitato', True)
		Window.setLocation(self.market)
		self.hide()

	def onNonOra(self):
		self.hide()

	def onCommunity(self):
		storage_set('voto_disabilitato', True)
		Window.setLocation(self.community)
		self.hide()

	def onMaiPiu(self):
		storage_set('voto_disabilitato', True)
		self.hide()

	def __init__(self, owner):
		DialogBox.__init__(self, glass=True)
		self.owner = owner

		if ios():
			community = _("sulla nostra pagina Facebook")
			self.market = 'itms-apps://itunes.apple.com/it/app/muoversi-a-roma/id820255342'
			self.community = 'http://muovi.roma.it/facebook'
		else:
			community = _("sulla nostra Community Google+")
			self.market = 'market://details?id=com.realtech.romamobilita'
			self.community = 'http://muovi.roma.it/gplus'

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Aiutaci con il tuo feedback")],
					'style': 'indicazioni-h1',
					'height': None,
				},
				{
					'class': HTML,
					'args': [_("""
						<p>L'app ti &egrave; utile? Supporta lo sviluppo con la tua valutazione.
						Per inviare proposte e suggerimenti sull'app, scrivici %s. Grazie!</p>
					""") % community],
					'style': 'indicazioni',
					'height': None,
				},
				{
					'class': GP,
					'column_count': 2,
					'sub': [
						{
							'class': Button,
							'args': [_('Vota'), self.onVota],
							'width': '50%',
						},
						{
							'class': Button,
							'args': [_('Non ora'), self.onNonOra],
							'width': '50%',
						},
						{
							'class': Button,
							'args': [_('Scrivici'), self.onCommunity],
							'width': '50%',
						},
						{
							'class': Button,
							'args': [_('Non mostrare pi&ugrave;'), self.onMaiPiu],
							'width': '50%',
						},
					]
				},
			],
			add_to_owner=True,
		)
		self.addStyleName('indicazioni')
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)


def onPause():
	pause_all_timers()


def onResume():
	if control_panel[0] is not None:
		control_panel[0].resume()
	resume_all_timers()


def register_pausable_timers():
	pa = onPause
	ra = onResume

	JS("""
		$wnd.document.addEventListener(
			"pause",
			function() {pa();},
			false
		);
		$wnd.document.addEventListener(
			"resume",
			function() {ra();},
			false
		);
	""")


control_panel = [None]

framework_init_done = [False]


def onFrameworkInit(res=None):
	if not framework_init_done[0]:
		framework_init_done[0] = True
		raw_params = getRawParams()
		lang = 'it'
		store_lang = False
		stored_lang = storage_get('hl', '-')
		if stored_lang != '-':
			lang = stored_lang
		elif raw_params.find('hl=it') != -1:
			lang = 'it'
			store_lang = True
		elif raw_params.find('hl=en') != -1 or raw_params.find('HL=EN') != -1:
			lang = 'en'
			store_lang = True
		if store_lang:
			storage_set('hl', lang)
		set_lang('it', lang)

		rp = RootPanel()
		splash = DOM.getElementById("Loading-Message")
		par = DOM.getParent(splash)
		DOM.removeChild(par, splash)
		small = int(Window.getClientWidth()) < 800
		gp = GeneralPanel(small=small)
		rp.add(gp)
		gp.createMap()
		gp.relayout()

		if flavor == 'web':
			session_key = 'web'
		else:
			session_key = storage_get('session_key', '')
		client.servizi_app_init_2({
			'session_or_token': session_key,
			'versione': version,
			'os': get_os(),
		}, getRawParams(), JsonHandler(gp.onAppInit))

		register_pausable_timers()
		Window.addWindowResizeListener(gp)
		gp.getElement().scrollIntoView()


def onStorageInit(res):
	storage_web.update(res)
	onFrameworkInit()


wnd().onFrameworkInitJs = onFrameworkInit

if __name__ == '__main__':
	if flavor == 'web':
		client.servizi_storage_init(JsonHandler(onStorageInit))
	else:
		# ready_timer = Timer(notify=onFrameworkInit)
		# ready_timer.schedule(1500)
		JS("""
			$wnd.document.addEventListener(
				"deviceready",
				function() {$wnd.onFrameworkInitJs();},
				false
			);
		""")

