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
from servizi.utils import datetime2time
from django.db.models import Q
from mercury.models import *
import traceback
import importlib
from django.db import transaction

config = {
	'allow_public_attrs': True,
}

class Command(BaseCommand):
	args = "job_function"
	help = """
		Run a single job.

		Job is run only if no other instances of the same job were running within job timeout.
	"""
	option_list = BaseCommand.option_list + (
		make_option(
			'-i',
			action='store_true',
			dest='ignore_timeout',
			default=False,
			help='Ignore job timeout, always start a new instance',
		),
	)

	@transaction.commit_manually
	def handle(self, *args, **options):
		
		n = datetime.now()

		if len(args) == 1:
			name = args[0]
		else:
			transaction.rollback()
			raise CommandError("Invalid parameters")

		try:
			j = Job.objects.get(function=name)
		except Job.DoesNotExist:
			transaction.rollback()
			raise CommandError("Job %s does not exist in database" % name)

		if not options['ignore_timeout'] and (j.keepalive_ts is not None and n < j.keepalive_ts + timedelta(minutes=j.timeout_minutes)):
			transaction.rollback()
			raise CommandError("Job %s already in progress" % name)

		j.start_ts = n
		j.keep_alive()
		transaction.commit()

		try:
			module, function = name.split('.')
			m = importlib.import_module("%s.jobs" % module)
			status, message = getattr(m, function)(j)
			print "Job %s completed" % name
			j.completed_ts = datetime.now()
			j.last_status = status
			j.last_message = message
		except:
			print "Exception while executing job %s" % name
			j.last_status = -1
			j.last_message = 'Exception caught by job handler: %s' % traceback.format_exc()

		j.stop_ts = datetime.now()
		j.save()
		transaction.commit()

