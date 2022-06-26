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
from util import StyledFixedColumnFlexTable, HTMLFlowPanel, DP, VP, HP, GP, SP, DeferrablePanel, ScrollAdaptivePanel
from util import get_checked_radio, HidingPanel, ValidationErrorRemover, MyAnchor, LoadingButton
from util import SearchBox, _, get_lang, getdefault, LuogoPanel
from datetime import date, time, datetime, timedelta
from Calendar import Calendar, DateField, TimeField
from map import MapPanel, Layer, LayerPanel, Marker
from globals import make_absolute, base_url

from DissolvingPopup import DissolvingPopup
from util import JsonHandler, JsonInteractiveHandler, redirect


client = JSONProxy(base_url + '/json/', ['risorse_lista_tipi', 'servizi_autocompleta_indirizzo'])

class CRLuogoPanel(LuogoPanel):
	pass
	# def activateMarker(self):
	# 	self.owner.setActiveMarker(None)

class CercaLuogoPanel(ScrollAdaptivePanel, KeyboardHandler, FocusHandler, DeferrablePanel):
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
							'args': [_('Indirizzo')],
							'style': 'indicazioni-h1',
							'height': None,
						},			
						{
							'class': HP,
							'sub': [
								{
									'class': HP,
									'width': '70%',
									'sub': [							
										{
											'class': SearchBox,
											'name': 'query',
											'call_addKeyboardListener': ([self], {}),
											'args': [client.servizi_autocompleta_indirizzo, None, 0, 100, False],
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
												{
													'class': Button,
													'args': ['X', self.onChiudiQuery],
													'width': '40px',
													'style': 'close-button',
												},										
											]
										},											
									],
								},
								{
									'class': LoadingButton,
									'args': [_('Cerca'), self.onCerca],
									'width': '30%',
									'name': 'button',
								},									
							]
						},
						{
							'class': ListBox,
							'name': 'risorse',
							'style': 'big-list',
							'call_setVisibleItemCount': ([6], {}),
							'call_setMultipleSelect': ([True], {}),
						},
						{
							'class': MyAnchor,
							'name': 'risorse_percorso',
						},								
					]
				},
			],
			add_to_owner=True,						
		)
		
		self.cl_layer = None
		self.cr_lista_tipi = []
		self.cr_a = None
		rp = self.base.by_name('risorse_percorso')
		rp.setWidget(HTML(_('Cerca luogo lungo un percorso')))
		rp.addClickListener(self.onRisorsePercorso)
		client.risorse_lista_tipi([], JsonHandler(self.onRisorsaListaTipiDone))
		
	def availableParams(self):
		return [
			'cr_da',
			'cr_a',
			'cr_lista_tipi',
			'cr',
		]
		
	def setParam(self, param, value):
		if param == 'cr_da':
			self.base.by_name('query').setText(value)
		if param == 'cr_a':
			self.cr_a = value
		if param == 'cr_lista_tipi':
			self.cr_lista_tipi = value.split(',')
			client.risorse_lista_tipi(self.cr_lista_tipi, JsonHandler(self.onRisorsaListaTipiDone))
		if param == 'cr':
			if self.cr_a is None:
				self.ripristinaWidgets()
				self.cercaLuogo(self.base.by_name('query').getText(), self.cr_lista_tipi)
			else:
				self.owner.cercaPercorsoRisorse(
					self.base.by_name('query').getText(),
					self.cr_lista_tipi,
					self.cr_a,
				)
		
	def ripristinaWidgets(self):
		for x, x_list, x_holder in [self.getWidgets()]:
			x.removeStyleName('validation-error')
			if not x.getVisible():
				x.setText(x_list.getSelectedItemText()[0])
				x_holder.setVisible(False)
				x.setVisible(True)
		
	def onChange(self, el):
		el.removeStyleName('validation-error')
		
	def onFocus(self, text):
		text.selectAll()
		
	def setMap(self, map):
		self.map = map
		self.map.addRightClickOption(_("Luoghi vicini"), self.onRightClick)
		
	def onRightClick(self, lat, lng):
		query = self.base.by_name('query')
		query.setText('punto:(%0.4f,%0.4f)' % (lat, lng))
		self.owner.setTabMappaLuogo()
		self.onCerca()

	def onKeyDown(self, sender, keycode, modifiers):
		if keycode == 13:
			self.onCerca()

		
	def onCerca(self):
		self.ripristinaWidgets()
		self.cercaLuogo(self.base.by_name('query').getText())
		
	def cercaLuogo(self, query, tipi=None, set_input=False):
		query = query.strip()
		if set_input:
			self.base.by_name('query').setText(query)
		if query == '':
			self.onCercaErrore({'stato': 'Error'})
			return

		self.pannello_riepilogo = self.owner.creaPannelloRiepilogo(height='150px')

		def on_cpda():
			self.owner.cercaPercorsoDa(query)
		def on_cpa():
			self.owner.cercaPercorsoA(query)
		def on_cr():
			self.pannello_riepilogo.selectIndex(1)
		def on_cl():
			self.owner.cercaLinea(query, su_mappa=True, jump_to_result=True)
		luogo_panel = CRLuogoPanel(self, on_cpda, on_cpa, on_cl, on_cr)
		self.pannello_riepilogo.add(luogo_panel, title=query)

		if tipi is None:
			tipi = self.base.by_name('risorse').getSelectedValues()

		if len(tipi) > 0:
			self.map.loadNewLayer(
				'cerca_risorsa',
				'risorsa',
				(query, tipi, 2000),
				reload=True,
				info_panel=self.pannello_riepilogo,
				on_error=self.onCercaErrore,
				onDone=self.onCercaDone,
			)
		
		

	def onRisorsaListaTipiDone(self, res):
		trs = set(self.cr_lista_tipi)
		risorse = self.base.by_name('risorse')
		risorse.clear()
		i = 0
		for r in res:
			risorse.addItem(r['nome'], r['id'])		
			risorse.setItemSelected(i, r['id'] in trs)
			i += 1


				
	def onCercaErrore(self, el):
		self.owner.setTabLuogoMappa()
		x, x_list, x_holder = self.getWidgets()
		if el['stato'] == 'Ambiguous':
			x.setVisible(False)
			x_holder.setVisible(True)
			x_list.addStyleName('validation-error')
			x_list.clear()
			for i in el['indirizzi']:
				x_list.addItem(i)
		else:
			x.addStyleName('validation-error')
		self.owner.setBottomWidget(None)

	def onCercaDone(self, el):
		self.owner.setTabMappaLuogo()
		self.pannello_riepilogo.selectIndex(1)

	def getWidgets(self):
		x = self.base.by_name('query')
		x_list = self.base.by_name('query_list')
		x_holder = self.base.by_name('query_list_holder')
		return x, x_list, x_holder			
			
	def onChiudiQuery(self):
		x, x_list, x_holder = self.getWidgets()
		x_holder.setVisible(False)
		x.setVisible(True)
		
		
	def onRisorsePercorso(self):
		self.owner.cercaPercorsoRisorse(
			self.base.by_name('query').getText(),
			self.base.by_name('risorse').getSelectedValues(),
		)