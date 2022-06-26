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

from prnt import prnt
from __pyjamas__ import JS
from pyjamas import DOM
from pyjamas.ui.Calendar import Calendar, DateField
from pyjamas.ui.RootPanel import RootPanel
from pyjamas.ui.VerticalPanel import VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas.ui.ScrollPanel import ScrollPanel
from pyjamas.ui.FocusPanel import FocusPanel
from pyjamas.ui.DisclosurePanel import DisclosurePanel
from pyjamas.ui.DialogBox import DialogBox
from pyjamas.ui.TabPanel import TabPanel
from pyjamas.ui.Grid import Grid
from pyjamas.ui.Frame import Frame
from pyjamas.ui.TextBox import TextBox
from pyjamas.ui.TextArea import TextArea
from pyjamas.ui.HTML import HTML
from pyjamas.ui.FlowPanel import FlowPanel
from pyjamas.ui.FlexTable import FlexTable
from pyjamas.ui.Anchor import Anchor
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
from pyjamas.ui import HasAlignment, HorizontalSplitPanel, FocusListener
from pyjamas.JSONService import JSONProxy
from pyjamas.ui.MenuBar import MenuBar
from pyjamas.ui.MenuItem import MenuItem
from pyjamas.ui.Widget import Widget
from pyjamas.ui.Hyperlink import Hyperlink
from pyjamas import Window, History, DOM
from pyjamas.Timer import Timer
from datetime import date, time, datetime, timedelta
from DissolvingPopup import DissolvingPopup
from pyjamas.ui.HTMLPanel import HTMLPanel
from messages import messages
from globals import get_user, get_control, old_android, flavor, base_url

client = JSONProxy(base_url + '/json/', [
	'servizi_storage_set',
])


class JsonHandler():
	def __init__(self, callback=None, callback_error=None, data=None):
		self.callback = callback
		self.callback_error = callback_error
		self.data = data

	def onRemoteResponse(self, res):
		if self.callback is not None:
			if isinstance(self.callback, str):
				DissolvingPopup(self.callback)
			elif self.data is None:
				self.callback(res)
			else:
				self.callback(res, self.data)

	def onRemoteError(self, text, code):
		if self.callback_error is not None:
			if self.data is None:
				self.callback_error(text, code)
			else:
				self.callback(text, code, self.data)
		else:
			prnt(text)
			prnt(code)


class JsonInteractiveHandler(JsonHandler):
	def __init__(self, callback, callback_error=None, data=None, waiting_handler=None, error_popup=None):
		JsonHandler.__init__(self, callback, callback_error, data)
		self.waiting_handler = waiting_handler
		if self.waiting_handler is not None:
			self.waiting_handler.start()
		self.error_popup = _("Impossibile scaricare i dati, riprova") if error_popup is None else error_popup

	def onRemoteResponse(self, res):
		if self.waiting_handler is not None:
			self.waiting_handler.stop()
		wait_stop()
		return JsonHandler.onRemoteResponse(self, res)

	def onRemoteError(self, text, code):
		if self.waiting_handler is not None:
			self.waiting_handler.stop()
		wait_stop()
		if self.error_popup is not None:
			DissolvingPopup(self.error_popup, error=True)
		return JsonHandler.onRemoteError(self, text, code)


class WaitingHandler(object):
	def __init__(self,
							 els=None,
							 el_ids=None,
							 widgets=None,
							 custom_style='waiting-for-connection',
							 custom_start_callbacks=None,
							 custom_stop_callbacks=None,
							 ):
		object.__init__(self)
		if els is None:
			self.els = []
		else:
			self.els = els
		if el_ids is not None:
			self.addElementsById(el_ids)
		if widgets is not None:
			self.addWidgets(widgets)
		self.custom_style = custom_style
		self.custom_start_callbacks = custom_start_callbacks if custom_start_callbacks is not None else []
		self.custom_stop_callbacks = custom_stop_callbacks if custom_stop_callbacks is not None else []

	def start(self):
		for el in self.els:
			el.className += " " + self.custom_style
		for s in self.custom_start_callbacks:
			s()

	def stop(self):
		for el in self.els:
			styles = el.className.split(" ")
			el.className = " ".join([x for x in styles if x != self.custom_style])
		for s in self.custom_stop_callbacks:
			s()

	def addElementsById(self, el_ids):
		for i in el_ids:
			self.els.append(DOM.getElementById(i))

	def addElements(self, els):
		for el in els:
			self.els.append(el)

	def addWidgets(self, ws):
		for w in ws:
			self.els.append(w.getElement())

	def addStartCallbacks(self, cbs):
		self.custom_start_callbacks.extend(cbs)

	def addStopCallbacks(self, cbs):
		self.custom_stop_callbacks.extend(cbs)


class MyKeyboardHandler(KeyboardHandler):
	def __init__(self, callback):
		self.callback = callback

	def onKeyDown(self, res):
		self.callback()


def redirect(url):
	JS("""$wnd.location.replace(url);""")


def date2mysql(d):
	return d.strftime("%Y-%m-%d")


def mysql2date(s):
	return date(year=int(s[0:4]), month=int(s[5:7]), day=int(s[8:10]))


def date2italian(d):
	return d.strftime("%d/%m/%Y")


def italian2date(s):
	return date(year=int(s[6:10]), month=int(s[3:5]), day=int(s[0:2]))


def datetime2mysql(dt):
	return dt.strftime("%Y-%m-%d %H:%M:%S")


def mysql2datetime(s):
	return datetime(
		year=int(s[0:4]),
		month=int(s[5:7]),
		day=int(s[8:10]),
		hour=int(s[9:11]),
		minute=int(s[12:14]),
		second=int(s[15:17]),
	)


def validateMandatory(tbs):
	"""
	Verifica che tutte le textbox siano state riempite ed evidenzia le textbox non riempite

	tbs: lista ti textbox
	return: True sse tutte sono state riempite
	"""
	error = False
	for tb in tbs:
		if tb.getText() == '':
			tb.addStyleName('validation-error')
			error = True
	return not error


def validateInteger(tbs):
	"""
	Verifica che tutte le textbox contengano numeri interi ed evidenzia le textbox non riempite

	tbs: lista ti textbox
	return: True sse tutte contengono numeri interi
	"""
	error = False
	for tb in tbs:
		if not tb.getText().isdigit():
			tb.addStyleName('validation-error')
			error = True
	return not error


class ValidatingFieldsChangeListener():
	def onChange(self, widget):
		widget.removeStyleName('validation-error')

	def onKeyDown(self, sender, keycode, modifiers):
		sender.removeStyleName('validation-error')

	def onKeyUp(self, sender, keycode, modifiers):
		pass

	def onKeyPress(self, sender, keycode, modifiers):
		pass


vfcl = ValidatingFieldsChangeListener()


def setValidatingFields(fields):
	"""
	Add a listener to fields, such that validation-error style is removed
	when user changes field content
	"""
	for f in fields:
		f.addChangeListener(vfcl)
		f.addKeyboardListener(vfcl)


def emptyFields(fields):
	"""
	Clear content of textboxes
	"""
	for f in fields:
		f.setText('')


class DataButton(Button):
	"""
	Button holding some associated data
	"""

	def __init__(self, html, callback, data):
		"""
		callback is a function, not a class
		"""
		Button.__init__(self, html, getattr(self, "onButton"))
		self.data = data
		self.callback = callback

	def onButton(self):
		self.callback(self, self.data)


class MessageDialog(DialogBox):
	def __init__(self, message, title):
		DialogBox.__init__(self, glass=True)

		self.base = VP(
			self,
			[
				{
					'class': HTML,
					'args': [title],
					'height': None,
					'style': 'indicazioni-h1',
				},
				{
					'class': HTML,
					'args': [message],
					'height': None,
					'style': 'indicazioni',
				},
				{
					'class': Button,
					'args': [_('OK'), self.onOk],
					'height': None,
				},
			],
			add_to_owner=True,
		)
		self.addStyleName('indicazioni')
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)

	def onOk(self):
		self.hide()


class DisturbingMessageDialog(DialogBox):
	def __init__(self, message, title, id):
		DialogBox.__init__(self, glass=True)
		self.id = id

		if not storage_get('disturbing_%s' % id, False):
			self.base = VP(
				self,
				[
					{
						'class': HTML,
						'args': [title],
						'height': None,
						'style': 'indicazioni-h1',
					},
					{
						'class': HTML,
						'args': [message],
						'height': None,
						'style': 'indicazioni',
					},
					{
						'class': ButtonsPanel,
						'args': [[
							(_('OK'), self.onOk),
							(_('Non mostrare pi&ugrave;'), self.onNeverMore),
						]]
					},
				],
				add_to_owner=True,
			)
			self.addStyleName('indicazioni')
			self.show()
			left = (Window.getClientWidth() - self.getClientWidth()) / 2
			top = (Window.getClientHeight() - self.getClientHeight()) / 2
			self.setPopupPosition(left, top)

	def onOk(self):
		self.hide()

	def onNeverMore(self):
		storage_set('disturbing_%s' % self.id, True)
		self.hide()


class QuestionDialogBox(DialogBox):
	def __init__(self, title, question, answers):
		"""
		Init a dialog box with predefined answers

		Each answer has an associated callback function; it can be None if
		no other action than closing the dialog box is required

		title, question: strings
		answers: list of 3-ples with the form (answer_string, callback, data)
		"""
		DialogBox.__init__(self, glass=True)
		contents = VerticalPanel(StyleName="Contents", Spacing=4)
		contents.add(HTML(question))
		buttons = HorizontalPanel()
		contents.add(buttons)
		contents.setCellWidth(buttons, '100%')
		contents.setCellHorizontalAlignment(buttons, HasAlignment.ALIGN_RIGHT)
		buttons.setWidth('100%')
		perc = "%d%%" % (int(100 / len(answers)) - 1)
		n = len(answers)
		for i in range(n):
			a = answers[i]
			db = DataButton(a[0], self.onButton, (a[1], a[2]))
			db.setWidth('100%')
			buttons.add(db)
			buttons.setCellWidth(db, perc)
			if i < n - 1:
				buttons.add(HTML('&nbsp;'))
		self.setHTML('<b>%s</b>' % title)
		self.setWidget(contents)
		left = (Window.getClientWidth() - 200) / 2 + Window.getScrollLeft()
		top = (Window.getClientHeight() - 100) / 2 + Window.getScrollTop()
		self.setPopupPosition(left, top)

	def onButton(self, button, data):
		self.hide()
		callback = data[0]
		if callback is not None:
			callback(data[1])


class HourListBox(ListBox):
	def __init__(self):
		ListBox.__init__(self)
		for h in range(0, 24):
			ora = "%02d" % h
			self.addItem(ora, ora)

	def selectValue(self, v):
		v = "%02d" % int(v)
		return ListBox.selectValue(self, v)


class MinuteListBox(ListBox):
	def __init__(self):
		ListBox.__init__(self)
		for m in range(0, 60, 5):
			minuto = "%02d" % m
			self.addItem(minuto, minuto)

	def selectValue(self, v):
		v = "%02d" % int(v)
		return ListBox.selectValue(self, v)


class MyAnchor(Anchor):
	def __init__(self, max_parita=2, *args, **kwargs):
		Anchor.__init__(self, *args, **kwargs)
		self.my_parita = 0
		self.max_parita = max_parita
		self.widget = None

	def set_numero_eventi(self, n):
		self.max_parita = n

	def addClickListener(self, listener):
		self.my_original_listener = listener
		Anchor.addClickListener(self, self.myClickListener)

	def myClickListener(self, source):
		self.my_parita += 1
		if self.my_parita >= self.max_parita:
			self.my_parita = 0
			self.my_original_listener(source)

	def setWidget(self, widget):
		if self.widget is not None:
			self.removeWidget()
		self.widget = widget
		Anchor.setWidget(self, widget)


class HelpButton(HorizontalPanel):
	def __init__(self, text, align_right=False):
		HorizontalPanel.__init__(self)
		self.img = Image("question.png")
		self.add(self.img)
		if align_right:
			self.setWidth('100%')
			self.setCellHorizontalAlignment(self.img, HasAlignment.ALIGN_RIGHT)
		self.text = text
		self.img.addClickListener(self.showPopup)
		self.img.addStyleName('help-image')

	def showPopup(self, event):
		contents = HTML(self.text)
		contents.addClickListener(getattr(self, "onClick"))

		self._popup = PopupPanel(autoHide=True)
		self._popup.add(contents)
		self._popup.setStyleName("help-popup")
		pw = Window.getClientWidth()
		x = self.img.getAbsoluteLeft()
		y = self.img.getAbsoluteTop()
		left = x + 10 if pw - x > 300 else x - 300
		top = y + 10
		self._popup.setPopupPosition(left, top)
		self._popup.show()

	def onClick(self, sender=None):
		self._popup.hide()


class StyledFlexTable(FlexTable):
	def __init__(self, *args, **kwargs):
		FlexTable.__init__(self, *args, **kwargs)
		self.formatter = FlexCellFormatter(self)
		self.setCellFormatter(self.formatter)
		self.row = 0
		self.column = 0

	def newRow(self):
		self.row += 1
		self.column = 0

	def getRow(self):
		return self.row

	def addStyledWidget(self, w, style=None, center=False, expand=False, width=None):
		self.setWidget(self.row, self.column, w)
		if style is not None:
			self.formatter.addStyleName(self.row, self.column, style)
		if type(center) == bool:
			if center:
				self.formatter.setHorizontalAlignment(self.row, self.column, HasAlignment.ALIGN_CENTER)
		else:
			self.formatter.setHorizontalAlignment(self.row, self.column, center)
		if expand:
			self.formatter.setWidth(self.row, self.column, '100%')
			w.setWidth('100%')
		elif width is not None:
			self.formatter.setWidth(self.row, self.column, width)
			w.setWidth('100%')
		self.column += 1


class StyledFixedColumnFlexTable(StyledFlexTable):
	def __init__(self, *args, **kwargs):
		self.column_count = kwargs['column_count']
		del kwargs['column_count']
		StyledFlexTable.__init__(self, *args, **kwargs)

	def addStyledWidget(self, w, style=None, center=False, expand=False, width=None):
		StyledFlexTable.addStyledWidget(self, w, style, center, expand, width=width)
		if self.column == self.column_count:
			self.newRow()

	def add(self, w, center=True, expand=False):
		self.addStyledWidget(w, center=center, expand=expand)


class MatrixChoiceElem(FocusPanel):
	def __init__(self, owner, text):
		FocusPanel.__init__(self)
		self.text = text
		self.owner = owner
		self.add(HTML(text))
		self.addStyleName('matrix-choice-unselected')
		self.addClickListener(self.onClick)

	def onClick(self):
		self.owner.onSelected(self)

	def setSelected(self, selected=True):
		on = 'matrix-choice-selected'
		off = 'matrix-choice-unselected'
		if not selected:
			on, off = off, on
		self.removeStyleName(off)
		self.addStyleName(on)

	def getText(self):
		return self.text


class MatrixChoice(StyledFixedColumnFlexTable):
	def __init__(self, choices, onChange=None):
		"""
		choices is a list of lists, representing available choices
		"""
		StyledFixedColumnFlexTable.__init__(self, column_count=len(choices[0]))
		self.selected = None
		self.choices = choices
		self.onChange = onChange
		self.el_dict = {}
		for row in choices:
			for el in row:
				mce = MatrixChoiceElem(self, el)
				self.add(mce)
				self.el_dict[el] = mce

	def onSelected(self, mce, notify=True):
		if self.selected is not None:
			self.selected.setSelected(False)
		self.selected = mce
		mce.setSelected(True)
		if self.onChange is not None and notify:
			self.onChange(self.selected.getText())

	def getValue(self):
		if self.selected is None:
			return None
		return self.selected.getText()

	def setValue(self, value):
		if value in self.el_dict:
			self.onSelected(self.el_dict[value], False)


hour_choices = [
	['00', '12'],
	['01', '13'],
	['02', '14'],
	['03', '15'],
	['04', '16'],
	['05', '17'],
	['06', '18'],
	['07', '19'],
	['08', '20'],
	['09', '21'],
	['10', '22'],
	['11', '23'],
]
min_choices = [
	['00'],
	['05'],
	['10'],
	['15'],
	['20'],
	['25'],
	['30'],
	['35'],
	['40'],
	['45'],
	['50'],
	['55'],
]


class TimePicker(DialogBox):
	def __init__(self, onSelected, hour=0, minute=0):
		DialogBox.__init__(self, glass=True)

		self.vp = VerticalPanel()

		self.hour_value = hour
		self.minute_value = minute
		self.onSelected = onSelected

		self.time = HTML('')
		self.time.addStyleName('timepicker-time')
		self.vp.add(self.time)

		self.holder = HorizontalPanel()

		self.hour = VerticalPanel()
		ore_label = HTML(_("Ore"))
		ore_label.addStyleName('timepicker-label')
		self.hour.add(ore_label)
		self.hour_matrix = MatrixChoice(hour_choices, self.onHour)
		self.hour.add(self.hour_matrix)
		self.holder.add(self.hour)

		spacer = SimplePanel()
		self.holder.add(spacer)
		self.holder.setCellWidth(spacer, '100%')

		self.min = VerticalPanel()
		min_label = HTML(_("Min"))
		min_label.addStyleName('timepicker-label')
		self.min.add(min_label)
		self.min_matrix = MatrixChoice(min_choices, self.onMin)
		self.min.add(self.min_matrix)
		self.holder.add(self.min)

		self.vp.add(self.holder)

		self.commandBar = HorizontalPanel()
		self.ok = Button(_("OK"), self.onOk)
		self.ok.setWidth('95%')
		self.cancel = Button(_("Annulla"), self.onCancel)
		self.cancel.setWidth('100%')
		self.commandBar.add(self.ok)
		self.commandBar.add(self.cancel)
		self.commandBar.setCellWidth(self.ok, '50%')
		self.commandBar.setCellWidth(self.cancel, '50%')
		self.vp.add(self.commandBar)
		self.commandBar.setWidth('100%')

		self.update()
		self.hour_matrix.setValue("%02d" % self.hour_value)
		self.min_matrix.setValue("%02d" % self.minute_value)

		self.add(self.vp)
		self.show()
		left = (Window.getClientWidth() - self.getClientWidth()) / 2
		top = (Window.getClientHeight() - self.getClientHeight()) / 2
		self.setPopupPosition(left, top)

	def onOk(self):
		self.onSelected("%02d:%02d" % (self.hour_value, self.minute_value))
		self.hide()

	def onCancel(self):
		self.hide()

	def onHour(self):
		self.hour_value = int(self.hour_matrix.getValue())
		self.update()

	def onMin(self):
		self.minute_value = int(self.min_matrix.getValue())
		self.update()

	def update(self):
		self.time.setHTML("%02d:%02d" % (self.hour_value, self.minute_value))


class TimeBox(HorizontalPanel):
	def __init__(self, time="00:00"):
		HorizontalPanel.__init__(self)
		self.setVerticalAlignment(HasAlignment.ALIGN_MIDDLE)
		self.tb = TextBox()
		self.tb.setVisibleLength(5)
		self.tb.setText(time)
		self.add(self.tb)

		self.image = Image('icon_clock.gif')
		self.image.addClickListener(self.onImageClick)
		self.add(self.image)
		self.enabled = True
		self.change_listeners = []
		self.tb.addChangeListener(self.onChange)

	def getTextBox(self):
		return self.tb

	def onChange(self):
		for l in self.change_listeners:
			l()

	def addChangeListener(self, l):
		self.change_listeners.append(l)

	def onImageClick(self):
		if self.enabled:
			hour = 0
			min = 0
			try:
				time = self.tb.getText()
				hour = time[:2]
				min = time[3:5]
			except:
				pass
			TimePicker(self.onTimePicker, hour, min)

	def onTimePicker(self, time):
		self.tb.setText(time)
		self.onChange()

	def setText(self, time):
		self.tb.setText(time)

	def getText(self):
		return self.tb.getText()

	def setEnabled(self, enabled):
		self.enabled = enabled
		self.tb.setEnabled(enabled)


class AutofitHorizontalPanel(HorizontalPanel):
	def __init__(self, owner):
		HorizontalPanel.__init__(self)
		self.owner = owner
		self.setWidth('100%')
		self.owner.add(self)
		self.owner.setCellWidth(self, '100%')

	# self.owner.setCellVerticalAlignment(self, HasAlignment.ALIGN_MIDDLE)


class AutofitVerticalPanel(VerticalPanel):
	def __init__(self, owner):
		VerticalPanel.__init__(self)
		self.owner = owner
		self.setHeight('100%')
		self.owner.add(self)
		self.owner.setCellHeight(self, '100%')

	# self.owner.setCellHorizontalAlignment(self, HasAlignment.ALIGN_CENTER)


class Autofit(object):
	def __init__(self, owner):
		object.__init__(self)
		self.owner = owner
		self.owner.add(self)
		self.setSize('100%', '100%')
		self.owner.setCellWidth(self, '100%')
		self.owner.setCellHeight(self, '100%')


class HTMLFlowPanel(FlowPanel):
	"""
	Requires the following CSS class to be defined:
	.inl {
		display: inline-block;
		vertical-align: middle;
	}
	.inl-ie6 {
		display: inline;
		vertical-align: middle;
	}
	"""

	def setInl(self, w):
		w.addStyleName('inl')

	def add(self, w):
		self.setInl(w)
		FlowPanel.add(self, w)

	def addHtml(self, html, style=None):
		h = HTML(html)
		if style is not None:
			h.addStyleName(style)
		self.add(h)

	def addBr(self):
		FlowPanel.add(self, HTML(''))

	def addAnchor(self, text, callback):
		a = MyAnchor()
		h = HTML(text)
		self.setInl(h)
		a.setWidget(h)
		a.addClickListener(callback)
		self.add(a)


class HidingPanel(HorizontalPanel):
	def __init__(self, open=True):
		HorizontalPanel.__init__(self)
		self.content_panel = SimplePanel()
		self.content_panel.setSize('300px', '100%')
		HorizontalPanel.add(self, self.content_panel)

		hp = HorizontalPanel()
		hp.setSize('5px', '100%')
		hp.addStyleName('hiding-splitter')
		HorizontalPanel.add(self, hp)
		self.setCellWidth(hp, '5px')

		self.hider_panel = MyAnchor()
		hp.add(self.hider_panel)
		self.hider_panel.addClickListener(self.onHider)
		self.hider_panel.setSize('5px', '100%')
		hp.setCellWidth(self.hider_panel, '5px')
		self.hider_panel.addStyleName('hidePanel')
		self.setCellWidth(self.content_panel, '100%')
		self.hider_panel.set_numero_eventi(1)

		self.open_label = MyAnchor()
		# self.html_open_label = HTML("&nbsp;&laquo;&nbsp;")
		self.html_open_label = Image('toolbar/grip.png', Width='24px', Height='48px')
		self.open_label.setWidget(self.html_open_label)
		self.html_open_label.addStyleName('hiding-label-html')
		hp.add(self.open_label)
		# hp.setCellWidth(self.open_label, 0)
		self.open_label.addStyleName('hiding-label')
		self.open_label.addClickListener(self.onHider)

		self.hide_listener = None
		self.is_open = open
		self.update()

	def addHideListener(self, listener):
		self.hide_listener = listener

	def add(self, widget):
		# self.content_panel.remove(self.w)
		self.w = widget
		self.content_panel.add(widget)

	def update(self):
		self.content_panel.setVisible(self.is_open)
		"""
		if self.is_open:
			self.html_open_label.setHTML("&nbsp;&laquo;&nbsp;")
		else:
			self.html_open_label.setHTML("&nbsp;&raquo;&nbsp;")
		"""
		if self.hide_listener is not None:
			self.hide_listener(self)

	def onHider(self):
		self.is_open = not self.is_open
		self.update()

	def hide(self, hide=True):
		if self.is_open != (not hide):
			self.is_open = not hide
			self.update()


class AutoLayout:
	def __init__(self, owner, sub=[], add_to_owner=False, **kwargs):
		self.owner = owner
		self.sub = []
		self.dict = {}
		reserved_args = ['class', 'name', 'args', 'style', 'enabled', 'checked', 'click_listener',
										 'client_data'] + self.getReservedArgs()
		for l in sub:
			klass = l['class']
			res = dict([(x, l[x]) for x in l if x not in reserved_args and x[:5] != 'call_'])
			call = dict([(x[5:], l[x]) for x in l if x[:5] == 'call_'])
			args = []
			if issubclass(klass, AutoLayout):
				args.append(self)
			if 'args' in l:
				args.extend(l['args'])
			el = klass(*args, **res)
			if 'style' in l:
				el.addStyleName(l['style'])
			if 'enabled' in l:
				el.setEnabled(l['enabled'])
			if 'checked' in l:
				el.setChecked(l['checked'])
			if 'click_listener' in l:
				el.addClickListener(l['click_listener'])
			if 'client_data' in l:
				l.client_data = l['client_data']
			for f in call:
				getattr(el, f)(*(call[f][0]), **(call[f][1]))
			self.onCreate(el, l)
			self.sub.append(el)
			if 'name' in l:
				self.dict[l['name']] = el

		if owner is not None and add_to_owner:
			owner.add(self)

	def onCreate(self, el, kwargs):
		el.setSize('100%', '100%')
		self.add(el)

	def getReservedArgs(self):
		return []

	def by_name(self, name):
		if name in self.dict:
			return self.dict[name]
		for s in self.sub:
			if isinstance(s, AutoLayout):
				el = s.by_name(name)
				if el is not None:
					return el
		return None

	def __getitem__(self, name):
		return self.by_name(name)


class HP(HorizontalPanel, AutoLayout):
	def __init__(self, owner, sub=[], **kwargs):
		HorizontalPanel.__init__(self)
		AutoLayout.__init__(self, owner, sub, **kwargs)
		self.setHeight('100%')

	def onCreate(self, el, kwargs):
		# el.setSize('100%', '100%')
		self.add(el)
		if not 'width' in kwargs:
			el.setWidth('100%')
		if 'width' in kwargs:
			if kwargs['width'] is not None:
				el.setWidth('100%')
				self.setCellWidth(el, kwargs['width'])
		if not 'height' in kwargs:
			self.setCellHeight(el, '100%')
		elif kwargs['height'] is not None:
			self.setCellHeight(el, kwargs['height'])
		if 'vertical_alignment' in kwargs:
			self.setCellVerticalAlignment(el, kwargs['vertical_alignment'])
		if 'horizontal_alignment' in kwargs:
			self.setCellHorizontalAlignment(el, kwargs['horizontal_alignment'])

	def getReservedArgs(self):
		return ['width', 'height', 'vertical_alignment', 'horizontal_alignment']


class VP(VerticalPanel, AutoLayout):
	def __init__(self, owner, sub=[], **kwargs):
		VerticalPanel.__init__(self)
		AutoLayout.__init__(self, owner, sub, **kwargs)
		self.setWidth('100%')

	def onCreate(self, el, kwargs):
		if not 'width' in kwargs:
			el.setWidth('100%')
		elif kwargs['width'] is not None:
			el.setWidth(kwargs['width'])
		self.add(el)
		if 'height' in kwargs:
			if kwargs['height'] is not None:
				self.setCellHeight(el, kwargs['height'])
				el.setHeight('100%')
		else:
			self.setCellHeight(el, '100%')
			el.setHeight('100%')
		self.setCellWidth(el, '100%')
		if 'horizontal_alignment' in kwargs:
			self.setCellHorizontalAlignment(el, kwargs['horizontal_alignment'])

	def getReservedArgs(self):
		return ['height', 'width', 'horizontal_alignment']


class DP(DisclosurePanel, AutoLayout):
	def __init__(self, owner, sub=[], **kwargs):
		DisclosurePanel.__init__(self, kwargs['title'])
		AutoLayout.__init__(self, owner, sub, **kwargs)
		self.setWidth('100%')
		self.setOpen(True)

	def getReservedArgs(self):
		return ['height']


class SP(SimplePanel, AutoLayout):
	def __init__(self, owner, sub=[], **kwargs):
		SimplePanel.__init__(self)
		AutoLayout.__init__(self, owner, sub, **kwargs)
		self.setWidth('100%')

	def getReservedArgs(self):
		return ['height']


class GP(StyledFixedColumnFlexTable, AutoLayout):
	def __init__(self, owner, sub=[], **kwargs):
		StyledFixedColumnFlexTable.__init__(self, column_count=kwargs['column_count'])
		AutoLayout.__init__(self, owner, sub, **kwargs)
		self.setWidth('100%')

	def onCreate(self, el, kwargs):
		expand = True
		width = None
		center = False
		if 'expand' in kwargs:
			expand = kwargs['expand']
		if 'width' in kwargs:
			expand = False
			width = kwargs['width']
		if 'center' in kwargs:
			center = kwargs['center']
		self.addStyledWidget(el, expand=expand, width=width, center=center)

	def getReservedArgs(self):
		return ['expand', 'width', 'center']


def get_checked_radio(base, name, values):
	for v in values:
		if base.by_name("%s_%s" % (name, str(v))).isChecked():
			return v
	return None


class GPh(HTML):
	def __init__(self, owner, column_count, row_id_prefix=None, table_class=None):
		HTML.__init__(self)
		self.setWidth('100%')
		self.ncol = column_count
		self.rows = []
		self.current_row = []
		self.row_id_prefix = row_id_prefix
		self.table_class = table_class

	def add(self, html='', td_class='', td_id=''):
		self.current_row.append((html, td_class, td_id))
		if len(self.current_row) == self.ncol:
			self.rows.append(self.current_row)
			self.current_row = []

	def render(self):
		if self.table_class is None:
			html = '<table>'
		else:
			html = '<table class="%s">' % self.table_class
		rcount = 0
		for r in self.rows:
			row_id = ''
			if self.row_id_prefix is not None:
				row_id = ' id="%s%d"' % (self.row_id_prefix, rcount)
			rcount += 1
			html += '<tr%s>' % row_id
			for col in r:
				h, c, i = col
				hh = '&nbsp;' if h == '' else h
				cc = '' if c == '' else (' class="%s"' % c)
				ii = '' if i == '' else (' id="%s"' % i)
				html += '<td%s%s>%s</td>' % (cc, ii, hh)
			html += '</tr>'
		html += '</table>'
		self.setHTML(html)


class ValidationErrorRemover(KeyboardHandler):
	def __init__(self, widget):
		self.widget = widget

	def onKeyDown(self, sender, keycode, modifiers):
		self.widget.removeStyleName('validation-error')

	def remove(self):
		self.widget.removeStyleName('validation-error')


class LoadingButton(Button):
	def __init__(self, *args, **kwargs):
		Button.__init__(self, *args, **kwargs)
		self.backup_html = None

	def start(self):
		if self.backup_html is None:
			self.setEnabled(False)
			self.backup_html = self.getHTML()
			# self.setHTML('<img src="loading.gif" />')
			wait_start()

	def stop(self):
		if self.backup_html is not None:
			# self.setHTML(self.backup_html)
			self.backup_html = None
			self.setEnabled(True)
			wait_stop()


class MenuCmd:
	def __init__(self, handler):
		self.handler = handler

	def execute(self):
		self.handler()


# ToggleImage
class ToggleImage(Image):
	def __init__(self, filename, style_inactive, style_active, callback=None, data=None, can_turn_off=True):
		Image.__init__(self, filename)
		self.style_inactive = style_inactive
		self.style_active = style_active
		self.callback = callback
		self.active = False
		self.setActive(False)
		self.addClickListener(self.onClick)
		self.data = data
		self.can_turn_off = can_turn_off

	def setTooltip(self, s):
		self.getElement().setAttribute('title', s)

	def setActive(self, active=None):
		if active is None:
			active = not self.active
		self.active = active
		if not active:
			self.removeStyleName(self.style_active)
			self.addStyleName(self.style_inactive)
		else:
			self.removeStyleName(self.style_inactive)
			self.addStyleName(self.style_active)

	def isActive(self):
		return self.active

	def onClick(self):
		if self.can_turn_off:
			self.setActive()
		elif not self.active:
			self.setActive(True)
		if self.callback is not None:
			self.callback(self)


# SearchBox

class SearchPopup(PopupPanel, KeyboardHandler):
	def __init__(self, callback, textbox=None):
		PopupPanel.__init__(self, False, modal=False)
		self.sp = ScrollPanel()
		self.sp.setSize('100%', '400px')
		self.add(self.sp)
		self.callback = callback
		self.list = HTML()
		self.sp.addStyleName('big-list')
		self.names = {}
		self.sp.add(self.list)
		self.textbox = textbox
		self.addStyleName('search-popup')

	def onListElFactory(self, pk, text):
		def f():
			self.callback(pk, text)

		return f

	def update(self, els):
		self.els = els
		html = '<table>'
		i = 0
		self.names = {}
		for el in els:
			pk, name = el
			self.names[pk] = name
			html += '<tr id="search-popup-%d"><td>%s</td></tr>' % (i, name)
			i += 1
		html += '</table>'
		i = 0
		self.list.setHTML(html)
		for el in els:
			pk, name = el
			DOM.getElementById('search-popup-%d' % i).onclick = self.onListElFactory(pk, name)
			i += 1

	def setFocus(self, focus=True):
		self.list.setFocus(focus)

	def onKeyDown(self, sender, keycode, modifiers):
		return
		if keycode == 38 and self.textbox is not None and self.list.getSelectedIndex() == 0:
			self.list.setValueSelection([])
			self.textbox.setFocus(True)

	def onKeyUp(self, sender, keycode, modifiers):
		return
		if keycode == 13:
			pk = self.list.getValue(self.list.getSelectedIndex())
			self.callback(pk, self.names[pk])
		if keycode == 27:
			self.hide()

	def getSingleElement(self):
		"""
		Return (pk, name) if a single element is present; None otherwise
		"""
		if len(self.names) == 1:
			return self.names.items()[0]
		return None


class SearchBox(TextBox, KeyboardHandler, FocusListener):
	def __init__(self, method, callback=None, min_len=3, delay=100, mandatory=True):
		"""
		method: json-rpc method. It expects a search string, a returns a list of pairs (pk, name)
		"""
		TextBox.__init__(self)
		self.method = method
		self.addKeyboardListener(self)
		self.addFocusListener(self)
		self.pk = -1
		self.popup = None
		self.callback = callback
		self.delay = delay
		self.min_len = min_len
		self.timer = Timer(notify=self.onTimer)
		self.timer_enabled = False
		self.mandatory = mandatory
		el = self.getElement()
		self.schedule_popup_close = False
		JS("""
			el.oninput = function(e) {
				self.onInput();
			};
		""")

	def closePopup(self):
		self.stop_timer()
		if self.popup is not None:
			self.popup.hide()

	def onTimer(self):
		if self.schedule_popup_close:
			self.schedule_popup_close = False
			self.timer_enabled = False
			self.popup.hide()
		elif self.timer_enabled:
			search = self.getText()
			if len(search) >= self.min_len:
				self.method(search, JsonHandler(self.onMethodDone))

	def start_timer(self, delay=None):
		self.timer_enabled = True
		delay = self.delay if delay is None else delay
		self.timer.schedule(delay)

	def stop_timer(self):
		self.timer_enabled = False
		self.timer.cancel()

	def onMethodDone(self, res):
		if self.timer_enabled and res['cerca'] == self.getText() and len(res['risultati']) > 0:
			res = res['risultati']
			if self.popup is None:
				self.popup = SearchPopup(self.onSearchPopupSelected, self)
			self.popup.setPopupPosition(self.getAbsoluteLeft(), self.getAbsoluteTop() + self.getClientHeight())
			self.popup.show()
			self.popup.update(res)
		elif self.popup is not None:
			self.popup.hide()

	def manualPopup(self, elems):
		"""
		Manually open a popup panel.

		elems is a list of pairs (pk, value)
		"""
		self.stop_timer()
		self.setFocus()
		if self.popup is None:
			self.popup = SearchPopup(self.onSearchPopupSelected, self)
		self.popup.setPopupPosition(self.getAbsoluteLeft(), self.getAbsoluteTop() + self.getClientHeight())
		self.popup.show()
		self.popup.update(elems)

	def onFocus(self):
		self.selectAll()

	def onLostFocus(self):
		self.stop_timer()
		if self.mandatory and self.popup is not None:
			el = self.popup.getSingleElement()
			if el is not None:
				pk, name = el
				self.onSearchPopupSelected(pk, name)
		if self.popup is not None:
			# Process pending evens, i.e., an eventual click on a menu item, before closing popup
			self.schedule_popup_close = True
			self.start_timer(delay=150)

	def onInput(self):
		self.pk = -1
		self.start_timer()

	def onKeyDown(self, sender, keycode, modifiers):
		if keycode in [9, 13, 27]:  # TAB, Enter, ESC
			self.stop_timer()
			self.closePopup()

	def onKeyUp(self, sender, keycode, modifiers):
		self.removeStyleName('validation-error')
		if keycode == 40 and self.popup is not None:  # Down
			self.popup.setFocus()
			self.stop_timer()
		elif self.mandatory and keycode == 13 and self.popup is not None:
			self.stop_timer()
			el = self.popup.getSingleElement()
			if el is not None:
				pk, name = el
				self.onSearchPopupSelected(pk, name)

	def setValidationError(self):
		self.addStyleName('validation-error')

	def setText(self, text):
		TextBox.setText(self, text)
		self.pk = -1

	def getStatus(self):
		return (self.pk, TextBox.getText(self))

	def setStatus(self, pk, text):
		self.pk = pk
		TextBox.setText(self, text)

	def onSearchPopupSelected(self, pk, name):
		self.closePopup()
		TextBox.setText(self, name)
		self.setFocus(True)
		self.setCursorPos(len(name))
		self.pk = pk
		if self.callback is not None:
			self.callback()


class FavSearchBox(SearchBox):
	"""
	SearchBox con sostituzione dei preferiti, per Roma mobile
	"""

	def getText(self):
		if self.pk != -1 and not str(self.pk).startswith('A'):
			s = 'fav:' + self.pk
		else:
			s = SearchBox.getText(self)
		return s


# Input mapper

class InputMapper(KeyboardHandler):
	def __init__(self, pk, desc, load_method, save_method, save_button, save_callback=None, load_callback=None,
							 close_button=None, close_callback=None):
		"""
		pk: pk of object, or -1 if not created yet
		desc: list of dictionaries: {
			'name': field name,
			'type': 'free' | 'single' | 'multi' | 'address' | 'foreign' | 'custom',
			'input': input widget, or callback for custom type
		}
		load_method, save_methos: jsonrpc methods
		"""
		self.pk = pk
		self.desc = desc
		self.load_method = load_method
		self.save_method = save_method
		self.desc = {}
		for el in desc:
			self.desc[el['name']] = el
			if el['type'] in ['free', 'single', 'multi']:
				el['input'].addChangeListener(self.onChange)
				if el['type'] == 'free':
					el['input'].addKeyboardListener(self)
		self.load()
		self.save_button = save_button
		if save_button is not None:
			save_button.addClickListener(self.onSaveButton)
		self.save_callback = save_callback
		self.load_callback = load_callback
		self.modified = False
		self.close_button = close_button
		self.close_callback = close_callback
		if self.close_button is not None:
			self.close_button.addClickListener(self.onCloseButton)

	def setModified(self, modified=True):
		if modified and not self.modified:
			self.modified = True
			if self.close_button is not None:
				self.close_button.setText('Annulla')
		elif not modified and self.modified:
			self.modified = False
			if self.close_button is not None:
				self.close_button.setText('Chiudi')

	def onChange(self, sender):
		sender.removeStyleName('validation-error')
		self.setModified()

	def onKeyUp(self, sender, keycode, modifiers):
		sender.removeStyleName('validation-error')
		self.setModified()

	def onSaveDone(self, res):
		if res['status'] == 'OK':
			self.pk = res['pk']
		else:
			DissolvingPopup(res['msg'], error=True)
			for f in res['fields']:
				d = self.desc[f]
				if d['type'] in ['free', 'multi', 'single']:
					d['input'].addStyleName('validation-error')
				elif d['type'] in ['address', 'foreign']:
					d['input'].setValidationError()
		if self.save_button is not None:
			self.save_button.setEnabled(True)
		self.setModified(False)
		if self.save_callback is not None:
			self.save_callback(res)

	def save(self, callback):
		out = {}
		for name in self.desc:
			d = self.desc[name]
			t = d['type']
			input = d['input']
			if t == 'free':
				out[name] = input.getText()
			elif t == 'single':
				out[name] = input.getValue(input.getSelectedIndex())
			elif t == 'multi':
				# TODO
				out[name] = ''
			elif t == 'foreign':
				out[name] = input.pk if input.pk > -1 else None
			elif t == 'custom':
				out[name] = input()
			elif t == 'address':
				out[name] = input.getAddress()
		self.callback = callback
		self.save_method(self.pk, out, JsonHandler(self.onSaveDone))

	def onSaveButton(self):
		self.save_button.setEnabled(False)
		self.save()

	def onCloseButton(self):
		self.confirmClose(self.close_callback)

	def confirmClose(self, callback_yes, callback_no=None):
		if not self.modified:
			if callback_yes is not None:
				callback_yes()
		else:
			QuestionDialogBox("Conferma", "Ci sono modifiche non salvate. Confermi la chiusura?",
												[("S&igrave;", callback_yes, None), ("No", callback_no, None)]).show()

	def onLoadDone(self, res):
		for name in res:
			el = res[name]
			d = self.desc[name]
			input = d['input']
			type = d['type']
			if type == 'free':
				input.setText(el)
			elif type == 'single':
				input.clear()
				pk = el[0]
				i = 0
				for item in el[1]:
					ipk, iname = item
					input.addItem(iname, ipk)
					if ipk == pk:
						input.setSelectedIndex(i)
					i += 1
			elif type == 'multi':
				# TODO
				pass
			elif type == 'foreign':
				pk, text = el
				input.setText(text)
				input.pk = pk
			elif type == 'custom':
				pass
			elif type == 'address':
				text, lng, lat = el
				input.setAddress(text, lng, lat)
		if self.load_callback is not None:
			self.load_callback(res)

	def load(self):
		self.load_method(self.pk, JsonHandler(self.onLoadDone))


class DeferrableTabPanel(TabPanel):
	def __init__(self, owner):
		super(DeferrableTabPanel, self).__init__()
		History.addHistoryListener(self)
		self.owner = owner
		self.selected = None

	def onHistoryChanged(self, token):
		if token.startswith('htm-'):
			index = int(token[4:])
			super(DeferrableTabPanel, self).selectTab(index)

	def onTabSelected(self, sender, tabIndex):
		res = super(DeferrableTabPanel, self).onTabSelected(sender, tabIndex)
		self.selected = self.getWidget(tabIndex)
		History.newItem("htm-%d" % tabIndex)
		self.selected.perform_deferred()
		self.selected.onTabSelected()
		return res

	def add(self, widget, *args, **kwargs):
		widget.dtp = self
		return TabPanel.add(self, widget, *args, **kwargs)

	def star_tab(self, index):
		tab_bar = self.getTabBar()
		# h = tab_bar.getTabHTML(index)
		w = tab_bar.getTabWidget(index)
		w.addStyleName('tab-evidenziata')

		def remove_star():
			w.removeStyleName('tab-evidenziata')

		self.getWidget(index).do_or_defer(remove_star)


class DeferrablePanel(object):
	def __init__(self, deferrable_tab_panel, deferred_interval=None):
		object.__init__(self)
		self.op = []
		self.dtp = deferrable_tab_panel
		self.deferred_timer = Timer(notify=self.onTimer)
		self.deferred_interval = deferred_interval

	def onTimer(self):
		self.perform_deferred_actions()

	def perform_deferred_actions(self):
		self.deferred_timer.cancel()
		op = self.op
		self.op = []
		for el in op:
			o, args, kwargs = el
			o(*args, **kwargs)

	def do_or_defer(self, o, *args, **kwargs):
		self.op.append([o, args, kwargs])
		if self == self.dtp.selected:
			self.perform_deferred_actions()

	def perform_deferred(self):
		if self.deferred_interval is not None:
			self.deferred_timer.schedule(self.deferred_interval)
		else:
			self.perform_deferred_actions()

	def onTabSelected(self):
		pass


if old_android():
	class ScrollAdaptivePanel(VerticalPanel):
		def __init__(self):
			VerticalPanel.__init__(self)

		def relayout(self):
			pass

else:
	class ScrollAdaptivePanel(ScrollPanel):
		def __init__(self):
			ScrollPanel.__init__(self)

		def relayout(self):
			w = self.getWidget()
			self.remove(w)
			self.setHeight('100%')
			height = self.getClientHeight()
			self.setHeight(height)
			self.setWidget(w)

waiting = [None]


def wait_init(owner):
	waiting[0] = Waiting(owner)
	return waiting[0]


def wait_start():
	waiting[0].start()


def wait_stop():
	waiting[0].stop()


class Waiting(VerticalPanel):
	def __init__(self, owner):
		super(Waiting, self).__init__(Width='48px', Height='48px')
		self.wait = Image('wait.gif', Width='31px', Height='31px')
		self.wait.addStyleName('waiting-image')
		self.menu = Image('toolbar/menu.png', Width='48px', Height='48px')
		self.focus = Button('')
		self.focus.addStyleName('focus-sink')
		self.add(self.wait)
		self.add(self.menu)
		self.add(self.focus)
		self.wait.setVisible(False)
		self.owner = owner
		self.owner.add(self)
		self.addStyleName('waiting')
		self.setVerticalAlignment(HasAlignment.ALIGN_MIDDLE)
		self.setHorizontalAlignment(HasAlignment.ALIGN_CENTER)

	def start(self):
		self.focus.setFocus(True)
		# self.remove(self.focus)
		# self.remove(self.menu)
		# self.add(self.wait)
		self.menu.setVisible(False)
		self.wait.setVisible(True)

	def stop(self):
		# self.remove(self.wait)
		# self.add(self.focus)
		# self.add(self.menu)
		self.wait.setVisible(False)
		self.menu.setVisible(True)

	def setGeneralMenuPanel(self, menu_panel):
		self.menu.addClickListener(menu_panel.display_menu)


def getdefault(d, key, default):
	if key in d:
		return d[key]
	return default


# [default_lang, current_lang]
langs = ['', '']


def set_lang(default_lang, current_lang):
	langs[0] = default_lang
	langs[1] = current_lang


def get_lang():
	return langs[1]


def _(x):
	if langs[0] == langs[1]:
		return x
	try:
		return messages[langs[1]][x]
	except:
		return x


class MenuPanelItem(HorizontalPanel):
	def __init__(self, owner, id, text, listener=None, icon=None, width=None, height=None, action_icon=None,
							 action_listener=None):
		HorizontalPanel.__init__(self)
		self.setWidth('100%')
		self.setVerticalAlignment(HasAlignment.ALIGN_MIDDLE)
		self.owner = owner
		self.id = id
		self.text = text
		self.addStyleName('menu-item')
		self.fp = FocusPanel()
		self.fp.setSize('100%', '100%')
		self.add(self.fp)
		self.setCellWidth(self.fp, '100%')
		self.hp = HorizontalPanel()
		self.fp.add(self.hp)
		self.hp.setHeight('100%')
		self.hp.setVerticalAlignment(HasAlignment.ALIGN_MIDDLE)
		self.icon = HorizontalPanel()
		if icon is not None:
			self.icon_image = Image(icon)
			if width is None:
				width = '72px'
			self.icon_image.setWidth(width)
			if height is None:
				height = '48px'
			self.icon_image.setHeight(height)
			self.icon.add(self.icon_image)
			self.icon.setCellVerticalAlignment(self.icon_image, HasAlignment.ALIGN_MIDDLE)
			self.icon.setCellHorizontalAlignment(self.icon_image, HasAlignment.ALIGN_CENTER)

		self.icon.addStyleName('menu-item-icon')
		self.hp.add(self.icon)
		self.html = HTML(text)
		self.hp.add(self.html)
		self.action_listener = action_listener
		if action_icon is not None:
			self.action_icon = Image(action_icon)
			self.action_icon.addStyleName('menu-item-action-icon')
			self.add(self.action_icon)
			self.action_icon.addClickListener(self.onActionClick)
		self.listener = listener
		self.fp.addClickListener(self.onClick)

	def onClick(self):
		self.owner.onClick()
		if self.listener is not None:
			self.listener(self)

	def onActionClick(self):
		if self.action_listener is not None:
			self.action_listener(self)

	def setText(self, t):
		self.html.setHTML(t)

	def setListener(self, listener):
		self.listener = listener


class MenuPanel(FocusPanel):
	"""
	Menu panel

	Definition is a list of dictionaries, with the following items:
	 * id: id of the item
	 * icon: url of the item icon, or None (optional)
	 * text: text of menu item
	 * listener: item listener
	 * action_icon: url of the action icon for the item, or None (optional)
	 * action_listener: action listener for the item (optional)
	"""

	def __init__(self, general_menu_panel, definition, title='Menu', icon=None, on_click=None):
		FocusPanel.__init__(self)
		self.vp = VerticalPanel(self)
		self.add(self.vp)
		self.gmp = general_menu_panel
		# self.setSize('100%', '100%')
		self.setWidth('100%')
		self.addStyleName('menu')
		self.vp.setWidth('100%')
		self.items = []
		self.itemdict = {}
		self.on_click = on_click
		if title is not None:
			self.header = MenuPanelItem(
				self,
				id='header',
				text=title,
				listener=None,
				icon=icon,
			)
			self.header.addStyleName('menu-header')
			self.vp.add(self.header)
		for d in definition:
			mip = MenuPanelItem(
				self,
				id=d['id'],
				text=d['text'],
				listener=d['listener'],
				icon=getdefault(d, 'icon', None),
				width=getdefault(d, 'width', None),
				height=getdefault(d, 'height', None),
				action_icon=getdefault(d, 'action_icon', None),
				action_listener=getdefault(d, 'action_listener', None),
			)
			self.items.append(mip)
			self.itemdict[d['id']] = mip
			self.vp.add(mip)
		# self.addClickListener(self.onClick)

	def addItem(self, id, text, listener, icon=None, width=None, height=None):
		mip = MenuPanelItem(
			self,
			id=id,
			text=text,
			listener=listener,
			icon=icon,
			width=width,
			height=height,
		)
		self.items.append(mip)
		self.itemdict[id] = mip
		self.vp.add(mip)

	def clear(self):
		self.vp.clear()
		self.items = []
		self.itemdict = {}

	def by_id(self, id):
		return self.itemdict[id]

	def hide(self):
		if self.gmp is not None:
			self.gmp.display_menu(False)

	def onClick(self):
		self.hide()
		if self.on_click is not None:
			self.on_click()


class MenuPopupPanel(PopupPanel):
	def __init__(self, definition, x, y, anchor='tl'):
		"""
		Create and display a popup with a MenuPanel

		definition: menu panel definition, as in MenuPanel init
		x, y: anchor point
		anchor: anchor corner, in ['tl', 'tr', 'bl', 'br']
		"""
		PopupPanel.__init__(self, True, modal=False)
		self.menu = MenuPanel(None, definition, None, on_click=self.hide)
		self.addStyleName('menu-popup-panel')
		self.add(self.menu)
		self.show()
		if 'r' in anchor:
			x = x - int(self.getClientWidth())
		if 'b' in anchor:
			y = y - int(self.getClientHeight())
		self.setPopupPosition(x, y)


class GeneralMenuPanel(SimplePanel):
	def __init__(self):
		SimplePanel.__init__(self)
		self.setSize('100%', '100%')
		self.active_menu = None

	def setMainPanel(self, main_panel):
		self.main_panel = main_panel
		self.add(main_panel)

	def setMenuPanel(self, menu_panel):
		self.menu_panel = menu_panel

	def display_menu(self, display=True, alternative_menu=None):
		if display:
			self.active_menu = alternative_menu if alternative_menu is not None else self.menu_panel
			self.remove(self.main_panel)
			self.add(self.active_menu)
		else:
			self.remove(self.active_menu)
			self.add(self.main_panel)
			self.active_menu = None


def setAttribute(widget, name, value):
	widget.getElement().setAttribute(name, value)


class PreferitiImage(Image):
	def __init__(self, tipo, nome, descrizione, esiste, client):
		self.esiste = esiste
		self.prepareUrl()
		Image.__init__(self, self.url, Width='18px', Height='18px')
		self.tipo = tipo
		self.nome = nome
		self.descrizione = descrizione
		self.client = client
		self.addClickListener(self.onClick)

	def onClick(self):
		u = get_user()
		if u is None:
			ask_login()
		else:
			self.esiste = not self.esiste
			self.prepareUrl()
			self.setUrl(self.url)
			self.client(self.tipo, self.nome, self.descrizione, self.esiste, JsonHandler(self.onClientDone))

	def prepareUrl(self):
		if self.esiste:
			self.url = 'palina_preferita_on.png'
		else:
			self.url = 'palina_preferita_off.png'

	def onClientDone(self, res):
		get_control().setPreferiti(res['fav'])


# def ask_login():
# 	QuestionDialogBox(
# 		_('Accesso richiesto'),
# 		_("Per continuare devi effettuare l'accesso."),
# 		[
# 			(_('Accedi'), get_control().onLogin, None),
# 			(_('Annulla'), None, None),
# 		]
# 	).show()

def ask_login():
	QuestionDialogBox(
		_('Preferiti non disponibili'),
		_("Temporaneamente i preferiti non sono disponibili, ma torneranno presto!"),
		[
			# (_('Accedi'), get_control().onLogin, None),
			(_('Chiudi'), None, None),
		]
	).show()


storage_web = {}


def storage_get(key, default_value=None):
	if flavor == 'web':
		if key in storage_web:
			return storage_web[key]
		return default_value
	else:
		JS("""
			if(localStorage && localStorage[key]) {
				ret = localStorage[key];
			} else {
				ret = default_value;
			}
		""")
		return ret


def storage_set(key, value):
	if flavor == 'web':
		storage_web[key] = value
		client.servizi_storage_set(key, value, JsonHandler())

	else:
		JS("""localStorage[key] = value;""")


def enforce_login(f):
	def g(*args, **kwargs):
		u = get_user()
		if u is None:
			ask_login()
		else:
			return f(*args, **kwargs)

	return g


class PausableTimer(Timer):
	timers = []

	def __init__(self, delayMillis=0, notify=None):
		self.delayMillis = delayMillis
		self.notify = notify
		Timer.__init__(self, delayMillis, self.call)
		PausableTimer.timers.append(self)
		if delayMillis == 0:
			self.modo = 0
		else:
			self.modo = 1
		self.paused = None

	def call(self):
		# prnt("Timer calling")
		# prnt(self.paused)
		# prnt(self.modo)
		if self.paused is None and self.modo > 0:
			if self.notify is not None:
				self.notify()
			else:
				self.run()

	def schedule(self, delayMillis):
		# prnt("Timer scheduling")
		# prnt(self.paused)
		# prnt(self.modo)

		Timer.schedule(self, delayMillis, self.call)
		self.modo = 1
		self.delayMillis = delayMillis

	def cancel(self):
		# prnt("Timer cancel")
		# prnt(self.paused)
		# prnt(self.modo)

		self.modo = 0
		Timer.cancel(self)

	def scheduleRepeating(self, periodMillis):
		# prnt("Timer scheduling repeating")
		# prnt(self.paused)
		# prnt(self.modo)

		self.modo = 2
		self.delayMillis = periodMillis
		Timer.scheduleRepeating(self, periodMillis, self.call)

	def pause(self):
		# prnt("Timer pausinig")
		# prnt(self.paused)
		# prnt(self.modo)
		if self.paused is None and self.modo > 0:
			self.paused = datetime.now()
			Timer.cancel(self)

	def resume(self):
		# prnt("Timer resuming")
		# prnt(self.paused)
		# prnt(self.modo)
		if self.paused is not None and self.modo > 0:
			# elapsed = (datetime.now() - self.paused).total_seconds() * 1000
			self.paused = None
			if True:  # elapsed > self.delayMillis:
				self.call()
			if self.modo == 1:
				Timer.schedule(self, self.delayMillis, self.call)
				self.modo = 1
			elif self.modo == 2:
				Timer.scheduleRepeating(self, self.delayMillis, self.call)
				self.modo = 2

	def __del__(self):
		PausableTimer.timers.remove(self)


def pause_all_timers():
	# prnt("Pausing all timers")
	# prnt(PausableTimer.timers)
	for t in PausableTimer.timers:
		t.pause()


def resume_all_timers():
	# prnt("Resuming all timers")
	# prnt(PausableTimer.timers)
	for t in PausableTimer.timers:
		t.resume()


class PaginatedPanelPage(object):
	"""
	Mixin for widgets to be added to a PaginatedPanel
	"""

	def notifyShow(self):
		pass

	def initPaginatedPanelPage(self, pp, index):
		self.paginated_panel = pp
		self.paginated_panel_index = index

	def isShown(self):
		return self.paginated_panel.isShown(self)

	def insertMenuItem(self, position, description):
		"""
		Add a menu item at position position

		Description is in the format of MenuPanel description
		"""
		self.paginated_panel.menus[self.paginated_panel_index].insert(position, description)
		self.paginated_panel.update()


class PaginatedPanel(VerticalPanel):
	def __init__(self, height=None, close_callback=None):
		VerticalPanel.__init__(self)
		self.setWidth('100%')
		if height is not None:
			self.setHeight(height)

		self.title_hp = HorizontalPanel()
		self.title_hp.setWidth('100%')
		self.title_hp.addStyleName('paginated-title')
		self.title = HTML()
		self.title_hp.add(self.title)
		self.title_hp.setCellVerticalAlignment(self.title, HasAlignment.ALIGN_MIDDLE)
		self.title_hp.setCellWidth(self.title, '100%')
		self.detail = Image('paginated-details.png', Width='18px', Height='18px')
		self.detail.setStyleAttribute('margin-right', '6px')
		self.detail.addClickListener(self.onDetails)
		self.detail.setVisible(False)
		self.title_hp.add(self.detail)
		self.title_hp.setCellVerticalAlignment(self.detail, HasAlignment.ALIGN_MIDDLE)
		self.menu = Image('paginated-menu.png', Width='18px', Height='18px')
		self.menu.addClickListener(self.onMenu)
		self.title_hp.add(self.menu)
		self.title_hp.setCellVerticalAlignment(self.menu, HasAlignment.ALIGN_MIDDLE)
		self.close = Image('paginated-close.png', Width='18px', Height='18px')
		self.close.addClickListener(self.onClose)
		self.title_hp.add(self.close)
		self.title_hp.setCellVerticalAlignment(self.close, HasAlignment.ALIGN_MIDDLE)

		VerticalPanel.add(self, self.title_hp)
		self.setCellWidth(self.title_hp, '100%')

		self.hp = HorizontalPanel()
		self.hp.addStyleName('paginated-panel')
		self.hp.setWidth('100%')

		self.left = Button('<img src="paginated_left.png" width="35px" height="45px"/>', self.onLeft)
		self.left.addStyleName('paginated-arrow')
		self.left.addStyleName('paginated-inactive')
		self.left.setHeight('100%')
		self.hp.add(self.left)
		self.hp.setCellVerticalAlignment(self.left, HasAlignment.ALIGN_MIDDLE)

		self.sp = SimplePanel()
		self.hp.add(self.sp)
		self.hp.setCellWidth(self.sp, '100%')
		self.hp.setCellHeight(self.sp, '100%')

		self.right = Button('<img src="paginated_right.png" width="35px" height="45px"/>', self.onRight)
		self.right.addStyleName('paginated-arrow')
		self.right.addStyleName('paginated-inactive')
		self.right.setHeight('100%')
		self.hp.add(self.right)
		self.hp.setCellVerticalAlignment(self.right, HasAlignment.ALIGN_MIDDLE)

		VerticalPanel.add(self, self.hp)
		self.setCellWidth(self.hp, '100%')

		self.widgets = []
		self.index = 0
		self.callbacks = []
		self.titles = []
		self.details = []
		self.menus = []
		self.close_callback = close_callback

	def add(self, widget, callback=None, title='', details=None, menu_description=None):
		"""
		Add a page to the panel

		widget: page widget
		callback:
		title: page title
		details: callback, called when user clicks on title or on details icon
		menu_description: description of a context menu, in the format of MenuPanel description (see MenuPanel init doc)
		"""
		index = len(self.widgets)
		self.widgets.append(widget)
		self.callbacks.append(callback)
		self.titles.append(title)
		self.details.append(details)
		if menu_description is not None:
			menu_description.append({
				'id': 'close',
				'text': _('Chiudi'),
				'listener': self.onClose,
			})
		self.menus.append(menu_description)
		if index == 0:
			self.update(False)
		if index == 1:
			self.right.removeStyleName('paginated-inactive')
		widget.initPaginatedPanelPage(self, index)
		return index

	def onLeft(self):
		if self.index > 0:
			self.index -= 1
			self.update()

	def onRight(self):
		if self.index < len(self.widgets) - 1:
			self.index += 1
			self.update()

	def update(self, call_callback=True):
		i = self.index
		widget = self.widgets[i]
		widget.notifyShow()
		self.sp.setWidget(widget)
		self.title.setHTML(self.titles[i])
		self.detail.setVisible(self.details[i] is not None)
		self.close.setVisible(self.menus[i] is None)
		self.menu.setVisible(self.menus[i] is not None)
		if i == 0:
			self.left.addStyleName('paginated-inactive')
		else:
			self.left.removeStyleName('paginated-inactive')
		if i == len(self.widgets) - 1:
			self.right.addStyleName('paginated-inactive')
		else:
			self.right.removeStyleName('paginated-inactive')
		c = self.callbacks[i]
		if call_callback and c is not None:
			c()

	def selectIndex(self, i):
		if i >= 0 and i < len(self.widgets):
			self.index = i
			self.update()

	def onDetails(self):
		details = self.details[self.index]
		if details is not None:
			details()

	def onMenu(self):
		l = int(self.menu.getAbsoluteLeft())
		t = int(self.menu.getAbsoluteTop())
		MenuPopupPanel(self.menus[self.index], l, t, 'br')

	def onClose(self):
		self.setVisible(False)
		if self.close_callback is not None:
			self.close_callback()

	def isShown(self, widget):
		return widget.paginated_panel_index == self.index

	@classmethod
	def generaPuntiPassi(cls, passo, totali):
		"""
		Genera tanti pallini quanti sono i passi, e colora il passo corrente

		totali: numero totale di passi
		passo: passo corrente, partendo da 0; oppure -1 (nessun passo corrente)
		"""
		out = ['<img src="paginated-dot-%s.png" width="14px" height="14px" style="vertical-align:middle;"/>' % (
		'full' if i == passo else 'blank') for i in range(totali)]
		return "&nbsp;".join(out)


class ImageTextButton(Button):
	def __init__(self, img, img_width, img_height, text, listener):
		html = """
			<table class="text-image-button-table">
				<tr>
					<td><img src="%(img)s" height="%(height)s"/></td>
					<td class="text-image-button-text">%(text)s</td>
				</tr>
			</table>
		""" % {'img': img, 'width': img_width, 'height': img_height, 'text': text}
		Button.__init__(self, html, listener)
		self.addStyleName('text-image-button')


class LuogoPanel(VerticalPanel, PaginatedPanelPage):
	active_marker = None

	def __init__(self, owner, on_percorso_da, on_percorso_a, on_cerca_linea, on_cerca_luogo):
		VerticalPanel.__init__(self)
		self.owner = owner
		self.setSize('100%', '100%')
		self.base = VP(
			self,
			sub=[
				{
					'class': GP,
					'column_count': 2,
					'name': 'bottoni',
					'sub': [
						{
							'class': ImageTextButton,
							'call_setHeight': (['48px'], {}),
							'width': '50%',
							'args': [
								'azioni_luogo/percorso_da.png',
								'36px',
								'36px',
								_('Percorso<br />da qui'),
								on_percorso_da,
							],
						},
						{
							'class': ImageTextButton,
							'call_setHeight': (['48px'], {}),
							'width': '50%',
							'args': [
								'azioni_luogo/linea.png',
								'36px',
								'36px',
								_('Fermate<br />vicine'),
								on_cerca_linea,
							],
						},
						{
							'class': ImageTextButton,
							'call_setHeight': (['48px'], {}),
							'width': '50%',
							'args': [
								'azioni_luogo/percorso_a.png',
								'36px',
								'36px',
								_('Percorso<br />fino a qui'),
								on_percorso_a,
							],
						},
						{
							'class': ImageTextButton,
							'call_setHeight': (['48px'], {}),
							'width': '50%',
							'args': [
								'azioni_luogo/luogo.png',
								'36px',
								'36px',
								_('Luoghi<br />vicini'),
								on_cerca_luogo,
							],
						},
					],
				},
			],
			add_to_owner=True,
		)


class CheckList(VerticalPanel):
	def __init__(self, items):
		"""
		items: list of triples (id, text, checked)
		"""
		VerticalPanel.__init__(self)
		self.items = items
		self.cbs = []
		self.index = {}
		i = 0
		for iid, text, checked in self.items:
			cb = CheckBox(text)
			cb.setChecked(checked)
			self.add(cb)
			self.index[iid] = i
			self.cbs.append(cb)
			i += 1

	def getCheckboxById(self, iid):
		return self.cbs[self.index[iid]]

	def getSelectedItems(self):
		"""
		Return list of id's of selected items
		"""
		ret = []

		n = len(self.items)
		for i in range(n):
			if self.cbs[i].isChecked():
				ret.append(self.items[i][0])

		return ret


class LocalNotificationOld(object):
	counter = 0

	def __init__(self, onNotification=None):
		"""
		Each Notification instance handles 1 local notification
		"""
		object.__init__(self)
		self.counter += 1
		self.id = self.counter
		self.onNotificationDone = onNotification

	def schedule(self, delay, message, title=_("Notifica")):
		"""
		Schedule (or reschedule) notification.

		delay in millisec
		"""
		JS("""
			var now = new Date().getTime();
			var t = new Date(now + delay);
			$wnd.plugin.notification.local.add({
				id:	self.id,
				date: t,
				message: message,
				title: title,
			});
		""")
		if self.onNotificationDone is not None:
			JS("""
				$wnd.plugin.notification.local.ontrigger = function(id, state, json) {self.onNotificationDone()};
			""")

	def cancel(self):
		"""
		Cancel modification
		"""
		JS("""
			$wnd.plugin.notification.local.cancel(self.id);
		""")


class LocalNotification(object):
	counter = 0

	def __init__(self, onNotification=None):
		"""
		Each Notification instance handles 1 local notification
		"""
		object.__init__(self)
		self.onNotificationDone = onNotification
		self.timer = Timer(notify=self.onTimer)

	def onTimer(self):
		if self.onNotificationDone is not None:
			self.onNotificationDone()
		title = self.title
		message = self.message
		JS("""
			var notification = new $wnd.Notification(title, { 
				 body: message
			}); 
		""")

	def schedule(self, delay, message, title=_("Notifica")):
		"""
		Schedule (or reschedule) notification.

		delay in millisec
		"""
		self.message = message
		self.title = title
		self.timer.cancel()
		if delay > 0:
			self.timer.schedule(delay)
		elif delay == 0:
			self.onTimer()

	def cancel(self):
		"""
		Cancel modification
		"""
		self.timer.cancel()



class WebNotification(object):
	counter = 0

	def __init__(self, onNotification=None):
		"""
		Each Notification instance handles 1 local notification
		"""
		object.__init__(self)
		self.onNotificationDone = onNotification
		self.timer = Timer(notify=self.onTimer)

	def onTimer(self):
		if self.onNotificationDone is not None:
			self.onNotificationDone()
		MessageDialog(self.message, self.title)

	def schedule(self, delay, message, title=_("Notifica")):
		"""
		Schedule (or reschedule) notification.

		delay in millisec
		"""
		self.message = message
		self.title = title
		self.timer.cancel()
		if delay > 0:
			self.timer.schedule(delay)
		elif delay == 0:
			self.onTimer()

	def cancel(self):
		"""
		Cancel modification
		"""
		self.timer.cancel()


class ButtonsPanel(HorizontalPanel):
	def __init__(self, buttons):
		"""
		Creates a panel with buttons and spacing between them.

		buttons is a list of pairs (html, listener)
		"""
		HorizontalPanel.__init__(self)
		self.setWidth('100%')
		self.buttons = []
		n = len(buttons)
		width = "%d%%" % (int(100 / n) - 1)

		for i in range(n):
			html, listener = buttons[i]
			b = Button(html, listener)
			b.setWidth('100%')
			self.add(b)
			self.setCellWidth(b, width)
			if i < n - 1:
				self.add(HTML('&nbsp;'))
			self.buttons.append(b)


def addClickListener(el_id, listener):
	el = DOM.getElementById(el_id)
	JS("""el.onclick = listener;""")