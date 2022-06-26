# coding: utf-8

#
#    Copyright 2017 Roma mobile
#    Developed by Luca Allulli
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


from models import *
from django.http import HttpResponseRedirect
from datetime import datetime, timedelta


def get_client_ip(request):
	x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		ip = x_forwarded_for.split(',')[0]
	else:
		ip = request.META.get('REMOTE_ADDR')
	return ip


def redirect(request, slug):
	try:
		u = Url.objects.get(slug=slug)
		Log(
			url=u,
			time=datetime.now(),
			ip=get_client_ip(request),
			user_agent=request.META.get('HTTP_USER_AGENT')
		).save()
		u.count += 1
		u.save()
		return HttpResponseRedirect(u.target)
	except:
		return HttpResponseRedirect('/')

