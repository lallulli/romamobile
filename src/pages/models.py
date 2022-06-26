# coding: utf-8

#
#    Copyright 2020 Skeed di Luca Allulli
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

from django.db import models
import markdown

class Page(models.Model):
	slug = models.CharField(max_length=127, db_index=True)
	codice_lingua = models.CharField(max_length=6, default='it')
	title = models.CharField(max_length=765, help_text="Page title is generated as an H2")
	content = models.TextField(default='')
	markdown = models.BooleanField(default=True, blank=True)
	enabled = models.BooleanField(default=True, blank=True)
	from_date = models.DateTimeField(blank=True, null=True)
	to_date = models.DateTimeField(blank=True, null=True)
	cached_content = models.TextField(default='', blank=True, editable=False)

	def save(self, *args, **kwargs):
		if self.markdown:
			self.cached_content = markdown.markdown(self.content, extensions=['extra'])
		super(Page, self).save(*args, **kwargs)

	def __unicode__(self):
		return self.slug

