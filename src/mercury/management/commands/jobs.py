# coding: utf-8

#
#    Copyright 2015-2016 Roma servizi per la mobilità srl
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


from django.core.management.base import BaseCommand, CommandError
from optparse import make_option
import settings
import os, subprocess, signal
from datetime import date, time, datetime, timedelta
from servizi.utils import datetime2time, close_idle_db_connections
from django.db.models import Q
from mercury.models import *
import traceback
import sys

config = {
	'allow_public_attrs': True,
}


def match_sched(sched, value):
	if sched == '*':
		return True
	sched = sched.split(',')
	for s in sched:
		if value == int(s):
			return True
	return False


class Command(BaseCommand):
	args = "node_name"
	help = """
		Run scheduled jobs for this node.

		Each job is run in a separate process.
		To be launched every minute, e.g. via a crontab script
		
		Furthermore, cleanup idle db connections to avoid shortage
		of available connections
	"""
	option_list = BaseCommand.option_list

	def handle(self, *args, **options):
		close_idle_db_connections()

		n = datetime.now()

		if len(args) == 1:
			name = args[0]
		else:
			raise CommandError("Invalid parameters")

		jobs = Job.objects.filter(node__name=name)
		for j in jobs:
			try:
				mins = j.sched_minute
				if mins != '*':
					mins = mins.split(',')
				if j.action != 'S' and (
					j.action in ['F', 'O']
					or (
						match_sched(j.sched_minute, n.minute)
						and match_sched(j.sched_hour, n.hour)
						and match_sched(j.sched_dow, n.weekday())
						and match_sched(j.sched_dom, n.day)
						and match_sched(j.sched_moy, n.month)
					)
				):
					if j.action == 'F':
						j.action = 'N'
					elif j.action == 'O':
						j.action = 'S'
					j.save()

					command = "%s manage.py run_job %s" % (sys.executable, j.function)
					print "Lancio %s" % j.function
					print subprocess.Popen(command.split())

			except:
				print "Exception while launching job %s" % j.function
				j.last_status = -1
				j.last_message = 'Exception in job scheduler: %s' % traceback.format_exc()
				j.save()