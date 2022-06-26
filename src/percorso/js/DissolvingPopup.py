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

from pyjamas.ui.Calendar import Calendar, DateField
from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.DisclosurePanel import DisclosurePanel
from pyjamas.ui.DialogBox import DialogBox
from pyjamas.ui.TabPanel import TabPanel
from pyjamas.ui.Grid import Grid
from pyjamas.ui.Frame import Frame
from pyjamas.ui.TextBox import TextBox
from pyjamas.ui.TextArea import TextArea
from pyjamas.ui.HTML import HTML
from pyjamas.ui.FlexTable import FlexTable
from pyjamas.ui.FlexCellFormatter import FlexCellFormatter
from pyjamas.ui.Label import Label
from pyjamas.ui.CheckBox import CheckBox
from pyjamas.ui.ListBox import ListBox
from pyjamas.ui.Button import Button
from pyjamas.ui.ToggleButton import ToggleButton
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
from pyjamas.ui import HasAlignment
from prnt import prnt

class DissolvingPopup(PopupPanel):
	
	old_dp = None
		
	def __init__(self, s, error=False):
		PopupPanel.__init__(self, autoHide=False, modal=False, glass=True)
		self.hp = HorizontalPanel()
		self.d1 = HTML("")
		self.d2 = HTML("")
		self.add(self.hp)
		self.hp.add(self.d1)
		self.hp.setCellWidth(self.d1, "50%")
		self.html = HTML(s)
		self.html.setWordWrap(False)
		self.html.setHorizontalAlignment(HasAlignment.ALIGN_CENTER)
		self.addStyleName("dissolving-popup")
		if not error:
			self.html.setStyleName("showcase-popup")
		else:
			self.html.setStyleName("showcase-popup-error")			
		self.hp.add(self.html)
		self.hp.add(self.d2)
		self.hp.setCellWidth(self.d2, "50%")
		self.setPopupPosition(0, 0)
		self.setWidth("100%")
		if DissolvingPopup.old_dp is not None:
			DissolvingPopup.old_dp.hide()
		DissolvingPopup.old_dp = self
		self.setGlassPosition()
		self.show()
		self.timer = Timer(2500 if error else 5000, self)
		#Window.addWindowResizeListener(self.setGlassPosition)

	def setGlassPosition(self): 
		top = Window.getScrollTop() 
		left = Window.getScrollLeft() 
		height = Window.getClientHeight() 
		width = Window.getClientWidth()
		self.setPopupPosition(left, top)

	def onTimer(self, t):
		self.hide()
		DissolvingPopup.old_dp = None

