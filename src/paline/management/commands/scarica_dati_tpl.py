# coding: utf-8

from django.core.management.base import BaseCommand, CommandError
from paline import jobs

class Command(BaseCommand):
	args = """
	"""

	help = """
		Scarica da Muoveri a Roma:
		* rete GTFS
		e aggiorna il db locale
	"""
	

	def handle(self, *args, **options):
		jobs.scarica_rete_tpl()


