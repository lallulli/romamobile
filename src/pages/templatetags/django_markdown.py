# coding: utf-8
from django import template
from django.utils.safestring import mark_safe
# import mistune
import markdown as mdown

register = template.Library()

@register.filter
def markdown(value):
	# return mark_safe(mistune.markdown(value))
	return mark_safe(mdown.markdown(value, extensions=['extra']))

# @register.filter
# def percentage(value):
# 	return '{0:.0%}'.format(value)
