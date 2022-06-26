import re
import os
import os.path
import sys
import shutil
from optparse import OptionParser
import polib
from pprint import pprint, pformat

def createDirAndGo(path, dir):
	final = os.path.join(path, dir)
	if not os.path.isdir(final) and not os.path.isfile(final):
		os.mkdir(final)
	return final

def execute(path, xrc=False, lang=[]):
	print path
	d = os.listdir(path)
	created = []
	for f in d:
		fp = os.path.join(path, f)
		if os.path.isfile(fp):
			n, e = os.path.splitext(f)
			if xrc and e == '.xrc':
				newfp = os.path.join(path, n + '.pos')
				wx.tools.pywxrc.main(['', '-g', '-o', newfp, fp])
				fp = newfp
			if e == '.py' or (xrc and e == '.xrc'):
				join = ''
				if os.path.isfile(os.path.join(path, 'messages.pot')):
					join = '-j '
				s = 'xgettext -L python %s-o messages.pot "%s"' % (join, fp)
				print s
				os.system(s)
	for l in lang:
		p = createDirAndGo(path, "locale")
		pl = createDirAndGo(p, l)
		pl = createDirAndGo(pl, 'LC_MESSAGES')
		# n, e = os.path.splitext(f)
		fn = os.path.join(pl, "messages.po")
		fo = os.path.join(path, "messages.pot")
		if os.path.isfile(fn):
			s = 'msgmerge -U "%s" "%s"' % (fn, fo)
			print s
			os.system(s)
		else:
			shutil.copy(fo, fn)

def parse_for_pyjamas(path, lang):
	for l in lang:
		p = createDirAndGo(path, "locale")
		pl = createDirAndGo(p, l)
		pl = createDirAndGo(pl, 'LC_MESSAGES')
		po = polib.pofile(os.path.join(pl, 'messages.po'))
		out = {}
		for l in lang:
			out[l] = {}
			for entry in po:
				if entry.msgstr != '':
					out[l][entry.msgid] = entry.msgstr
		with open(os.path.join(path, 'messages.py'), 'w') as f:
			f.write("messages = " + pformat(out))

if __name__ == '__main__':
	parser = OptionParser()
	parser.add_option("-d", "--dir", dest="dir",
										help="directory to process")
	parser.add_option("-l", "--languages", dest="lang",
										help="comma-separated list of languages to handle (init, merge)")
	parser.add_option("-x", "--xrc",
										action="store_true", dest="xrc", default=False,
										help="process xrc files (wxWidgets required)")

	parser.add_option("-p", "--pyjamas",
										action="store_true", dest="pyjamas", default=False,
										help="generate dictionary for usage in pyjamas")

	(options, args) = parser.parse_args()
	if options.xrc:
		import wx.tools.pywxrc
	if options.lang != None:
		lang = options.lang.split(',')
	else:
		lang = []
	if options.dir == None:
		path = os.path.abspath(os.curdir)
	else:
		path = options.dir
	execute(path, options.xrc, lang)
	if options.pyjamas:
		parse_for_pyjamas(path, lang)


