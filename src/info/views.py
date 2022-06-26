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
from django.db import models, connections, transaction
from log_servizi.models import ServerVersione
import errors
from servizi.utils import dict_cursor, project, messaggio, hist_redirect
import uuid
import hashlib
import datetime
from django.template.response import TemplateResponse
from servizi.models import Lingua, LinguaPreferita
from django.utils import translation
from django.utils.translation import ugettext as _

lingue1 = ServerVersione("lingue", 1)


def cookies(request):
	return TemplateResponse(request, 'info-cookies.html', {})


def dev(request):
	return TemplateResponse(request, 'info-dev.html', {})