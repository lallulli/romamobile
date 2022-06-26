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

from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.VerticalSplitPanel import VerticalSplitPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.ScrollPanel import ScrollPanel
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
from prnt import prnt
from util import StyledFixedColumnFlexTable, HTMLFlowPanel, DP, VP, HP, GP, SP, enforce_login
from util import get_checked_radio, HidingPanel, ValidationErrorRemover, MyAnchor
from util import ToggleImage, FavSearchBox, DeferrablePanel, ScrollAdaptivePanel
from util import wait_start, wait_stop, _, get_lang, TimeBox, PaginatedPanelPage, PaginatedPanel
from datetime import date, time, datetime, timedelta
from Calendar import Calendar, DateField, TimeField
from map import MapPanel, Layer, LayerPanel, Marker, get_location, GeoJson
from globals import base_url, make_absolute, web_prefix
from DissolvingPopup import DissolvingPopup
from util import JsonHandler, JsonInteractiveHandler, redirect

SOGLIA_DIST_TRATTO_PIEDI = 200


client = JSONProxy(base_url + '/json/', [
	'percorso_cerca',
	'urldecode',
	'risorse_lista_tipi',
	'ztl_get_lista',
	'percorso_get_params',
	'percorso_email',
	'percorso_posizione_attuale',
	'servizi_autocompleta_indirizzo',
	'carpooling_dettaglio_offerta',
])

class LineaLabel(HorizontalPanel):
	def __init__(self, id_linea):
		HorizontalPanel.__init__(self)
		self.id_linea = id_linea
		self.addStyleName('inl')
		self.addStyleName('linea-label')
		self.linea = MyAnchor()
		self.linea.setWidget(HTML(id_linea))
		self.linea.addStyleName('linea-label-sx')
		self.add(self.linea)
		self.x = MyAnchor()
		self.x.setWidget(Image('x.png'))
		self.x.addStyleName('linea-label-dx')
		self.add(self.x)
		self.setCellHorizontalAlignment(self.x, HasAlignment.ALIGN_CENTER)
		self.setCellVerticalAlignment(self.x, HasAlignment.ALIGN_MIDDLE)
		self.chiudi_listener = None
		self.x.addClickListener(self.onClose)
		
	def addCloseListener(self, l):
		self.chiudi_listener = l
		
	def addLineaListener(self, l):	
		self.linea.addClickListener(l)
		
	def onClose(self):
		if self.chiudi_listener is not None:
			self.x.setVisible(False)
			self.linea.addStyleName('linea-chiusa')
			chiudi = self.chiudi_listener
			self.chiudi_listener = None
			chiudi()

class RiepilogoPercorsoPanel(ScrollPanel, PaginatedPanelPage):
	def __init__(self, owner, stat, linee_escluse):
		ScrollPanel.__init__(self)
		self.owner = owner
		self.setHeight('136px')
		self.stat = stat
		self.init_done = False
		self.linee_escluse = linee_escluse

	def notifyShow(self):
		if not self.init_done:
			self.lazy_init()

	def lazy_init(self):
		self.init_done = True
		self.base = VP(
			self,
			sub=[
				{
					'class': SimplePanel,
					'name': 'tratti',
					'style': 'vskip',
					'horizontal_alignment': HasAlignment.ALIGN_CENTER,
				},
				{
					'class': HTMLPanel,
					'args': ["<b>%s</b>" % self.stat['tempo_totale_format']],
					'style': 'vskip',
					'horizontal_alignment': HasAlignment.ALIGN_CENTER,
				},
				{
					'class': HTMLFlowPanel,
					'name': 'esclusioni',
					'args': [],
					'horizontal_alignment': HasAlignment.ALIGN_CENTER,
				},
			],
			add_to_owner=True,
		)

		self.base.setWidth('96%')

		self.tratti = HorizontalPanel()
		sopratratti = self.base.by_name('tratti')
		sopratratti.add(self.tratti)
		self.n_tratti = 0
		self.qualche_tratto = False

		# Esclusioni
		if len(self.linee_escluse) > 0:
			esclusioni = self.base.by_name('esclusioni')
			esclusioni.addHtml(_('<b>Esclusioni:</b>&nbsp;'))
			for el in self.linee_escluse:
				id_linea, nome_linea = el['id_linea'], el['nome']
				ll = LineaLabel(nome_linea)
				ll.addCloseListener(self.owner.onIncludiFactory(id_linea))
				esclusioni.add(ll)
				esclusioni.addHtml('&nbsp;')
				self.owner.linee_escluse[id_linea] = nome_linea

	def getMenu(self):
		return [
			{
				'id': 'opzioni',
				'text': _('Opzioni di viaggio'),
				'listener': self.owner.onOpzioni,
			},
			{
				'id': 'ritorno',
				'text': _('Cerca ritorno'),
				'listener': self.owner.onRitorno,
			},
			{
				'id': 'parti_qui',
				'text': _('Ricalcola da posizione attuale'),
				'listener': self.owner.onPartiQui,
			},
			{
				'id': 'email',
				'text': _('Invia per email'),
				'listener': self.owner.onEmail,
			},
			{
				'id': 'link',
				'text': _('Link al percorso'),
				'listener': self.owner.onGetLink,
			},
		]

	def addTratto(self, tratto):
		# if self.n_tratti % 4 == 0:
		# 	self.tratti = HorizontalPanel()
		# 	self.base.by_name('tratti').append(self.tratti)
		self.n_tratti += 1
		if tratto['dist'] >= SOGLIA_DIST_TRATTO_PIEDI:
			n_tratti = self.n_tratti
			tratti = self.tratti
			if self.qualche_tratto:
				freccia = Image('freccia_dx.png', Height='24px')
				tratti.add(freccia)
				tratti.setCellVerticalAlignment(freccia, HasAlignment.ALIGN_MIDDLE)
			self.qualche_tratto = True
			t = VerticalPanel()
			icona, hfp, w1, w2, escludi = self.owner.decodeResTratto(tratto, False, True)
			def onClick():
				self.paginated_panel.selectIndex(n_tratti)
			icona.addClickListener(onClick)
			icona.setSize('24px', '24px')
			t.add(icona)
			t.setCellHorizontalAlignment(icona, HasAlignment.ALIGN_CENTER)
			t.add(w1)
			t.setCellHorizontalAlignment(w1, HasAlignment.ALIGN_CENTER)
			t.add(w2)
			t.setCellHorizontalAlignment(w2, HasAlignment.ALIGN_CENTER)
			tratti.add(t)
			tratti.setCellVerticalAlignment(t, HasAlignment.ALIGN_TOP)



class TrattoPercorsoPanel(ScrollPanel, PaginatedPanelPage):
	def __init__(self, owner, nodo_partenza, tratto, nodo_arrivo):
		ScrollPanel.__init__(self)
		self.owner = owner
		self.setHeight('136px')
		self.init_done = False
		self.marker = None
		self.nodo_partenza = nodo_partenza
		self.tratto = tratto
		self.nodo_arrivo = nodo_arrivo
		self.id_palina = None

	def notifyShow(self):
		if not self.init_done:
			self.lazy_init()

	def formatNodo(self, n, nome_tempo, nome_nodo, con_tempi=False):
		self.base.by_name(nome_tempo).setHTML(n['t'])
		tipo = n['tipo']
		out = self.base.by_name(nome_nodo)
		if tipo == 'F':
			out.addHtml(_("Fermata&nbsp;"))

		if n['url'] != '':
			out.addAnchor(n['nome'], self.owner.onPalinaFactory(n['id']))
			if con_tempi:
				self.id_palina = n['id']
				self.insertMenuItem(2,
					{
						'id': 'tempi_attesa',
						'text': _('Tempi di attesa della fermata'),
						'listener': self.onTempiAttesa,
					},
				)
		else:
			out.addHtml(n['nome'])


	def lazy_init(self):
		self.init_done = True
		self.base = VP(
			self,
			sub=[
				{
					'class': GP,
					'column_count': 2,
					'name': 'indicazioni',
					'sub': [
						{
							'class': HTML,
							'center': True,
							'style': 'indicazioni-orario',
							'name': 'tempo_p',
							'expand': False,
						},
						{
							'class': HTMLFlowPanel,
							'name': 'nodo_p',
							'expand': False,
						},
						{
							'class': SP,
							'center': True,
							'name': 'icona',
							'expand': False,
						},
						{
							'class': SP,
							'name': 'tratto',
							'expand': False,
						},
						{
							'class': HTML,
							'center': True,
							'style': 'indicazioni-orario',
							'name': 'tempo_a',
							'expand': False,
						},
						{
							'class': HTMLFlowPanel,
							'name': 'nodo_a',
							'expand': False,
						},
					],
				},
			],
			add_to_owner=True,
		)

		self.formatNodo(self.nodo_partenza, 'tempo_p', 'nodo_p', con_tempi=True)

		icona, hfp, d1, d2, escludi = self.owner.decodeResTratto(self.tratto, True, False)
		if escludi is not None:
			self.insertMenuItem(2,
				{
					'id': 'escludi',
					'text': _('Escludi questa linea'),
					'listener': escludi,
				},
			)
		icona.addStyleName('tratto')
		self.base.by_name('icona').add(icona)
		self.base.by_name('tratto').add(hfp)
		self.formatNodo(self.nodo_arrivo, 'tempo_a', 'nodo_a')

	def onSintesi(self):
		self.paginated_panel.selectIndex(0)

	def onTempiAttesa(self):
		self.owner.cercaLinea(self.id_palina, su_mappa=False)

	def onEscludi(self):
		pass

	def getMenu(self):
		return [
			{
				'id': 'sintesi',
				'text': _('Sintesi del percorso'),
				'listener': self.onSintesi,
			},
			{
				'id': 'opzioni',
				'text': _('Opzioni di viaggio'),
				'listener': self.owner.onOpzioni,
			},
			{
				'id': 'ritorno',
				'text': _('Cerca ritorno'),
				'listener': self.owner.onRitorno,
			},
			{
				'id': 'parti_qui',
				'text': _('Ricalcola da posizione attuale'),
				'listener': self.owner.onPartiQui,
			},
			{
				'id': 'email',
				'text': _('Invia per email'),
				'listener': self.owner.onEmail,
			},
			{
				'id': 'link',
				'text': _('Link al percorso'),
				'listener': self.owner.onGetLink,
			},
		]


class CercaPercorsoPanel(ScrollAdaptivePanel, KeyboardHandler, FocusHandler, DeferrablePanel):
	def __init__(self, owner):
		ScrollAdaptivePanel.__init__(self)
		DeferrablePanel.__init__(self)
		KeyboardHandler.__init__(self)
		self.owner = owner
		self.map = None
		self.carpooling = 0
		self.tipi_risorse_init = None
		self.base = VP(
			self,
			[	
				{
					'class': VP,
					'style': 'indicazioni',
					'sub': [
						{
							'class': Label,
							'args': [_('Dove')],
							'style': 'indicazioni-h1',
							'height': None,
						},
						{
							'class': GP,
							'column_count': 2,
							#'style': 'indicazioni',
							'sub': [
								{
									'class': Label,
									'args': [_("Da: ")],
									'expand': False,
								},
								{
									'class': HP,
									'sub': [
											{
												'class': FavSearchBox,
												'name': 'da',
												'call_addKeyboardListener': ([self], {}),
												'args': [client.servizi_autocompleta_indirizzo, None, 0, 100, False],
											},
											{
												'class': HP,
												'call_setVisible': ([False], {}),
												'name': 'da_list_holder',
												'sub': [
													{
														'class': ListBox,
														'name': 'da_list',
														'width': '100%',
														'height': '100%',
													},
												],
										},
										{
											'class': Button,
											'args': ['X', self.onChiudiDa],
											'width': '40px',
											'style': 'close-button',
										},
									]
								},
								{
									'class': Label,
									'args': [_("A: ")],
									'expand': False,
								}, 
								{
									'class': HP,
									'sub': [
											{
												'class': FavSearchBox,
												'name': 'a',
												'call_addKeyboardListener': ([self], {}),
												'args': [client.servizi_autocompleta_indirizzo, None, 0, 100, False],
											},
											{
												'class': HP,
												'call_setVisible': ([False], {}),
												'name': 'a_list_holder',
												'sub': [
													{
														'class': ListBox,
														'name': 'a_list',
														'width': '100%',
													},
												]
											},
											{
												'class': Button,
												'args': ['X', self.onChiudiA],
												'width': '40px',
												'style': 'close-button',
											}
									]
								},
							]
						},
						{
							'class': HP,
							'sub': [
								{
									'class': Button,
									'args': [_("Cerca"), self.onCerca],
									'name': 'cerca',
									'width': '49%',
								},
								{
									'class': SP,
									'sub': [],
									'width': '2%',
								},
								{
									'class': Button,
									'args': [_("Ritorno"), self.onScambia],
									'name': 'scambia',
									'width': '49%',
								},
							]
						},
						{
							'class': Label,
							'args': [_('Come: Trasporto pubblico')],
							'style': 'indicazioni-h1',
							'name': 'come_header',
							'height': None,
						},
						{
							'class': HP,
							'width': None,
							'name': 'selettore_modo',
							'sub': [
								{
									'class': GP,
									'column_count': 4,
									'sub': [
										{
											'class': ToggleImage,
											'args': ['modo_tpl.png', 'modo-inactive', 'modo-active', self.onModo, 1, False],
											'name': 'modo_tpl',
											'expand': False,
											'call_setTooltip': ([_("Trasporto pubblico")], {}),
											'call_setSize': (['39px', '40px'], {}),
										},
										{
											'class': ToggleImage,
											'args': ['modo_bnr.png', 'modo-inactive', 'modo-active', self.onModo, 3, False],
											'name': 'modo_bnr',
											'expand': False,
											'call_setTooltip': ([_("Bike and ride")], {}),
											'call_setSize': (['79px', '40px'], {}),
										},
										# {
										# 	'class': ToggleImage,
										# 	'args': ['modo_carpooling.png', 'modo-inactive', 'modo-active', self.onModo, 5, False],
										# 	'name': 'modo_carpooling',
										# 	'expand': False,
										# 	'call_setTooltip': ([_("Car pooling")], {}),
										# 	'call_setSize': (['39px', '40px'], {}),
										# 	'call_setVisible': ([False], {}),
										# },
										{
											'class': ToggleImage,
											'args': ['modo_auto.png', 'modo-inactive', 'modo-active', self.onModo, 0, False],
											'name': 'modo_auto',
											'expand': False,
											'call_setTooltip': ([_("Trasporto privato")], {}),
											'call_setSize': (['39px', '40px'], {}),
										},
										# {
										# 	'class': ToggleImage,
										# 	'args': ['modo_pnr.png', 'modo-inactive', 'modo-active', self.onModo, 2, False],
										# 	'name': 'modo_pnr',
										# 	'expand': False,
										# 	'call_setTooltip': ([_("Park and ride")], {}),
										# 	'call_setSize': (['79px', '40px'], {}),
										# },
										# {
										# 	'class': ToggleImage,
										# 	'args': ['modo_carsharing.png', 'modo-inactive', 'modo-active', self.onModo, 4, False],
										# 	'name': 'modo_carsharing',
										# 	'expand': False,
										# 	'call_setTooltip': ([_("Car sharing")], {}),
										# 	'call_setSize': (['39px', '40px'], {}),
										# },
									],
								},
							],
						},
					],
				},
				{
					'class': DP,
					'name': 'opzioni_avanzate',
					'title': _('Opzioni avanzate'),
					'sub': [{
						'class': VP,
						'style': 'indicazioni',
						'sub': [
							{
								'class': Label,
								'args': [_('Opzioni')],
								'style': 'indicazioni-h1',
								'height': None,
							},
							# {
							# 	'class': CheckBox,
							# 	'args': [_('Cerca un luogo lungo il percorso'), True],
							# 	'name': 'luogo',
							# 	'click_listener': self.onCercaLuogo,
							# },
							{
								'class': ListBox,
								'name': 'risorse',
								'style': 'big-list',
								'call_setVisibleItemCount': ([6], {}),
								'call_setMultipleSelect': ([True], {}),
								'call_setVisible': ([False], {}),
							},

							{
								'class': VP,
								'name': 'opzioni_car',
								'call_setVisible': ([False], {}),
								'sub': [
									{
										'class': Label,
										'args': [_('Permessi di accesso ZTL')],
										'style': 'indicazioni-h2',
									},
									{
										'class': ListBox,
										'name': 'ztl',
										'style': 'big-list',
										'call_setVisibleItemCount': ([6], {}),
										'call_setMultipleSelect': ([True], {}),
									},
									{
										'class': MyAnchor,
										'name': 'ztl_all',
										'args': [1, ],
									},
								],
							},
							{
								'class': VP,
								'name': 'opzioni_tpl',
								'sub': [
									{
										'class': Label,
										'args': [_('Propensione spostamenti a piedi')],
										'style': 'indicazioni-h2',
									},									
									{
										'class': RadioButton,
										'args': ['piedi', _('Bassa (camminatore lento)')],
										'name': 'piedi_0',	
									},
									{
										'class': RadioButton,
										'args': ['piedi', _('Media')],
										'name': 'piedi_1',
										'checked': True,
									},
									{
										'class': RadioButton,
										'args': ['piedi', _('Alta (camminatore veloce)')],
										'name': 'piedi_2',
									},
									{
										'class': Label,
										'args': [_('Mezzi pubblici da utilizzare')],
										'style': 'indicazioni-h2',
									},									
									{
										'class': CheckBox,
										'args': [_('Autobus e tram'), True],
										'name': 'bus',
										'checked': True,						
									},
									{
										'class': CheckBox,
										'args': [_('Metropolitana'), True],
										'name': 'metro',
										'checked': True,						
									},
									{
										'class': CheckBox,
										'args': [_('Ferrovie urbane'), True],
										'name': 'ferro',
										'checked': True,						
									},
									{
										'class': CheckBox,
										'args': [_('Teletrasporto'), True],
										'name': 'teletrasporto',
										'checked': False,
										'call_setVisible': ([False], {}),	
									},
								],
							},
							{
								'class': VP,
								'name': 'opzioni_bnr',
								'call_setVisible': ([False], {}),
								'sub': [
									{
										'class': CheckBox,
										'args': [_('Porta la bici sui mezzi pubblici'), True],
										'name': 'bici_sul_tpl',
										'checked': False,
									},
									{
										'class': HP,
										'sub': [
											{
												'class': HTML,
												'args': [_('Max distanza in bici:&nbsp;')],
												'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
											},
											{
												'class': TextBox,
												'name': 'max_distanza_bici',
												'call_setVisibleLength': ([3], {}),
												'call_setText': (['5'], {}),
												'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
											},
											{
												'class': HTML,
												'args': [_('&nbsp;km')],
												'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
											},
										],
									},
								],
							},
							{
								'class': VP,
								'name': 'opzioni_pnr',
								'call_setVisible': ([False], {}),
								'sub': [
									{
										'class': Label,
										'args': [_('Parcheggi Park and Ride')],
										'style': 'indicazioni-h2',
									},									
									{
										'class': CheckBox,
										'args': [_('Parcheggi di scambio'), True],
										'name': 'parcheggi_scambio',
										'checked': True,					
									},
									{
										'class': CheckBox,
										'args': [_('Autorimesse private'), True],
										'name': 'parcheggi_autorimesse',
										'checked': False,	
									},
								],
							},
							{
								'class': VP,
								'name': 'altre_opzioni',
								'call_setVisible': ([False], {}),
								'sub': []
							},
							{
								'class': Label,
								'args': [_('Quando')],
								'style': 'indicazioni-h1',
								'height': None,
							},
							{
								'class': RadioButton,
								'args': ['quando', _('Adesso')],
								'name': 'quando_0',
								'checked': True,
							},
							{
								'class': RadioButton,
								'args': ['quando', _('Fra 5 minuti')],
								'name': 'quando_1',
							},
							{
								'class': HP,
								'width': None,
								'sub': [
									{
										'class': RadioButton,
										'args': ['quando', _('Parti alle:&nbsp;'), True],
										'name': 'quando_2',
										'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
									},											
									{
										'class': RadioButton,
										'args': ['quando', _('Arriva alle:&nbsp;'), True],
										'name': 'quando_3',
										'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
									},											
								]
							},
							{
								'class': HP,
								'width': None,
								'sub': [										
									{
										'class': DateField,
										'args': ['%d/%m/%Y'],
										'name': 'data',
										'call_addChangeListener': ([self.onDateTimeChanged], {}),
										'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
									},
									{
										'class': HTML,
										'args': [_('&nbsp;&nbsp;Ore:&nbsp;')],
										'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
									},											
									{
										'class': TimeBox,
										'name': 'ora',
										'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
										'call_addChangeListener': ([self.onDateTimeChanged], {}),
									},											
								]
							},
							{
								'class': HP,
								'sub': [
									{
										'class': Button,
										'args': [_("Cerca"), self.onCerca],
										'name': 'cerca2',
										'width': '49%',
									},
									{
										'class': SP,
										'sub': [],
										'width': '2%',
									},
									{
										'class': Button,
										'args': [_("Ritorno"), self.onScambia],
										'name': 'scambia2',
										'width': '49%',
									},
								]
							},
						]
					}],
				},
				{
					'class': VP,
					'name': 'risultati_holder',
					'sub': [],
				},
				{
					'class': HTML,
					'style': 'indicazioni',
					'name': 'informazioni_su',
					'args': [
						_("""
						<p>
							Questo servizio calcola il miglior percorso con i mezzi
							Atac, Roma TPL e le ferrovie regionali Trenitalia.
							Usa i dati in tempo reale per tener conto dello stato
							del traffico e della posizione degli autobus.
						<p>
						</p>
							Roma mobile deriva da Muoversi a Roma (muovi.roma.it),
							originariamente sviluppato dall'Agenzia per la Mobilit&agrave;
							di Roma, e <a href="https://bitbucket.org/lallulli/muoversi-a-roma" target="_blank">pubblicato con licenza open source.</a>
						</p>
						<p>
							&copy; %d Roma mobile</a>
						</p>
						""") % datetime.now().year
					],
				},

			],
			add_to_owner=True,
		)
		
		self.base.by_name('modo_tpl').setActive(True)
		self.modo = 1
		self.get_ztl = []
		ztl_all = self.base.by_name('ztl_all')
		ztl_all.setWidget(HTML(_('Seleziona tutte')))
		ztl_all.addClickListener(self.onZtlAll)
		self.risultati = None
		n = datetime.now()
		
		if n.day == 1 and n.month == 4:
			self.base.by_name('teletrasporto').setVisible(True)
		
		self.base.by_name('data').getTextBox().setText(n.strftime('%d/%m/%Y'))
		self.base.by_name('ora').getTextBox().setText(n.strftime('%H:%M'))
		self.cp_layer = None
		self.linee_escluse = None
		self.percorsi_realtime = []
		self.usa_dss = False
		
		# self.realtime = Button("Tempo reale off", self.onRealtime)
		# self.realtime.addStyleName('realtime')
		# self.realtime.setVisible(False)
		# self.realtime_status = False
		# self.owner.owner.add(self.realtime)

		self.cercaLuogoInit = False
		self.navigator_on = False
		self.timer_navigator = Timer(notify=self.navigatorUpdate)

		# Mapping tra gli indici degli elementi del risultato del cerca percorso, e gli indici dei tratti
		# (escludendo quindi i nodi)
		self.indice_tratto = {}


	def scrollaAOpzioni(self):
		self.base.by_name('opzioni_avanzate').setOpen(True)
		self.base.getElement().scrollIntoView()


	def scrollaAPercorso(self):
		if self.risultati is not None:
			self.risultati.getElement().scrollIntoView()

	def navigatorStart(self):
		self.navigator_on = True
		self.navigatorUpdate()

	def navigatorUpdate(self):
		if self.navigator_on:
			get_location(self.navigatorOnLocation, self.navigatorOnLocationError)

	def navigatorOnLocation(self, lng, lat):
		if self.navigator_on:
			client.percorso_posizione_attuale(lng, lat, JsonHandler(self.navigatorOnPosizioneAttualeDone, self.navigatorOnLocationError))

	def navigatorOnPosizioneAttualeDone(self, res):
		if self.navigator_on:
			indice_el = res['indice_percorso']
			indice_tr = self.indice_tratto[indice_el]
			self.pannello_riepilogo.selectIndex(indice_tr + 1)
			#self.timer_navigator.schedule(res['refresh'] * 1000)
			self.timer_navigator.schedule(10000)


	def navigatorOnLocationError(self):
		if self.navigator_on:
			self.timer_navigator.schedule(10000)

	def navigator_stop(self):
		self.navigator_on = False
		self.timer_navigator.cancel()

		
	def cambiaModo(self, modo):
		modi = ['modo_auto', 'modo_tpl', 'modo_pnr', 'modo_bnr', 'modo_carsharing', 'modo_carpooling']
		come = [_('Trasporto privato'), _('Trasporto pubblico'), _('Park and Ride'), _('Bike and Ride'), _('Car Sharing'),  _('Car Pooling')]
		self.base.by_name(modi[self.modo]).setActive(False)
		self.modo = modo
		self.base.by_name(modi[self.modo]).setActive(True)
		tpl = False
		pnr = False
		bnr = False
		car = False
		luoghi = True
		if self.modo == 0:
			car = True
		if self.modo == 1:
			tpl = True
		elif self.modo == 2:
			tpl = True
			pnr = True
			luoghi = False
			car = True
		elif self.modo == 3:
			tpl = True
			bnr = True
		elif self.modo == 4:
			tpl = True
			luoghi = False
		elif self.modo == 5:
			tpl = True
			luoghi = False
		self.base.by_name('opzioni_tpl').setVisible(tpl)
		self.base.by_name('opzioni_bnr').setVisible(bnr)
		self.base.by_name('opzioni_pnr').setVisible(pnr)
		self.base.by_name('opzioni_car').setVisible(car)
		if not luoghi:
			# self.base.by_name('luogo').setChecked(False)
			self.base.by_name('risorse').setVisible(False)
		# self.base.by_name('luogo').setVisible(luoghi)
		self.base.by_name('come_header').setText(_("Come: %s") % come[self.modo])
		if car:
			self.getZtl()

	def onDateTimeChanged(self):
		if self.base.by_name('quando_0').isChecked() or self.base.by_name('quando_1').isChecked():
			self.base.by_name('quando_2').setChecked(True)

	def onModo(self, sender):
		self.cambiaModo(sender.data)
		if self.base.by_name('da') != "" and self.base.by_name('a') != "":
			self.cercaPercorso()
			
	def onRisorsaListaTipiDone(self, res):
		risorse = self.base.by_name('risorse')
		if self.tipi_risorse_init is not None:
			trs = set(self.tipi_risorse_init)
		else:
			trs = set()
		i = 0
		for r in res:
			risorse.addItem(r['nome'], r['id'])		
			risorse.setItemSelected(i, r['id'] in trs)
			i += 1
			
	def selectRisorse(self, tipi):
		trs = set(tipi)
		risorse = self.base.by_name('risorse')
		n = risorse.getItemCount()
		for i in range(n):
			risorse.setItemSelected(i, risorse.getItemText(i) in trs)

	def onZtlListaDone(self, res):
		ztl = self.base.by_name('ztl')
		i = 0
		for r in res:
			ztl.addItem(r['descrizione'], r['id_ztl'])
			ztl.setItemSelected(i, r['id_ztl'] in self.get_ztl)
			i += 1
		self.get_ztl = None

	def getZtl(self):
		if self.get_ztl is not None:
			client.ztl_get_lista(JsonHandler(self.onZtlListaDone))

	def onZtlAll(self):
		ztl = self.base.by_name('ztl')
		n = ztl.getItemCount()
		for i in range(n):
			ztl.setItemSelected(i, True)

	def getSelectedZtl(self):
		return self.base.by_name('ztl').getSelectedValues()

	def decodeResTratto(self, t, dettaglio, riepilogo):
		"""
		Decode a dict corresponding to a route part.

		Return (image, description, linea, quanto)
		- image: Image
		- description: HtmlFlowPanel (iff dettaglio)
		- linea: widget linea (iff riepilogo)
		- quanto: indicazioni sulla durata del tratto (iff riepilogo)
		- escludi: callback per ricalcolare il percorso escludendo la linea del tratto; None se non è una linea
		"""
		icona = Image(make_absolute("/percorso/s/img/%s" % t['icona']))

		out = linea = quanto = None
		escludi = None

		if dettaglio:
			out = HTMLFlowPanel()
			def addHtml(hfp, w):
				hfp.addHtml(w)
			def add(hfp, w):
				hfp.add(w)
			def addBr(hfp):
				hfp.addBr()
			def addAnchor(hfp, a, b):
				hfp.addAnchor(a, b)
		else:
			def addHtml(hfp, w):
				pass
			def add(hfp, w):
				pass
			def addBr(hfp):
				pass
			def addAnchor(hfp, a):
				pass

		mezzo = t['mezzo']
		tipo_attesa = t['tipo_attesa']
		if mezzo == 'Z':
			addHtml(out, 'Teletrasporto')
		elif mezzo == 'I':
			addHtml(out, _('Cambia linea'))
		else:
			if mezzo in ['P', 'C', 'CP', 'A', 'CS']:
				if mezzo =='P':
					desc = _('A piedi')
				elif mezzo == 'C':
					desc = _('In bici')
				elif mezzo == 'CP':
					desc = _('Car pooling')
					# w = CarPoolingChiediPanel(self, t['id'])
				elif mezzo == 'A':
					desc = _('In automobile')
				elif mezzo == 'CS':
					desc =_('Car sharing')
				addHtml(out, desc)
				if tipo_attesa == 'Z':
					addBr(out)
					addHtml(out, _('Apertura ZTL ore&nbsp;'))
					addHtml(out, " %s" % t['tempo_attesa'])
				if riepilogo:
					linea = HTML() #desc)
			else:
				if mezzo == 'B':
					addHtml(out, _('Linea&nbsp;'))
				linea = t['linea_short']
				id_linea = t['id_linea']
				ll = LineaLabel(linea)
				add(out, ll)
				addHtml(out, _("&nbsp;direz. ") + t['dest'])
				addBr(out)
				escludi = self.onEscludiFactory(id_linea, linea)
				ll.addCloseListener(escludi)
				id_percorso = t['id'].split('-')[-1]
				ll.addLineaListener(self.onLineaFactory(id_percorso))
				if mezzo == 'B':
					self.percorsi_realtime.append(id_percorso)
				if tipo_attesa == 'O':
					addHtml(out, _('Partenza ore&nbsp;'))
				elif tipo_attesa == 'S':
					addHtml(out, _('Attesa circa&nbsp;'))
				elif tipo_attesa == 'P' and t['numero'] == 0:
					addHtml(out, _('In arrivo fra&nbsp;'))
				elif tipo_attesa == 'P' and t['numero'] > 0:
					addHtml(out, _('In arrivo dopo&nbsp;'))
				addHtml(out, " %s" % t['tempo_attesa'])
				if riepilogo:
					linea = ll
			addBr(out)
			sp = SimplePanel()
			addAnchor(out, t['info_tratto'], self.onInfoEsteseFactory(sp, t['info_tratto_exp']))
			addBr(out)
			add(out, sp)
			if riepilogo:
				quanto = HTML(t['info_tratto_short'])
		return icona, out, linea, quanto, escludi

		
	# def onCercaLuogo(self):
	# 	v = self.base.by_name('luogo').isChecked()
	# 	self.base.by_name('opzioni_avanzate').setOpen(True)
	# 	self.base.by_name('risorse').setVisible(v)
	# 	q3 = self.base.by_name('quando_3')
	# 	if v and q3.isChecked():
	# 		self.base.by_name('quando_0').setChecked(True)
	# 	if not self.cercaLuogoInit:
	# 		self.cercaLuogoInit = True
	# 		if self.tipi_risorse_init is None:
	# 			self.tipi_risorse_init = []
	# 		client.risorse_lista_tipi(self.tipi_risorse_init, JsonHandler(self.onRisorsaListaTipiDone))
		

	def availableParams(self):
		return [
			'da',
			'a',
			'bus',
			'metro',
			'ferro',
			'usa_dss',
			'mezzo',
			'piedi',
			'quando',
			'max_distanza_bici',
			'bici_sul_tpl',
			'dt',
			'linee_escluse',
			'carpooling',
			'tipi_ris',
			'ztl',
			'cp', # cp deve essere l'ultimo parametro
		]
		
	def setParam(self, param, value):
		if param == 'carpooling':
			self.carpooling = value
		if param == 'da':
			self.base.by_name('da').setText(value)	
		if param == 'a':
			self.base.by_name('a').setText(value)						
		if param == 'bus':
			self.base.by_name('bus').setChecked(value==1)
		if param == 'metro':
			self.base.by_name('metro').setChecked(value==1)
		if param == 'ferro':
			self.base.by_name('ferro').setChecked(value==1)
		if param == 'quando':
			self.base.by_name('quando_%d' % value).setChecked(True)
		if param == 'usa_dss':
			self.usa_dss = True
			self.cambiaModo(0)
		if param == 'mezzo':
			self.cambiaModo(int(value))
		if param == 'piedi':
			self.base.by_name('piedi_%d' % value).setChecked(True)			
		if param == 'max_distanza_bici':
			self.base.by_name('max_distanza_bici').setText(value)
		if param == 'bici_sul_tpl':
			self.base.by_name('bici_sul_tpl').setChecked(value=='1')
		if param == 'dt':
			self.base.by_name('data').getTextBox().setText('%s/%s/%s' % (value[8:10], value[5:7], value[:4]))
			self.base.by_name('ora').setText('%s:%s' % (value[11:13], value[14:16]))
		if param == 'linee_escluse':
			self.linee_escluse = {}
			if value != '-':
				le = value.split(',')
				for l in le:
					i = l.find(':')
					self.linee_escluse[l[:i]] = l[i + 1:]
		if param == 'tipi_ris' and self.modo == 2:
			tipi_ris = value.split(",")
			self.base.by_name('parcheggi_scambio').setChecked('Parcheggi di scambio' in tipi_ris)
			self.base.by_name('parcheggi_autorimesse').setChecked('Autorimesse' in tipi_ris)
		if param == 'ztl':
			self.get_ztl = value.split(",")
		if param == 'cp':
			self.owner.showSidePanel()
			self.cercaPercorso()

	def setupDss(self):
		parent = self.base.by_name('altre_opzioni')
		self.dss_base =  VP(parent, [
			{
				'class': HP,
				'sub': [
					{
						'class': HTML,
						'args': ['k =&nbsp;'],
						'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
					},
					{
						'class': TextBox,
						'name': 'dss_k',
						'call_setVisibleLength': ([3], {}),
						'call_setText': (['1'], {}),
						'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
					},
				],
			},
			{
				'class': CheckBox,
				'args': ['Abilitato al transito nelle ZTL', True],
				'name': 'dss_ztl',
			},
		])
		parent.add(self.dss_base)
		parent.setVisible(True)
		self.base.by_name('opzioni_car').setVisible(False)
		# self.base.by_name('luogo').setVisible(False)
		self.base.by_name('selettore_modo').setVisible(False)
		self.base.by_name('informazioni_su').setVisible(False)
		self.k_layers = []


	def onChange(self, el):
		el.removeStyleName('validation-error')
		
	def onFocus(self, text):
		text.selectAll()
				
	def setMap(self, map):
		self.map = map
		self.map.addRightClickOption(_("Cerca percorso da qui"), self.onRightClickDa)
		self.map.addRightClickOption(_("Cerca percorso fino a qui"), self.onRightClickA)
		
	# def onRealtime(self):
	# 	self.realtime_status = not self.realtime_status
	# 	self.realtime.setText("Tempo reale %s" % ("on" if self.realtime_status else "off"))
	# 	for id_percorso in self.percorsi_realtime:
	# 		self.map.loadNewLayer("%s*" % id_percorso, 'percorso_tiny', id_percorso, toggle=self.realtime_status)

		
	def onRightClickDa(self, lat, lng):
		da = self.base.by_name('da')
		da.setText('punto:(%0.4f,%0.4f)' % (lat, lng))
		a = self.base.by_name('a')
		if a.getText() != '':
			self.onCerca()
		else:
			self.createCpLayer()
		if self.cp_layer is not None:
			m = Marker(
				self.cp_layer,
				(lng, lat),
				make_absolute('/paline/s/img/partenza_percorso.png'),
				icon_size=(32, 32),
				anchor=(16, 32),
				drop_callback=self.onRightClickDa,
			)
			
			
	def onRightClickA(self, lat, lng):
		a = self.base.by_name('a')
		a.setText('punto:(%0.4f,%0.4f)' % (lat, lng))
		da = self.base.by_name('da')
		if da.getText() != '':
			self.onCerca()				
		else:
			self.createCpLayer()
		if self.cp_layer is not None:
			m = Marker(
				self.cp_layer,
				(lng, lat),
				make_absolute('/paline/s/img/arrivo_percorso.png'),
				icon_size=(32, 32),
				anchor=(16, 32),
				drop_callback=self.onRightClickA,
			)			

		
	def ripristinaWidgets(self):
		for x, x_list, x_holder in [self.getWidgets(t) for t in (False, True)]:
			x.removeStyleName('validation-error')
			if not x.getVisible():
				x.setText(x_list.getSelectedItemText()[0])
				x_holder.setVisible(False)
				x.setVisible(True)


	def onKeyDown(self, sender, keycode, modifiers):
		if keycode == 13:
			self.onCerca()
			
	def onCerca(self):
		self.linee_escluse = None
		self.cercaPercorso()
		
	def createCpLayer(self):
		# self.owner.setTabMappaPercorso()
		if self.cp_layer is not None:
			self.cp_layer.destroy()
		self.map.hideAllLayers()
		self.cp_layer = Layer('cp_layer', _('Percorso trovato'), self.map)

	def impostaDa(self, da):
		self.base.by_name('da').setText(da)

	def impostaA(self, a):
		self.base.by_name('a').setText(a)
		
	def cercaPercorso(self, tipi_risorse=None, su_mappa=False):
		cerca = self.base.by_name('cerca')
		n = datetime.now().strftime('%d/%m/%Y %H:%M')
		quando = get_checked_radio(self.base, 'quando', range(4))
		offset = 0
		if quando == 1:
			offset = 5 * 60
		elif quando == 2 or quando == 3:
			data = self.base.by_name('data').getTextBox()
			ora = self.base.by_name('ora')
			data.removeStyleName('validation-error')
			ora.getTextBox().removeStyleName('validation-error')
			n = '%s %s' % (data.getText(), ora.getText())
		try:
			mdb = self.base.by_name('max_distanza_bici')
			max_distanza_bici = float(mdb.getText()) * 1000
			mdb.removeStyleName('validation-error')
		except Exception:
			mdb.addStyleName('validation-error')
			return
		tipi_ris = []
		# if self.base.by_name('luogo').isChecked():
		# 	if tipi_risorse is not None:
		# 		tipi_ris = tipi_risorse
		# 	else:
		# 		tipi_ris = self.base.by_name('risorse').getSelectedValues()
		da_in = self.getIndirizzo(False)
		a_in = self.getIndirizzo(True)
		
		if da_in != '' and a_in == '' and cerca.isEnabled():
			self.owner.cercaLinea(da_in)
		
		elif da_in != '' and a_in != '' and cerca.isEnabled():
			self.base.by_name('cerca').setEnabled(False)
			self.base.by_name('cerca2').setEnabled(False)
			wait_start()
			# cerca.setHTML('<img width="16" height="16" src="loading.gif" />')
			self.ripristinaWidgets()
			ztl = self.get_ztl
			if ztl is None:
				ztl = self.getSelectedZtl()

			opzioni = {
				'mezzo': 1 if self.modo == 3 else self.modo,
				'piedi': get_checked_radio(self.base, 'piedi', range(3)),
				'bus': self.base.by_name('bus').isChecked(),
				'metro': self.base.by_name('metro').isChecked(),
				'fc': self.base.by_name('ferro').isChecked(),
				'fr': self.base.by_name('ferro').isChecked(),
				'bici': self.modo == 3,
				'max_distanza_bici': max_distanza_bici,
				'teletrasporto': self.base.by_name('teletrasporto').isChecked(),
				'carpooling': 2 if self.modo == 5 else 0,
				'rev': quando == 3,
				'tipi_ris': tipi_ris,
				'parcheggi_scambio': self.base.by_name('parcheggi_scambio').isChecked(),
				'parcheggi_autorimesse': self.base.by_name('parcheggi_autorimesse').isChecked(),
				'ztl': ztl,
				'bici_sul_tpl': self.base.by_name('bici_sul_tpl').isChecked(),
			}
			if self.usa_dss and self.modo == 0:
				opzioni['usa_dss'] = True
				opzioni['dss_k'] = self.dss_base.by_name('dss_k').getText()
				opzioni['dss_ztl'] = self.dss_base.by_name('dss_ztl').isChecked()
				opzioni['dss_alg'] = 'pathrev' if self.base.by_name('quando_3').isChecked() else 'path'

			if self.linee_escluse is not None:
				opzioni['linee_escluse'] = self.linee_escluse
			if su_mappa:
				callback = self.onCercaDoneSuMappa
			else:
				callback = self.onCercaDone
			client.percorso_cerca(
				da_in,
				a_in,
				opzioni,				
				n,
				get_lang(),
				offset,
				JsonInteractiveHandler(callback, self.onCercaErroreRemoto)
			)
		
	def onEscludiFactory(self, id_linea, linea):
		def onEscludi():
			if self.linee_escluse is None:
				self.linee_escluse = {}
			self.linee_escluse[id_linea] = linea
			self.cercaPercorso()
		return onEscludi
	
	def onIncludiFactory(self, id_linea):
		def onIncludi():
			if id_linea in self.linee_escluse:
				del self.linee_escluse[id_linea]
			self.cercaPercorso()
		return onIncludi
	
	def onLineaFactory(self, id_percorso):
		def onLinea(source):
			self.owner.cercaLineaPercorso(id_percorso, su_mappa=True)
		return onLinea

	def cercaLinea(self, query, su_mappa=True):
		self.owner.cercaLinea(query, su_mappa)
	
	def onPalinaFactory(self, id_palina):
		def onPalina(source):
			self.cercaLinea(id_palina, su_mappa=True)
		return onPalina	
	
	def onInfoEsteseFactory(self, panel, info_ext):
		panel.w = None
		def onInfoEstese(self):
			if panel.w is not None:
				panel.remove(panel.w)
				panel.w = None
			else:
				h = HTML(info_ext)
				panel.add(h)
				panel.w = h
		return onInfoEstese
	
	# def cercaPercorsoRisorse(self, da, tipi, a=None):
	# 	self.base.by_name('da').setText(da)
	# 	if self.cercaLuogoInit:
	# 		self.selectRisorse(tipi)
	# 	else:
	# 		self.tipi_risorse_init = tipi
	# 	self.base.by_name('luogo').setChecked(True)
	# 	self.onCercaLuogo()
	# 	if a is not None:
	# 		self.base.by_name('a').setText(a)
	# 		self.cercaPercorso(self.tipi_risorse_init)
	
	def getWidgets(self, arrivo):
		if arrivo:
			x = self.base.by_name('a')
			x_list = self.base.by_name('a_list')
			x_holder = self.base.by_name('a_list_holder')
		else:
			x = self.base.by_name('da')
			x_list = self.base.by_name('da_list')
			x_holder = self.base.by_name('da_list_holder')
		return x, x_list, x_holder
	
	def onChiudiDa(self):
		x, x_list, x_holder = self.getWidgets(False)
		x_holder.setVisible(False)
		x.setVisible(True)
		x.setText('')
		x.setFocus()
		
	def onChiudiA(self):
		x, x_list, x_holder = self.getWidgets(True)
		x_holder.setVisible(False)
		x.setVisible(True)
		x.setText('')
		x.setFocus()

	def getIndirizzo(self, arrivo):
		x, x_list, x_holder = self.getWidgets(arrivo)
		if x.getVisible():
			return x.getText()
		return x_list.getSelectedItemText()[0]
	
	def abilitaCerca(self):
		self.base.by_name('cerca').setEnabled(True)
		self.base.by_name('cerca2').setEnabled(True)
		wait_stop()
		# cerca.setText('Cerca')
	
	def onCercaErroreRemoto(self, text, code):
		self.abilitaCerca()
		prnt(code)
		prnt(text)
				
	def onCercaErrore(self, el, arrivo):
		x, x_list, x_holder = self.getWidgets(arrivo)
		if el['stato'] == 'Ambiguous':
			x.setVisible(False)
			x_holder.setVisible(True)
			x_list.addStyleName('validation-error')
			x_list.clear()
			for i in el['indirizzi']:
				x_list.addItem(i)
		else:
			x.addStyleName('validation-error')

	def onCercaDoneSuMappa(self, res):
		self.onCercaDone(res, su_mappa=True)


	def onCercaDoneDss(self, res):
		risultati_holder = self.base.by_name('risultati_holder')
		risultati_holder.clear()

		for l in self.k_layers:
			l.destroy()

		Marker(
			self.cp_layer,
			res['start'],
			make_absolute('/paline/s/img/partenza_percorso.png'),
			icon_size=(32, 32),
			anchor=(16, 32),
			drop_callback=self.onRightClickDa,
		)

		Marker(
			self.cp_layer,
			res['stop'],
			make_absolute('/paline/s/img/arrivo_percorso.png'),
			icon_size=(32, 32),
			anchor=(16, 32),
			drop_callback=self.onRightClickA,
		)

		i = 0
		colors = ["#0000ff", "#ff0000", "#00ff00"]
		for percorso in res['percorsi']:
			color = colors[min(i, len(colors) - 1)]
			i += 1

			layer = Layer('k_layer_%d' % i, _('Percorso %d' % i), self.map)
			GeoJson(layer, percorso['geojson'], color=color)
			self.k_layers.append(layer)

			risultati = DP(
				None,
				[
					{
						'class': VP,
						'style': 'indicazioni',
						'sub': [
							{
								'class': GP,
								'column_count': 2,
								'name': 'proprieta',
								'sub': [],
							},
						]
					}
				],
				title=_('Percorso %d' % i),
			)

			prop = risultati.by_name('proprieta')
			stats = percorso['stats']
			for k in stats:
				name, value = k
				prop.add(HTML('<b>%s</b>:' % name))
				prop.add(HTML(value))

			risultati.setOpen(False)
			risultati_holder.add(risultati)

		self.owner.center_and_zoom(self.cp_layer)
		if self.owner.isSmall():
			self.do_or_defer(self.scrollaAPercorso)

		
	def onCercaDone(self, res, su_mappa=True):
		self.abilitaCerca()
		
		# Errori
		if 'errore-partenza' in res or 'errore-arrivo' in res:
			if 'errore-partenza' in res:
				self.onCercaErrore(res['errore-partenza'], False)
			if 'errore-arrivo' in res:
				self.onCercaErrore(res['errore-arrivo'], True)
			return
		
		if 'errore-data' in res:
			self.base.by_name('data').getTextBox().addStyleName('validation-error')
			self.base.by_name('ora').getTextBox().addStyleName('validation-error')
			return

		# OK
		if su_mappa:
			self.owner.setTabMappaPercorso()
		else:
			self.owner.setTabPercorsoMappa()
		self.createCpLayer()

		self.percorsi_realtime = []
		self.base.by_name('opzioni_avanzate').setOpen(False)

		# DSS
		if 'dss' in res:
			return self.onCercaDoneDss(res['dss'])

		risultati_holder = self.base.by_name('risultati_holder')
		if self.risultati is not None:
			risultati_holder.remove(self.risultati)
		
		self.risultati = DP(
			None,
			[ 
				{
					'class': VP,
					'style': 'indicazioni',
					'sub': [
						{
							'class': HP,
							'sub': [
								{
									'class': Label,
									'style': 'indicazioni-h1',
									'args': [_('Riepilogo')],
								},
								{
									'class': Image,
									'args': ["link.png"],
									'width': '41px',
									'height': '30px',
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
									'style': 'modo-inactive',
									'call_addClickListener': ([self.onGetLink], {}),
								},
								{
									'class': Image,
									'args': ["email.png"],
									'width': '40px',
									'height': '30px',
									'vertical_alignment': HasAlignment.ALIGN_MIDDLE,
									'style': 'modo-inactive',
									'call_addClickListener': ([self.onEmail], {}),
								},
							]
						},
						{
							'class': FlowPanel,
							'name': 'riepilogo',
							'args': [],
							'style': 'riepilogo',
						},
						{
							'class': Label,
							'args': [_('Esclusioni')],
							'style': 'indicazioni-h1',
							'height': None,
							'name': 'esclusioni-header'
						},											
						{
							'class': HTMLFlowPanel,
							'name': 'esclusioni',
							'args': [],
						},
						{
							'class': Label,
							'args': [_('Indicazioni')],
							'style': 'indicazioni-h1',
							'height': None,
						},									
						{
							'class': GP,
							'column_count': 2,
							'name': 'indicazioni',
							'sub': [],
						},
					]
				}
			],
			title=_('Percorso trovato'),
		)
		self.risultati.setOpen(True)
		indicazioni = self.risultati.by_name('indicazioni')
		count = 0
		numero_indicazioni = len(res['indicazioni'])

		# Riepilogo
		stat = res['stat']
		riepilogo = self.risultati.by_name('riepilogo')
		riepilogo.add(HTML(_("<b>Durata spostamento:</b> %s") % stat['tempo_totale_format']))
		riepilogo.add(HTML(_("<b>Distanza percorsa:</b> %s<br />") % stat['distanza_totale_format']))
		riepilogo.add(HTML(_("<b>Di cui a piedi:</b> %s") % stat['distanza_piedi_format']))
		
		# Esclusioni
		if len(res['linee_escluse']) > 0:
			self.linee_escluse = {}
			esclusioni = self.risultati.by_name('esclusioni')
			for el in res['linee_escluse']:
				id_linea, nome_linea = el['id_linea'], el['nome']
				ll = LineaLabel(nome_linea)
				ll.addCloseListener(self.onIncludiFactory(id_linea))
				esclusioni.add(ll)
				esclusioni.addHtml('&nbsp;')
				self.linee_escluse[id_linea] = nome_linea
		else:
			self.risultati.by_name('esclusioni-header').setVisible(False)

		# Costruisco pannello riepilogo
		self.pannello_riepilogo = self.owner.creaPannelloRiepilogo(height='150px')
		rpp = RiepilogoPercorsoPanel(self, stat, res['linee_escluse'])
		totali = len([x for x in res['indicazioni'] if 'tratto' in x])
		self.pannello_riepilogo.add(
			rpp,
			self.setBoundingBoxFactory(*res['bounding_box']),
			PaginatedPanel.generaPuntiPassi(-1, totali),
			menu_description=rpp.getMenu(),
		)

		# Indicazioni
		carpooling_trovato = False
		n_tratto = 0
		self.indice_tratto = {}
		for i in res['indicazioni']:
			count += 1
			
			# Tratto
			if 'tratto' in i:
				n_tratto += 1
				t = i['tratto']
				tpp = TrattoPercorsoPanel(
					self,
					res['indicazioni'][count - 2]['nodo'],
					t,
					res['indicazioni'][count]['nodo'],
				)
				self.pannello_riepilogo.add(
					tpp,
					self.setBoundingBoxFactory(*t['bounding_box']),
					PaginatedPanel.generaPuntiPassi(n_tratto - 1, totali),
					menu_description=tpp.getMenu(),
				)
				rpp.addTratto(t)
				self.indice_tratto[count - 1] = n_tratto

				def deferrable(indicazioni, t):
					def f():
						icona, hfp, d1, d2, escludi = self.decodeResTratto(t, True, False)
						indicazioni.addStyledWidget(icona, expand=False, center=True, style="tratto")
						indicazioni.addStyledWidget(hfp)
					return f

				self.do_or_defer(deferrable(indicazioni, t))


				
			# Nodo
			else:
				def deferrable_nodo(count, numero_indicazioni, indicazioni, n):
					def f():
						out = HTMLFlowPanel()

						partenza = False
						arrivo = False
						if count == 1:
							icona = 'partenza.png'
							partenza = True
						elif count == numero_indicazioni:
							icona = 'arrivo.png'
							arrivo = True
						else:
							icona = 'icon.png'
						vp = VP(
							indicazioni,
							[
								{
									'class': Image,
									'args': [make_absolute("/percorso/s/img/%s" % icona)],
									'width': '24px',
									'height': '24px',
									'horizontal_alignment': HasAlignment.ALIGN_CENTER,
								},
								{
									'class': HTML,
									'args': [n['t']],
									'horizontal_alignment': HasAlignment.ALIGN_CENTER,
									'style': 'indicazioni-orario',
								}
							],
							add_to_owner=False,
							expand=False,
							center=True
						)
						indicazioni.addStyledWidget(vp, expand=False, center=True, style="nodo")
						tipo = n['tipo']
						if tipo == 'F':
							out.addHtml(_("Fermata&nbsp;"))
						if tipo == 'L':
							ll = LineaLabel(n['nome'])
							out.add(ll)
							ll.addCloseListener(self.onEscludiFactory(n['id'], n['nome']))
							out.addHtml(n['info_exp'])
						elif n['url'] != '':
							out.addAnchor(n['nome'], self.onPalinaFactory(n['id']))
						else:
							out.addHtml(n['nome'])

						indicazioni.addStyledWidget(out)
					return f

				self.do_or_defer(deferrable_nodo(count, numero_indicazioni, indicazioni, i['nodo']))
				
		risultati_holder.add(self.risultati)

		if self.modo == 5 and not carpooling_trovato:
			pass
			# self.owner.setBottomWidget(CarPoolingNessunRisultatoPanel(self))
		elif self.modo == 0:
			pass
			# self.owner.setBottomWidget(CarPoolingOffriPassaggioPanel(self))

		self.cp_layer.deserialize(res['mappa'], callbacks={
			'drop_start': self.onRightClickDa,
			'drop_stop': self.onRightClickA,
		})
		self.owner.center_and_zoom(self.cp_layer)
		if self.owner.isSmall():
			self.do_or_defer(self.scrollaAPercorso)

		# self.navigatorStart()

		# if len(self.percorsi_realtime) > 0:
		# 	self.realtime_status = False
		# 	self.realtime.setVisible(True)
		# 	self.realtime.setText("Tempo reale off")

		
	def onScambia(self):
		da, a = self.base.by_name('da').getStatus(), self.base.by_name('a').getStatus()
		self.base.by_name('da').setStatus(*a)
		self.base.by_name('a').setStatus(*da)
		self.onCerca()

	def onPartiOra(self):
		self.base.by_name('quando_0').setChecked(True)
		self.onCerca()

	def onPartiQui(self):
		self.base.by_name('a').setText(self.owner.posizione)
		self.onPartiOra()

	def onRitorno(self):
		self.onScambia()

	def onOpzioni(self):
		self.owner.setTabPercorsoMappa()
		self.scrollaAOpzioni()


	def onGetLink(self):
		LinkDialog(self, self.base.by_name('da').getText(), self.base.by_name('a').getText())

	def onEmail(self):
		EmailDialog(self)

	def setBoundingBoxFactory(self, nw, se):
		def setBoundingBox():
			self.map.setBoundingBox(nw, se)
		return setBoundingBox

class LinkDialog(DialogBox, FocusHandler):
	def __init__(self, owner, origine, destinazione):
		DialogBox.__init__(self, glass=True)
		self.owner = owner

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_('Link al percorso completo:')],
					'style': 'indicazioni-h1',
					'height': None,
				},
				{
					'class': HTML,
					'args': [_("""
						Questo link mostrer&agrave; le indicazioni e la mappa del percorso
						da %s a %s.
					""") % (origine, destinazione)],
					'height': None,
				},
				{
					'class': TextBox,
					'name': 'route',
					'height': None,
					'call_addFocusListener': ([self], {}),

				},
				{
					'class': HTML,
					'args': [_('Link al cerca percorso fino a %s:') % destinazione],
					'style': 'indicazioni-h1',
					'height': None,
				},
				{
					'class': HTML,
					'args': [_("""
						Questo link chieder&agrave; un punto di partenza, a partire dal quale
						cercher&agrave; il percorso fino a %s.
					""") % destinazione],
					'height': None,
				},
				{
					'class': TextBox,
					'name': 'to',
					'height': None,
					'call_addFocusListener': ([self], {}),
				},
				{
					'class': Button,
					'args': [_('Chiudi'), self.onChiudi],
					'horizontal_alignment': HasAlignment.ALIGN_RIGHT,
					'height': None,
				},
			],
			add_to_owner=True,
		)
		self.setWidth('300px')
		self.addStyleName('indicazioni')
		client.percorso_get_params(JsonHandler(self.onPercorsoGetParams))
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)

	def onChiudi(self):
		self.hide()

	def onPercorsoGetParams(self, res):
		base_url = web_prefix + '/percorso/js/?'
		self.base.by_name('route').setText(base_url + res['route'])
		self.base.by_name('to').setText(base_url + res['to'])

	def onFocus(self, text):
		text.selectAll()

class EmailDialog(DialogBox):
	def __init__(self, owner):
		DialogBox.__init__(self, glass=True)
		self.owner = owner

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_('Indirizzo email del destinatario:')],
					'style': 'indicazioni-h1',
					'height': None,
				},
				{
					'class': TextBox,
					'name': 'email',
					'height': None,
				},
				{
					'class': HP,
					'sub': [
						{
							'class': Button,
							'args': [_('Invia'), self.onInvia],
							'height': None,
						},
						{
							'class': Button,
							'args': [_('Annulla'), self.onAnnulla],
							'height': None,
						},
					]
				},
			],
			add_to_owner=True,
		)
		client.percorso_get_params(JsonHandler(self.onPercorsoGetParams))
		self.addStyleName('indicazioni')
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)

	def onInvia(self):
		client.percorso_email(self.base.by_name('email').getText().strip(), JsonInteractiveHandler(self.onEmailDone))
		self.hide()

	def onEmailDone(self, res):
		pass

	def onAnnulla(self):
		self.hide()

	def onPercorsoGetParams(self, res):
		base_url = web_prefix + '/percorso/js/?'
		self.base.by_name('route').setText(base_url + res['route'])
		self.base.by_name('to').setText(base_url + res['to'])


class CarPoolingChiediPanel(SimplePanel):
	def __init__(self, owner, id_offerta):
		SimplePanel.__init__(self)
		self.owner = owner
		self.id_offerta = id_offerta

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Trovato un passaggio in car pooling")],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [_("Trovata un'offerta di passaggio in car pooling compatibile con il tuo spostamento.")],
					'height': None,
					'name': 'main',
				},
				{
					'class': HP,
					'sub': [
						{
							'class': Button,
							'args': [_('Chiedi un passaggio'), self.onChiedi],
							'height': None,
						},
						{
							'class': Button,
							'args': [_('Cerca un altro passaggio'), self.onEscludi],
							'height': None,
						},
					]
				},
			],
			add_to_owner=True,
		)
		self.addStyleName('indicazioni')
		self.id_linea_esclusa = None
		self.nome_linea_esclusa = None
		client.carpooling_dettaglio_offerta(id_offerta, False, JsonInteractiveHandler(self.onDettaglioOffertaDone))

	def onDettaglioOffertaDone(self, res):
		html = """
			<b>Da:</b> %(da_indirizzo)s (%(da_orario)s)<br />
			<b>A:</b> %(a_indirizzo)s (%(a_orario)s)<br />
			<b>Contributo suggerito:</b> %(costo)s &euro;<br />
			<b>Feedback offerente:</b> %(feedback_offerente)s / 5.0<br />
		"""	% res
		self.base.by_name('main').setHTML(html)
		self.id_linea_esclusa = res['id_linea_esclusa']
		self.nome_linea_esclusa = res['nome_linea_esclusa']

	def onDettaglioOffertaChiediDone(self, res):
		pass
		# self.owner.owner.setBottomWidget(CarPoolingChiestoPanel(self.owner))

	@enforce_login
	def onChiedi(self):
		client.carpooling_dettaglio_offerta(self.id_offerta, True, JsonInteractiveHandler(self.onDettaglioOffertaChiediDone))

	def onEscludi(self, res):
		if self.id_linea_esclusa is not None:
			if self.owner.linee_escluse is None:
				self.owner.linee_escluse = {}
			self.owner.linee_escluse[self.id_linea_esclusa] = self.nome_linea_esclusa
			self.owner.cercaPercorso()


class CarPoolingChiestoPanel(SimplePanel):
	def __init__(self, owner):
		SimplePanel.__init__(self)
		self.owner = owner

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Richiesta effettuata")],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [_("""
						La tua richiesta di passaggio &egrave; stata inviata. Riceverai una notifica con ulteriori dettagli
						quando l'offerente avr&agrave; accettato o rifiutato la richiesta.
					""")],
					'height': None,
					'name': 'main',
				},
				{
					'class': HP,
					'sub': [
						{
							'class': Button,
							'args': [_('Chiudi'), self.onChiudi],
							'height': None,
						},
					]
				},

			],
			add_to_owner=True,
		)
		self.addStyleName('pannello-carpooling')

	def onChiudi(self):
		self.owner.owner.setBottomWidget(None)


class CarPoolingNessunRisultatoPanel(SimplePanel):
	def __init__(self, owner):
		SimplePanel.__init__(self)
		self.owner = owner

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Nessun passaggio trovato")],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [_("""
						Nessun'offerta di passaggio soddisfa la tua richiesta. Ti proponiamo un percorso con i soli mezzi
						pubblici. In alternativa prova a modificare l'orario della ricerca, oppure
						offri tu stesso un passaggio in car pooling!
					""")],
					'height': None,
					'name': 'main',
				},
				{
					'class': HP,
					'sub': [
						{
							'class': Button,
							'args': [_('Offri un passaggio'), self.onOffri],
							'height': None,
						},
						{
							'class': Button,
							'args': [_('Chiudi'), self.onChiudi],
							'height': None,
						},
					]
				},

			],
			add_to_owner=True,
		)
		self.addStyleName('pannello-carpooling')

	def onOffri(self):
		self.owner.cambiaModo(0)
		self.owner.cercaPercorso()

	def onChiudi(self):
		self.owner.owner.setBottomWidget(None)


class CarPoolingOffriPassaggioPanel(SimplePanel):
	def __init__(self, owner):
		SimplePanel.__init__(self)
		self.owner = owner

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [_("Condividi il tuo viaggio")],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [_("""
						Fai car pooling, offri un passaggio! Se vuoi condividere il tuo viaggio, Roma mobile lo proporr&agrave;
						ad altri utenti che cercano un percorso, proprio come se la tua auto diventasse un autobus.
						Potrai anche accordarti con le persone a cui offri un passaggio per ricevere un contributo
						alle spese di viaggio, suggerito da Roma mobile.
					""")],
					'height': None,
					'name': 'main',
				},
				{
					'class': HP,
					'sub': [
						{
							'class': Button,
							'args': [_('Offri un passaggio'), self.onOffri],
							'height': None,
						},
						{
							'class': Button,
							'args': [_('No, grazie'), self.onChiudi],
							'height': None,
						},
					]
				},
			],
			add_to_owner=True,
		)
		self.addStyleName('pannello-carpooling')

	@enforce_login
	def onOffri(self):
		pass

	def onChiudi(self):
		self.owner.owner.setBottomWidget(None)