import os, os.path
import re
import shutil
from pprint import pprint
from datetime import date, time, datetime, timedelta
from sys import argv


def get_filepaths(directory):
	"""This function will generate the file names in a directory
	tree by walking the tree either top-down or bottom-up. For each
	directory in the tree rooted at directory top (including top itself),
	it yields a 3-tuple (dirpath, dirnames, filenames).
	"""
	file_paths = []  # List which will store all of the full filepaths.

	# Walk the tree.
	for root, directories, files in os.walk(directory):
		for filename in files:
			# Join the two strings in order to form the full filepath.
			filepath = os.path.join(root, filename)
			file_paths.append(filepath)  # Add it to the list.

	return [f.replace('\\', '/') for f in file_paths]  # Self-explanatory.


ESCLUSIONI = [
	r'.*red.appcache$',
	r'.*db$',
	#r'.*lib/.*',
	r'.*opera.*',
	r'.*oldmoz.*',
	r'.*ie6.*',
	r'.*safari.*',
]

r = '|'.join(["(%s)" % x for x in ESCLUSIONI])
rex = re.compile(r)

if len(argv) > 1:
	paths = []
else:
	paths = get_filepaths('output')
	paths = [f.replace('output', '/percorso/js') for f in paths if rex.search(f) is None]

pprint(paths)

f = open('output/red.appcache', 'w')
f.write("""CACHE MANIFEST
# %s
CACHE:
%s

NETWORK:
*
""" % (str(datetime.now()), '\n'.join(paths)))
f.close()

for el in ['safari', 'opera', 'oldmoz']:
	try:
		os.remove('output/main.%s.cache.html' % el)
	except:
		pass


# shutil.rmtree('deploy', ignore_errors=True)
# # os.makedirs('deploy')
# shutil.copytree('output', 'deploy')
# shutil.rmtree('deploy/lib', ignore_errors=True)


