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

from django import template
from django.utils.translation import ugettext as _

register = template.Library()
from django.template.defaultfilters import floatformat

def sec2min(secs):
	return int(round(secs/60.0))

def sec2min_lab(secs):
	m = sec2min(secs)
	if m == 1:
		return _("1 minuto")
	return _("%d minuti") % m

def arrotonda_distanza(n):
	step = 50
	k = round(n / float(step)) * step
	if k == 0:
		return _("meno di %.0f metri") % step
	if k > 1000:
		return _("%.1f km") % (k / 1000.0)
	return _("%.0f metri") % k

@register.filter
def percent(value):
  if value is None:
    return None
  return floatformat(value * 100.0, 2) + '%'

register.filter('sec2min', sec2min)
register.filter('sec2min_lab', sec2min_lab)
register.filter('arrotonda_distanza', arrotonda_distanza)
