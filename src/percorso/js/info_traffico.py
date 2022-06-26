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
from util import StyledFixedColumnFlexTable, HTMLFlowPanel, DP, VP, HP, GP, SP
from util import get_checked_radio, HidingPanel, ValidationErrorRemover
from util import LoadingButton, MyAnchor
from datetime import date, time, datetime, timedelta
from Calendar import Calendar, DateField, TimeField
from map import MapPanel, Layer, LayerPanel, Polygon

from DissolvingPopup import DissolvingPopup
from util import JsonHandler, redirect


client = JSONProxy('/json/', ['stato_traffico'])



class InfoTraffico(): #SimplePanel):
	def __init__(self, owner, map):
		#SimplePanel.__init__(self)
		self.owner = owner
		self.map = map
		self.layer_in = None
		self.layer_out = None
		self.layer_oscuramento = None
		self.onTrafficoIn()
		self.onTrafficoOut()
		self.oscuramento()
		"""
		self.base = VP(
			self,
			[
				{
					'class': LoadingButton,
					'args': ['Traffico in ingresso', self.onTrafficoIn],
					'height': None,
					'name': 'in',
				},
				{
					'class': LoadingButton,
					'args': ['Traffico in uscita', self.onTrafficoOut],
					'height': None,
					'name': 'out',
				},
			]
		)
		self.add(self.base)
		"""

		
	def onTrafficoIn(self):
		if self.layer_in is None:
			# self.base.by_name('in').start()
			client.stato_traffico('in', JsonHandler(self.onTrafficoInDone))
		else:
			self.layer_in.setVisible(True)
			self.layer_in.centerOnMap()		
				
	def onTrafficoOut(self):
		if self.layer_out is None:
			# self.base.by_name('out').start()
			client.stato_traffico('out', JsonHandler(self.onTrafficoOutDone))
		else:
			self.layer_out.setVisible(True)
			self.layer_out.centerOnMap()		


	def onTrafficoInDone(self, res):
		# self.map.hideAllLayers()
		self.layer_in = Layer('traffico-in', 'Traffico in ingresso', self.map)
		self.layer_in.deserialize(res['mappa'])
		self.layer_in.centerOnMap()
		# self.base.by_name('in').stop()
		
	def onTrafficoOutDone(self, res):
		# self.map.hideAllLayers()
		self.layer_out = Layer('traffico-out', 'Traffico in uscita', self.map)
		self.layer_out.deserialize(res['mappa'])
		self.layer_out.centerOnMap()		
		# self.base.by_name('out').stop()
		
	def setMap(self, map):
		self.map = map

	def oscuramento(self):
		if self.layer_oscuramento is None:
			self.layer_oscuramento = Layer('oscuramento', 'Oscuramento', self.map)
			Polygon(
				self.layer_oscuramento,
				[(10.0, 40.0), (13.0, 40.0), (13.0, 43.0), (10.0, 43.0)],
				0.8,
				'#000000',
				1,
				-10,
			)



