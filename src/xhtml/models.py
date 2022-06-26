# encoding: utf-8

from django.contrib.gis.db import models
import markdown
from django.db.models import Q, F
from datetime import date, time, datetime, timedelta
from servizi import utils
from redirect.models import Url
import random

ICON_POSITION_CHOICES = (
	(u'up', u"Above text"),
	(u'left', u"On the left"),
	(u'off', u"Manual positioning or no icon"),
)


def genkey():
	return utils.generate_key(30)


class Ad(Url):
	codice_lingua = models.CharField(max_length=6, default='it')
	is_ad = models.BooleanField(blank=True, default=True)
	title = models.CharField(default='Pubblicità', max_length=765, help_text="Generated as an H2")
	enabled = models.BooleanField(default=True, blank=True)
	icon = models.ImageField(null=True, blank=True, upload_to='img/btn/')
	icon_position = models.CharField(max_length=7, choices=ICON_POSITION_CHOICES, default='left')
	content = models.TextField(default='')
	markdown = models.BooleanField(default=True, blank=True)
	geom = models.PointField(srid=3004, null=True, blank=True, db_index=True, default=None)
	boost = models.FloatField(default=1, db_index=True)
	max_reboost = models.FloatField(default=40)
	boost_unary_dist = models.FloatField(default=750)
	from_date = models.DateTimeField(blank=True, null=True, db_index=True)
	to_date = models.DateTimeField(blank=True, null=True, db_index=True)
	n_views = models.IntegerField(default=0)
	max_views = models.IntegerField(null=True, blank=True)
	cached_content = models.TextField(default='', blank=True, editable=False)
	key = models.CharField(max_length=31, blank=True, default=genkey)

	def save(self, *args, **kwargs):
		if self.markdown:
			self.cached_content = markdown.markdown(self.content, extensions=['extra'])
		else:
			self.cached_content = self.content
		super(Ad, self).save(*args, **kwargs)

	def increment_views(self, increment=1):
		Ad.objects.filter(id=self.id).update(n_views=F('n_views') + increment)
		return ''

	@classmethod
	def random_choice(cls, language, increment_views=True, point=None):
		cas = list(cls.get_candidate_ads(language))
		if len(cas) == 0:
			return None
		if point is None:
			i = utils.weighted_random_choice(ca.boost for ca in cas)
		else:
			rcs = []
			for ca in cas:
				if ca.geom is None:
					rcs.append(ca.boost)
				else:
					d = ca.geom.distance(point)
					if d < 1:
						rcs.append(ca.boost * ca.max_reboost)
					else:
						reboost = min(ca.max_reboost, ca.boost_unary_dist / d)
						rcs.append(ca.boost * reboost)
			i = utils.weighted_random_choice(rcs)
		ca = cas[i]
		if increment_views:
			ca.increment_views()
		ca.random = random.randint(0, 100000)
		return ca

	@classmethod
	def get_candidate_ads(cls, language):
		n = datetime.now()

		return cls.objects.filter(
			Q(codice_lingua=language),
			Q(boost__gt=0) &
			Q(Q(from_date=None) | Q(from_date__lte=n)) &
			Q(Q(to_date=None) | Q(to_date__gte=n)) &
			Q(Q(max_views=None) | Q(max_views__gt=F('n_views'))) &
			Q(enabled=True)
		)


"""
alter table xhtml_ad
add column geom geometry(POINT, 3004) default null; 
CREATE INDEX "xhtml_ad_geom" ON "xhtml_ad" ("geom");
CREATE INDEX "xhtml_ad_geom_id" ON "xhtml_ad" USING GIST ( "geom" );

alter table xhtml_ad
add column max_reboost double precision not null default 40;

alter table xhtml_ad
add column boost_unary_dist double precision not null default 750;
 

"""