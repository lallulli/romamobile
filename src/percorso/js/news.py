from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.VerticalSplitPanel import VerticalSplitPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.StackPanel import StackPanel
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
from util import StyledFixedColumnFlexTable, HTMLFlowPanel, DP, VP, HP, GP, SP, DeferrablePanel, ScrollAdaptivePanel, \
	PreferitiImage
from util import get_checked_radio, HidingPanel, ValidationErrorRemover, MyAnchor, LoadingButton
from util import FavSearchBox, wait_start, wait_stop, getdefault, _, get_lang, MenuPanelItem
from datetime import date, time, datetime, timedelta
from Calendar import Calendar, DateField, TimeField
from map import MapPanel, Layer, LayerPanel, Marker, get_location
from globals import base_url, make_absolute


from DissolvingPopup import DissolvingPopup
from util import JsonHandler, JsonInteractiveHandler, redirect


client = JSONProxy(base_url + '/json/', [
	'news_tutte',
])

class SingleNewsPanel(VerticalPanel):
	def __init__(self, id_news, titolo, contenuto):
		VerticalPanel.__init__(self)
		self.setWidth('98%')
		self.addStyleName('news')
		a = MyAnchor()
		h = HTML(titolo)
		h.addStyleName('news-titolo')
		a.setWidget(h)
		a.addClickListener(self.onClick)
		self.add(a)
		self.testo = HTML(contenuto)
		self.testo.addStyleName('news-testo')
		self.testo.setVisible(False)
		self.add(self.testo)
		self.visible = False

	def onClick(self):
		self.visible = not self.visible
		if self.visible:
			self.addStyleName('news-selected')
		else:
			self.removeStyleName('news-selected')
		self.testo.setVisible(self.visible)


class NewsPanel(VerticalPanel):
	def __init__(self, owner):
		VerticalPanel.__init__(self)
		self.owner = owner
		self.header = MenuPanelItem(
			self,
			id='header',
			text=_('News'),
			icon='toolbar/back.png',
		)
		self.header.addStyleName('menu-header')
		self.add(self.header)
		self.sp = StackPanel()
		self.sp.setSize('100%', '100%')
		self.add(self.sp)
		self.setCellHeight(self.sp, '100%')
		wait_start()
		client.news_tutte(get_lang(), JsonInteractiveHandler(self.onNewsTutte))
		self.setSize('100%', '100%')

	def onNewsTutte(self, cs):
		self.sp.clear()
		for c in cs:
			cat = ScrollAdaptivePanel()
			cat.setWidth('100%')
			vp = VerticalPanel()
			vp.setWidth('100%')
			for n in c['news']:
				vp.add(SingleNewsPanel(n['id_news'], n['titolo'], n['contenuto']))
			cat.add(vp)
			self.sp.add(cat, "%s (%d)" % (c['nome_categoria'], len(c['news'])))
		wait_stop()

	def hide(self):
		self.owner.display_menu(False)

	def onClick(self):
		self.hide()


