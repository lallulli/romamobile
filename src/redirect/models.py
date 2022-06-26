# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#	 * Rearrange models' order
#	 * Make sure each model has one field with primary_key=True
# Feel free to rename the models, but don't rename db_table values or field names.
#
# Also note: You'll have to insert the output of 'django-admin.py sqlcustom [appname]'
# into your database.

from django.contrib.gis.db import models


class Url(models.Model):
	slug = models.CharField(max_length=63, db_index=True)
	target = models.CharField(max_length=2047)
	count = models.IntegerField(default=0)

	objects = models.GeoManager()

	def __unicode__(self):
		return self.slug


class Log(models.Model):
	url = models.ForeignKey(Url, on_delete=models.CASCADE)
	time = models.DateTimeField()
	user_agent = models.TextField(null=True, blank=True, default=None)
	ip = models.IPAddressField(null=True, blank=True, default=None)

	def __unicode__(self):
		return u"[{}] {}".format(self.time, self.url)

