'''\
string utilities
mocons.lib.utils.strutil.py
jjk  02/03/98  001  from mdcutil.py
jjk  02/18/98  002  unzfill() fix
jjk  02/19/98  003  add padLeading(}, padTrailing()
jjk  11/15/99  004  documentation updates

Equivalent built-in python functions may be available.
If so, I wrote these before they were available, or
before I was aware of them. :-)

def stripChar(aString, aChar):
def stripLeading(aString, aChar):
def stripTrailing(aString, aChar):
def unzfill(aString):
def replaceAll(aString, subStr, replStr):
def padLeading(aString, length, padChar=' '):
def padTrailing(aString, length, padChar=' '):

*** !!  USE AT YOUR OWN RISK    !! ***
*** !! NO WARRANTIES WHATSOEVER !! ***

Jeff Kunce <kuncej@mail.conservation.state.mo.us>
'''

import string

def stripChar(aString, aChar):
	# answer a String which is aString with leading and trailing aChar's removed
	# jjk  01/11/96
	s1 = stripLeading(aString, aChar)
	return(stripTrailing(s1, aChar))

def stripLeading(aString, aChar):
	# answer a String which is aString with leading aChar's removed
	# jjk  01/11/96
	s1 = aString
	p1 = 0
	while ((p1 < len(s1)) and (s1[p1] == aChar)):
		p1 = p1 + 1
	if (p1 > 0):
		s1 = s1[p1:]
	return(s1)

def stripTrailing(aString, aChar):
	# answer a String which is aString with trailing aChar's removed
	# jjk  01/11/96
	s1 = aString
	p1 = len(s1) - 1
	while ((p1 >= 0) and (s1[p1] == aChar)):
		p1 = p1 - 1
	if (p1 < (len(s1) - 1)):
		s1 = s1[:(p1+1)]
	return(s1)

def unzfill(aString):
	# return aString with trailing nulls removed
	# jjk  02/18/98
	p0 = string.find(aString, '\000')
	if (p0 < 0): return(aString)
	return(aString[:p0])

def replaceAll(aString, subStr, replStr):
	# answers a string which is aString  with all instances of subStr replaced with replStr
	# jjk  02/08/96
	return(string.joinfields(string.splitfields(aString, subStr), replStr))

def padLeading(aString, length, padChar=' '):
	'''pad aString with leading padChars until it is at least length long
	jjk  02/19/98'''
	npc = length -len(aString)
	if (npc<=0): return(aString)
	return((npc*padChar)+aString)

def padTrailing(aString, length, padChar=' '):
	'''pad aString with trailing padChars until it is at least length long
	jjk  02/19/98'''
	npc = length -len(aString)
	if (npc<=0): return(aString)
	return(aString+(npc*padChar))

