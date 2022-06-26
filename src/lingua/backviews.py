# Create your views here.
from carpooling.views import is_utente_carpooling
from servizi.models import Lingua, LinguaPreferita
from django.db import models, connections, transaction
from servizi.utils import dict_cursor, project, datetime2mysql, group_required
from datetime import datetime, timedelta, time, date
from jsonrpc import jsonrpc_method
from paline import tratto
from copy import copy
import rpyc
import cPickle as pickle
import views
from pprint import pprint


@jsonrpc_method('lingua_set', safe=True)
def lingua_set(
	request,
	codice,
):
	l = Lingua.objects.get(codice=codice)
	request.session['lingua'] = l
	if request.user.is_authenticated():
		try:
			lp = LinguaPreferita.objects.get(utente=request.user)
			lp.lingua = l
			lp.save()
		except LinguaPreferita.DoesNotExist:
			LinguaPreferita(utente=request.user, lingua=l).save()
	return 'OK'
