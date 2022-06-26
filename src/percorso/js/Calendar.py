# coding: utf-8

# Date Time Example
# Copyright (C) 2009 Yit Choong (http://code.google.com/u/yitchoong/)
# Copyright (C) 2009 Luke Kenneth Casson Leighton <lkcl@lkcl.net>
# Modified by Luca Allulli for Roma Servizi per la Mobilità srl

from pyjamas.ui.SimplePanel import SimplePanel
from pyjamas import Factory
from pyjamas.ui.VerticalPanel import  VerticalPanel
from pyjamas.ui.HorizontalPanel import HorizontalPanel
from pyjamas.ui.PopupPanel import  PopupPanel
from pyjamas.ui.Grid import Grid
from pyjamas.ui.Composite import Composite
from pyjamas.ui.Label import Label
from pyjamas.ui.HyperlinkImage import HyperlinkImage
from pyjamas.ui.HTML import HTML
from pyjamas.ui.FocusPanel import FocusPanel
from pyjamas.ui.TextBox import TextBox
from pyjamas.ui.Image import Image
from pyjamas.ui import HasAlignment
from pyjamas.ui.MenuBar import MenuBar
from pyjamas.ui.MenuItem import MenuItem
from pyjamas import DOM
from pyjamas import History

import time

class HyperLink(HTML):
	def __init__(self, *args, **kwargs):
		HTML.__init__(self, *args, **kwargs)
		self.addStyleName('clickable')

class Calendar(FocusPanel):
	monthsOfYear = ['Gen','Feb','Mar','Apr','Mag','Giu','Lug','Ago','Set','Ott','Nov','Dic']
	daysOfWeek = ['D','L','M','M','G','V','S']
	today = 'Oggi'
	tomorrow = 'Domani'
	yesterday = 'Ieri'
	cancel = 'Annulla'

	def __init__(self, **kwargs):
		FocusPanel.__init__(self, **kwargs)
		yr,mth,day = time.strftime("%Y-%m-%d").split("-")
		self.todayYear = int(yr)
		self.todayMonth = int(mth)  # change to offset 0 as per javascript
		self.todayDay = int(day)

		self.currentMonth = self.todayMonth
		self.currentYear = self.todayYear
		self.currentDay = self.todayDay

		self.selectedDateListeners = []

		self.defaultGrid = None # used later

		return

	def getMonthsOfYear(self):
		return self.monthsOfYear
	   
	def getDaysOfWeek(self):
		return self.daysOfWeek

	def addSelectedDateListener(self,listener):
		self.selectedDateListeners.append(listener)

	def removeSelectedDateListener(self,listener):
		self.selectedDateListeners.remove(listener)

	def isLeapYear(self,year):
		if (year % 4 == 0 and year % 100 != 0) or ( year % 400 == 0):
			return True
		else:
			return False

	def getDaysInMonth(self,mth,year):
		days = 0
		if (mth == 1 or mth == 3 or mth == 5 or mth == 7 or mth == 8 or mth == 10 or mth == 12): # in (1,3,5,7,8,10,12):
			days=31
		elif mth == 4 or mth == 6 or mth == 8 or mth == 11: #in (4,6,8,11):
			days = 30
		elif (mth==2 and self.isLeapYear(year)):
			days = 29
		else:
			days = 28
		return days

	def setPosition(self, left, top):
		element = self.getElement()
		DOM.setStyleAttribute(element, "left", "%dpx" % left)
		DOM.setStyleAttribute(element, "top", "%dpx" % top)

	def show(self, left, top):
		if left < 0:
			left = 0
		if top < 0:
			top = 0
		self.setPosition(left,top)
		self.drawCurrent()
		self.setVisible(True)

	def drawCurrent(self):
		yr,mth,day = time.strftime("%Y-%m-%d").split("-")
		self.draw( int(mth), int(yr) )

	def draw(self, month , year):
		tod = time.localtime()
		self.currentMonth = month
		self.currentYear = year
		mm = tod.tm_mon
		yy = tod.tm_year
		# has today changed and thus changed month? cater to rare case where widget in created on last day of month &
		# page left till next day
		hasChangeMonth = False
		if yy <> self.todayYear or mm <> self.todayMonth:
			hasChangeMonth = True
			self.todayYear = yy
			self.todayMonth = mm

		# check to see if we have drawn the full widget before
		if self.defaultGrid is None:
			self.drawFull(month,year)
		else:
			# ok means we are re-drawing, but first check if it is the same as the defaultGrid, if yes, just use it
			if not hasChangeMonth and month == self.todayMonth and year == self.todayYear:
				self.middlePanel.setWidget(self.defaultGrid)
				self.currentMonth = self.todayMonth
				self.currentYear = self.todayYear
			else:
				# we have to redraw the grid -- bah
				g = self.drawGrid(month,year)

				if hasChangeMonth:
					self.defaultGrid = grid # reset the default grid as we have changed months

			#
			# what about the title panel?
			#
			self.titlePanel.setWidget(HTML("<b>" + self.getMonthsOfYear()[month-1] + " " + str(year) + "</b>" ) )
			self.setVisible(True)

		return

	def drawFull(self, month, year):
		# should be called only once when we draw the calendar for the first time
		#
		self.vp = VerticalPanel()
		self.vp.setSpacing(2)
		self.vp.addStyleName("calendarbox calendar-module calendar")
		self.setWidget(self.vp)
		self.setVisible(False)
		#
		mth = int(month)
		yr = int(year)

		tp = HorizontalPanel()
		tp.addStyleName("calendar-top-panel")
		tp.setSpacing(5)

		h1 = HyperLink('<<') #, TargetHistoryToken=History.getToken())
		h1.addClickListener( getattr(self,'onPreviousYear') )
		h2 = HyperLink('<') #, TargetHistoryToken=History.getToken())
		h2.addClickListener( getattr(self,'onPreviousMonth') )
		h4 = HyperLink('>') #, TargetHistoryToken=History.getToken())
		h4.addClickListener( getattr(self,'onNextMonth') )
		h5 = HyperLink('>>') #, TargetHistoryToken=History.getToken())
		h5.addClickListener( getattr(self,'onNextYear') )

		tp.add(h1)
		tp.add(h2)

		# titlePanel can be changed, whenever we draw, so keep the reference

		self.titlePanel = SimplePanel()
		self.titlePanel.setWidget(HTML("<b>" + self.getMonthsOfYear()[mth-1] + " " + str(yr) + "</b>" ) )
		self.titlePanel.setStyleName("calendar-center")

		tp.add( self.titlePanel )
		tp.add(h4)
		tp.add(h5)
		tvp = VerticalPanel()
		tvp.setSpacing(10)
		tvp.add(tp)

		self.vp.add(tvp)

		# done with top panel

		self.middlePanel = SimplePanel()
		grid = self.drawGrid(mth,yr)
		self.middlePanel.setWidget(grid)
		self.vp.add(self.middlePanel)
		self.defaultGrid = grid
		#
		# some links & handlers
		#
		# bh1 = Hyperlink(self.yesterday, TargetHistoryToken=History.getToken())
		# bh1.addClickListener( getattr(self,'onYesterday') )
		bh2 = HyperLink(self.today) #, TargetHistoryToken=History.getToken())
		bh2.addClickListener( getattr(self,'onToday') )
		bh3 = HyperLink(self.tomorrow) #, TargetHistoryToken=History.getToken())
		bh3.addClickListener( getattr(self,'onTomorrow') )
		bh4 = HyperLink(self.cancel) #, TargetHistoryToken=History.getToken())
		bh4.addClickListener( getattr(self,'onCancel') )
		#
		# add code to test another way of doing the layout
		#
		b = HorizontalPanel()
		# b.add(bh1)
		# b.setCellWidth(bh1, "33%")
		b.add(bh2)
		b.setCellWidth(bh2, "50%")
		b.add(bh3)
		b.setCellWidth(bh3, "50%")
		b.addStyleName("calendar-shortcuts")
		self.vp.add(b)
		b2 = SimplePanel()
		b2.add(bh4)
		b2.addStyleName("calendar-cancel")
		self.vp.add(b2)

		self.setVisible(True)
		return

	def drawGrid(self,month,year):
		# draw the grid in the middle of the calendar

		daysInMonth = self.getDaysInMonth(month, year)
		secs = time.mktime( (year,month,1,0,0,0,0,0,-1) ) # first day of the month & year
		struct = time.localtime(secs)
		startPos = (struct.tm_wday + 1 ) % 7 # 0 - sunday for our needs instead 0 = monday in tm_wday
		slots = startPos + daysInMonth - 1
		rows = int(slots/7) + 1
		grid = Grid(rows+1, 7) # extra row for the days in the week
		grid.setWidth("100%")
		grid.addTableListener(self)
		self.middlePanel.setWidget(grid)
		#
		# put some content into the grid cells
		#
		for i in range(7):
			grid.setText(0, i, self.getDaysOfWeek()[i] )
			grid.cellFormatter.addStyleName(0,i,"calendar-header")
		#
		# draw cells which are empty first
		#
		day =0
		pos = 0
		while pos < startPos:
			grid.setText(1, pos , " ")
			grid.cellFormatter.setStyleAttr(1,pos,"background","#f3f3f3")
			grid.cellFormatter.addStyleName(1,pos,"calendar-blank-cell")
			pos += 1
		# now for days of the month
		row = 1
		day = 1
		col = startPos
		while day <= daysInMonth:
			if pos % 7 == 0 and day <> 1:
				row += 1
			col = pos % 7
			grid.setText(row,col, str(day) )
			if self.currentYear == self.todayYear and self.currentMonth == self.todayMonth and day == self.todayDay:
				grid.cellFormatter.addStyleName(row,col,"calendar-cell-today")
			else:
				grid.cellFormatter.addStyleName(row,col,"calendar-day-cell")
			day += 1
			pos += 1
		#
		# now blank lines on the last row
		#
		col += 1
		while col < 7:
			grid.setText(row,col," ")
			grid.cellFormatter.setStyleAttr(row,col,"background","#f3f3f3")
			grid.cellFormatter.addStyleName(row,col,"calendar-blank-cell")
			col += 1

		return grid

	def onCellClicked(self, grid, row, col):
		if row == 0:
			return
		text = grid.getText(row, col).strip()
		if text == "":
			return
		try:
			selectedDay = int(text)
		except ValueError, e:
			return
		# well if anyone is listening to the listener, fire that event
		for listener in self.selectedDateListeners:
			if hasattr(listener, "onDateSelected"):
				listener.onDateSelected(self.currentYear, self.currentMonth,
										selectedDay)
			else:
				listener(self.currentYear, self.currentMonth, selectedDay)
		self.setVisible(False)


	def onPreviousYear(self,event):
		self.drawPreviousYear()

	def onPreviousMonth(self,event):
		self.drawPreviousMonth()

	def onNextMonth(self,event):
		self.drawNextMonth()

	def onNextYear(self,event):
		self.drawNextYear()

	def onDate(self, event, yy, mm, dd):
		for listener in self.selectedDateListeners:
			if hasattr(listener, "onDateSelected"):
				listener.onDateSelected(yy,mm,dd)
			else:
				listener(yy,mm,dd)
		self.setVisible(False)

	def onYesterday(self,event):
		yesterday = time.localtime(time.time() - 3600 * 24)
		mm = yesterday.tm_mon
		dd = yesterday.tm_mday
		yy = yesterday.tm_year
		self.onDate(event, yy, mm, dd)

	def onToday(self,event):
		tod = time.localtime()
		mm = tod.tm_mon
		dd = tod.tm_mday
		yy = tod.tm_year
		self.onDate(event, yy, mm, dd)

	def onTomorrow(self,event):
		tom = time.localtime(time.time() + 3600 * 24)
		mm = tom.tm_mon
		dd = tom.tm_mday
		yy = tom.tm_year
		self.onDate(event, yy, mm, dd)

	def onCancel(self,event):
		self.setVisible(False)

	def drawCurrent(self):
		yr,mth,day = time.strftime("%Y-%m-%d").split("-")
		self.draw( int(mth), int(yr) )

	def drawDate(self, month, year ):
		# if year == self.currentYear and month == self.currentYear():
			# self.drawCurrent()
		self.currentMonth = month
		self.currentYear = year
		self.draw(self.currentMonth, self.currentYear)

	def drawPreviousMonth(self):
		if int(self.currentMonth) == 1:
			self.currentMonth = 12
			self.currentYear = int(self.currentYear) - 1
		else:
			self.currentMonth = int(self.currentMonth) - 1
		self.draw(self.currentMonth, self.currentYear)

	def drawNextMonth(self):
		if int(self.currentMonth) == 12:
			self.currentMonth = 1
			self.currentYear = int(self.currentYear) + 1
		else:
			self.currentMonth = int(self.currentMonth) + 1
		self.draw(self.currentMonth, self.currentYear)

	def drawPreviousYear(self):
		self.currentYear = int(self.currentYear) - 1
		self.draw(self.currentMonth, self.currentYear)

	def drawNextYear(self):
		self.currentYear = int(self.currentYear) + 1
		self.draw(self.currentMonth, self.currentYear)

class DateField(Composite):

	icon_img = "icon_calendar.gif"
	icon_style = "calendar-img"
	today_text = "Oggi"
	today_style = "calendar-today-link"

	def __init__(self,format='%d-%m-%Y'):
		self.is_enabled = True
		self.format = format
		self.tbox = TextBox()
		self.tbox.setVisibleLength(10)
		# assume valid sep is - / . or nothing
		if format.find('-') >= 0:
			self.sep = '-'
		elif format.find('/') >= 0:
			self.sep = '/'
		elif format.find('.') >= 0:
			self.sep = '.'
		else:
			self.sep = ''
		# self.sep = format[2] # is this too presumptious?
		self.calendar = Calendar()
		self.img = Image(self.icon_img)
		self.img.addStyleName(self.icon_style)
		self.calendarLink = self.img
		# self.calendarLink = HyperlinkImage(self.img, TargetHistoryToken=History.getToken())
		# self.todayLink = Hyperlink(self.today_text, TargetHistoryToken=History.getToken())
		# self.todayLink.addStyleName(self.today_style)
		#
		# lay it out
		#
		hp = HorizontalPanel()
		hp.setVerticalAlignment(HasAlignment.ALIGN_MIDDLE)
		#hp.setSpacing(2)
		vp = VerticalPanel()
		hp.add(self.tbox)
		#vp.add(self.calendarLink)
		#vp.add(self.todayLink)
		hp.add(self.calendarLink)
		#hp.add(vp)

		Composite.__init__(self)
		self.initWidget(hp)
		#
		# done with layout, so now set up some listeners
		#
		self.tbox.addFocusListener(self) # hook to onLostFocus
		self.calendar.addSelectedDateListener(getattr(self,"onDateSelected"))
		# self.todayLink.addClickListener(getattr(self,"onTodayClicked"))
		self.calendarLink.addClickListener(getattr(self,"onShowCalendar"))
		self.change_listeners = []
		self.tbox.addChangeListener(self.onChange)
		self.listener = None

	def setEnabled(self, e):
		self.tbox.setEnabled(e)
		self.is_enabled = e

	def getTextBox(self):
		return self.tbox

	def getCalendar(self):
		return self.calendar

	def setID(self,id):
		self.tbox.setID(id)

	def addChangeListener(self, listener):
		self.change_listeners.append(listener)

	def onChange(self):
		for l in self.change_listeners:
			l()

	def onDateSelected(self, yyyy, mm, dd):
		secs = time.mktime((int(yyyy),int(mm),int(dd),0,0,0,0,0,-1))
		d = time.strftime(self.format,time.localtime(secs))
		self.tbox.setText(d)
		self.onChange()
		if self.listener is not None:
			self.listener()

	def onLostFocus(self, sender):
		#
		text = self.tbox.getText().strip()
		# if blank - leave it alone
		if text and len(text) == 8:
			# ok what format do we have? assume ddmmyyyy --> dd-mm-yyyy
			self.tbox.setText( text[0:2] + self.sep + text[2:4] + self.sep + text[4:8] )

	def onFocus(self, sender):
		pass

	def onTodayClicked(self, event):
		today = time.strftime(self.format)
		self.tbox.setText( today )
		self.onChange()

	def onShowCalendar(self, sender):
	  if self.is_enabled:
			p = CalendarPopup(self.calendar)
			d = self.tbox.getText()
			arr = d.split("-")
			if len(arr) == 3 and arr[0].isdigit() and arr[1].isdigit():
				year = int(arr[0])
				month = int(arr[1])
				if year >= 2010 and month >= 1 and month <= 12:
					self.calendar.draw(month, year)
			x = self.tbox.getAbsoluteLeft() + 10
			y = self.tbox.getAbsoluteTop() + 10
			p.setPopupPosition(x,y)
			p.show()
		
	def setListener(self, listener):
		self.listener = listener
	   

#Factory.registerClass('pyjamas.ui.Calendar', Calendar)

class CalendarPopup(PopupPanel):
	def __init__(self, c):
		PopupPanel.__init__(self, True)
		p = SimplePanel()
		p.add(c)
		c.show(10,10)
		p.setWidth("100%")
		self.setWidget(p)

#Factory.registerClass('pyjamas.ui.CalendarPopup', CalendarPopup)

class MenuCmd:
	def __init__(self, object, handler):
		self._object  = object
		self._handler = handler

	def execute(self):
		handler = getattr(self._object, self._handler)
		handler()

class TimeField(HorizontalPanel):
	def __init__(self):
		HorizontalPanel.__init__(self)
		self.time = TextBox()
		self.time.setVisibleLength(5)
		self.add(self.time)
		self.sottomenu = MenuBar(vertical=True)
		self.sottomenu.addItem("Adesso", MenuCmd(self, "on0"))
		self.sottomenu.addItem("Adesso + 30 min.", MenuCmd(self, "on0_5"))
		self.sottomenu.addItem("Adesso + 1 ora", MenuCmd(self, "on1"))
		self.sottomenu.addItem("Adesso + 1 ora 30 min.", MenuCmd(self, "on1_5"))
		self.sottomenu.addItem("Adesso + 2 ore", MenuCmd(self, "on2"))								
		self.sottomenu.addItem("Adesso + 4 ore", MenuCmd(self, "on4"))
		self.sottomenu.addItem("Adesso + 6 ore", MenuCmd(self, "on6"))
		self.menu = MenuBar(vertical=False)
		self.menu.addItem('<img src="icon_clock.gif" >', True, self.sottomenu)
		self.add(self.menu)
		self.listener = None
		
	def setDelta(self, delta):
		self.time.setText(time.strftime("%H:%M", time.localtime(time.time() + delta*60)))
		if self.listener is not None:
			self.listener()

	def on0(self):
		self.setDelta(0)

	def on0_5(self):
		self.setDelta(30)

	def on1(self):
		self.setDelta(1*60)

	def on1_5(self):
		self.setDelta(90)
	
	def on2(self):
		self.setDelta(2*60)
		
	def on4(self):
		self.setDelta(4*60)
		
	def on6(self):
		self.setDelta(6*60)
			
	def getTextBox(self):
		return self.time
	
	def setListener(self, listener):
		 self.listener = listener

