from django.core.management.base import BaseCommand
from django.db import connections
# from django.db.utils import OperationalError
import time


class Command(BaseCommand):
    """ Django command to pause execution until database is available"""
    def handle(self, *args, **kwargs):
        self.stdout.write('waiting for db ...')
        db_conn = None
        while not db_conn:
            try:
                # get the database with keyword 'default' from settings.py
                db_conn = connections['default']
                # prints success messge in green
                self.stdout.write('db available')
            except:
                self.stdout.write("Database unavailable, waiting 1 second ...")
                time.sleep(1)
