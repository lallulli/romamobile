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
from servizi.utils import modifica_url_con_storia
import settings

register = template.Library()


def hist(parser, token):
	nodelist = parser.parse(('endhist',))
	parser.delete_first_token()
	return HistNode(nodelist, 1)

def nohist(parser, token):
	nodelist = parser.parse(('endnohist',))
	parser.delete_first_token()
	return HistNode(nodelist, 0)

class HistNode(template.Node):
	def __init__(self, nodelist, offset):
		self.nodelist = nodelist
		self.offset = offset
	def render(self, context):
		return modifica_url_con_storia(context['request'], self.nodelist.render(context), self.offset)


register.tag('hist', hist)
register.tag('nohist', nohist)

@register.simple_tag(takes_context=True)
def formhist(context):
	request = context['request']
	session = ''
	if request.does_not_accept_cookies:
		session = '<input type="hidden" name="%s" value="%s" />' % (settings.SESSION_COOKIE_NAME, request.session.session_key)	
	return '<input type="hidden" name="nav" value="%d" />%s' % (len(context['request'].session['history']), session)
formhist.is_safe=True

@register.simple_tag(takes_context=True)
def formnohist(context):
	request = context['request']
	session = ''
	if request.does_not_accept_cookies:
		session = '<input type="hidden" name="%s" value="%s" />' % (settings.SESSION_COOKIE_NAME, request.session.session_key)		
	return '<input type="hidden" name="nav" value="%d" />%s' % ((len(context['request'].session['history']) - 1), session)
formnohist.is_safe=True

@register.simple_tag(takes_context=True)
def addparam(context, param):
	request = context['request']
	url = request.path_info
	url = url.split('#')
	id = ('#' + url[1]) if len(url) > 1 else ''
	url = url[0].split('?')
	pre = url[0]
	op = dict([(x, request.GET[x]) for x in request.GET if x not in ['back', 'nav']])
	op['nav'] = len(request.session['history']) - 1
	if '#' in param:
		id = ''
	return pre + '?' + "&amp;".join([u'%s=%s' % (x, op[x]) for x in op]) + "&amp;" + param + id

@register.filter
def in_group(user, group):
	"""Returns True/False if the user is in the given group(s).
	Usage::
		{% if user|in_group:"Friends" %}
		or
		{% if user|in_group:"Friends,Enemies" %}
		...
		{% endif %}
	You can specify a single group or comma-delimited list.
	No white space allowed.
	"""
	import re
	if re.search(',', group): group_list = re.sub('\s+','',group).split(',')
	elif re.search(' ', group): group_list = group.split()
	else: group_list = [group]
	user_groups = []
	for group in user.groups.all(): user_groups.append(str(group.name))
	if filter(lambda x:x in user_groups, group_list): return True
	else: return False
in_group.is_safe = True