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

from pages.models import *
from django.template.response import TemplateResponse
from servizi.utils import hist_redirect
from django.utils.translation import ugettext_lazy as _
from datetime import date, time, datetime, timedelta
import traceback

def default(request, slug):
	ctx = {}
	try:
		p = Page.objects.get(slug=slug, codice_lingua=request.lingua.codice)
		n = datetime.now()
		if (
			not p.enabled
			or
			(p.from_date is not None and p.from_date > n)
			or
			(p.to_date is not None and p.to_date < n)
		):
			raise Exception('Not enabled')
	except:
		traceback.print_exc()
		return hist_redirect(request, '/', msg=_(u"La pagina richiesta non esiste."))
	ctx['page'] = p
	return TemplateResponse(request, 'page.html', ctx)
