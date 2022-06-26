#!/usr/local/bin/python
#
'''\
access a dbf file (read access works, write *might* work)
mocons.persist.dbf.py
jjk  02/18/98  001  from dbfload.py 004
jjk  02/19/98  002  add create/write capabilities
jjk  02/20/98  003  fix problems, add more features
jjk  06/08/98  004  fix problems, add more features
jjk  08/24/98  005  add some encodeValue methods (not tested), other tweaks
jjk  11/15/99  006  documentation updates, add demo

Example Usage:
	aDbf = Dbf()
	aDbf.openFile('fname.dbf', readOnly=1)
	numberOfRecords = len(aDbf)
	aDbfRecord = aDbf[recordIndex]
	aFieldName = aDbf.fieldNames[fieldIndex]
	aFieldValue = aDbfRecord[aFieldName]
also see demo1() function

*** !!  USE AT YOUR OWN RISK    !! ***
*** !! NO WARRANTIES WHATSOEVER !! ***

Jeff Kunce <kuncej@mail.conservation.state.mo.us>
'''

import sys
import string
import time

try: import binnum 
except ImportError: from mocons.lib.utils import binnum 

try: import strutil 
except ImportError: from mocons.lib.utils import strutil 

class Dbf:
	'''access dBase (.dbf) data
	jjk  02/18/98'''

	def __init__(self):
		'''public: initialize the receiver
		jjk  02/18/98'''
		self._reset()

	def _reset(self):
		'''private: reset the receiver instance variables to the initial state
		jjk  02/18/98'''
		self.dbfName = ''			# dbf file name '' if none
		self.dbfStream = None		# file object open on dbf data
		self.changed = 0

	def close(self):
		'''public: flush data, close files, clear buffers
		jjk  02/18/98'''
		self.flush()
		if (self.isOpen()):
			self.dbfStream.close()
		self._reset()

	def isOpen(self):
		'''public: answer true if the receiver has an open file
		jjk  02/18/98'''
		return(self.dbfStream!=None)

	def recordCount(self):
		'''public: answer the number of records in the receiver
		jjk  02/18/98'''
		return(self.header.recordCount)

	def fieldNames(self):
		'''public: answer the names of the receivers fields
		jjk  02/18/98'''
		return(self.header.fieldNames)

	def fieldDefinitions(self):
		'''public: answer the field definitions for the receiver
		jjk  02/19/98'''
		return(self.header.fieldDefs)

	def indexOfFieldName(self, fieldName):
		'''system: answer the index of fieldName in records of the receiver
		jjk  02/13/98'''
		return(self.header.fieldIndex[fieldName])

	def flush(self):
		'''public: flush any data in memory to file
		jjk  02/19/98'''
		if (not self.isOpen()): return
		if (self.changed):
			self.header.setCurrentDate()
			self.header.writeOn(self.dbfStream)
			self.changed = 0
		self.dbfStream.flush()

	def openFile(self, dbfFileName, readOnly=0):
		'''public: open the receiver on the specified dbf file name
		jjk  08/24/98'''
		if (readOnly): mode = 'rb'
		else: mode = 'r+b'
		dbfs = open(dbfFileName, mode)
		self.openOn(dbfs)
		self.dbfName = dbfFileName
		return(self)

	def openOn(self, dbfFileStream):
		'''public: open the receiver on the open dbf file stream
		jjk  08/24/98'''
		self.close()
		self.header = DbfHeader()
		self.header.readFrom(dbfFileStream)
		self.dbfStream = dbfFileStream
		return(self)
	
	def openString(self, aString):
		'''public: open the receiver on a string of raw dbf data
		jjk  08/24/98'''
		import StringIO
		dbfs = StringIO.StringIO(aString)
		self.openOn(dbfs)
		self.dbfName = ''
		return(self)
	
	def rawContents(self):
		'''public: answer the complete raw contents of the receiver as a string
		jjk  02/20/98'''
		self.dbfStream.seek(0)
		return(self.dbfStream.read())
	
	def reportOn(self, outs=sys.stdout, indent=0):
		'''Public: report info about the receiver
		jjk  02/18/98'''
		inds = indent*'\t'
		outs.write('%sDbf Instance  file: %s\n'%(inds,self.dbfName))
		self.header.reportOn(outs, indent+1)
		#outs.write('  deleted records: %d\n\n'%len(self.deletedRecords()))

	def __len__(self):
		'''public: answer number of records in the receiver
		jjk  06/08/98'''
		return(self.recordCount())

	def __getitem__(self, anIndex):
		'''public: answer the DbfRecordread at anIndex in the receiver.
		jjk  02/18/98'''
		rec = DbfRecord(self)
		rec.readData(anIndex)
		return(rec)

	def newRecord(self):
		'''public: answer new DbfRecordread created for the receiver.
		jjk  02/19/98'''
		rec = DbfRecord(self)
		return(rec)

	def append(self, aDbfRecord):
		'''public: add aDbfRecord to the end of the receiver
		jjk  02/19/98'''
		aDbfRecord.recordIndex = self.header.recordCount
		aDbfRecord.writeData()
		self.header.recordCount = self.header.recordCount + 1
		self.changed = 1

	def __setitem__(self, anIndex, aDbfRecord):
		'''public: write DbfRecordread at anIndex in the receiver.
		jjk  02/19/98'''
		aDbfRecord.writeData()
		self.changed = 1

class DbfHeader:
	'''system: header data for a dbf file
	jjk  02/18/98'''

	def __init__(self):
		'''public: initialize the receiver
		jjk  02/18/98'''
		self._reset()

	def _reset(self):
		'''system: reset the receiver data
		jjk  02/18/98'''
		self.version = 0x03	#0x03=no memo  0x83=memo
		self.setCurrentDate()
		self.recordCount = 0
		self._computeHeaderLength()
		self.recordLength = 0
		self.fieldDefs = []
		self.fieldNames = []
		self.fieldIndex = {}

	def setCurrentDate(self):
		'''system: set the receiver's date values to current day
		jjk  02/18/98'''
		timeA = time.localtime(time.time())
		self.year = timeA[0]
		self.month = timeA[1]
		self.day = timeA[2]

	def _computeHeaderLength(self):
		'''private: compute the receiver's headerLength value
		jjk  02/18/98'''
		self.headerLength = 32+(32*self.recordCount)+1

	def addFieldDef(self, aFieldDef):
		'''system: read and dcode dbf header data from binary input stream
		jjk  02/18/98'''
		self.fieldDefs.append(aFieldDef)
		self.fieldNames.append(aFieldDef.name)
		self.fieldIndex[aFieldDef.name] = len(self.fieldNames)-1

	def readFrom(self, dbfs):
		'''system: read and decode dbf header data from binary input stream
		jjk  02/19/98'''
		self._reset()
		dbfs.seek(0)
		hdrRawData = dbfs.read(32)
		self._fromRawData(hdrRawData)
		fieldCount = (self.headerLength - 33) / 32
		startPos = 1 #byte 0 is delete flag
		for fn in range(fieldCount):
			rawFieldDef = dbfs.read(32)
			fd = DbfFieldDefFromRawData(rawFieldDef, startPos)
			self.addFieldDef(fd)
			startPos = fd.end
		skip = dbfs.read(1)

	def _fromRawData(self, rawData):
		'''private: instantiate the receiver from dbf 32-byte raw header
		jjk  02/19/98'''
		self.version = ord(rawData[0])
		self.year = 1900+ord(rawData[1])
		self.month = ord(rawData[2])
		self.day = ord(rawData[3])
		self.recordCount = binnum.unsigned_from_Intel4(rawData[4:8])
		self.headerLength = binnum.unsigned_from_Intel2(rawData[8:10])
		self.recordLength = binnum.unsigned_from_Intel2(rawData[10:12])
		#reserved = rawData[12:32]

	def writeOn(self, dbfs):
		'''system: encode and write dbf header data on binary output stream
		jjk  02/19/98'''
		dbfs.seek(0)
		dbfs.write(self._asRawData())
		for fd in self.fieldDefs:
			dbfs.write(fd.asRawData())
		dbfs.write(chr(0x0D))	# cr at end of all hdr data

	def _asRawData(self):
		'''private: encode and answer dbf 32-byte raw header from receiver
		jjk  02/19/98'''
		rdl = [chr(self.version), 
			chr(self.year-1900), 
			chr(self.month),
			chr(self.day), 
			binnum.unsigned_as_Intel4(self.recordCount),
			binnum.unsigned_as_Intel2(self.headerLength),
			binnum.unsigned_as_Intel2(self.recordLength),
			20*chr(0)]
		return(string.joinfields(rdl,''))

	def reportOn(self, outs=sys.stdout, indent=0):
		'''Public: report info about the receiver
		jjk  02/18/98'''
		inds = indent*'\t'
		outs.write('%sversion: 0x%x  last update: %d/%d/%d\n'%(inds, self.version,
			self.year,self.month,self.day))
		outs.write('%shdrlen: %d  reclen: %d  reccnt: %d\n'%(inds, self.headerLength,
			self.recordLength,self.recordCount))
		outs.write(inds+' Field Name  Type  Len  Dec\n')
		for fdef in self.fieldDefs:
			fdef.reportOn(outs, indent)

def DbfFieldDefFromRawData(rawFieldDef, startPos):
	'''system: answer an appropriate DbfFieldDef decoded
	from the raw definition
	jjk  02/18/98'''
	fType = rawFieldDef[11]
	if (fType=='C'): fd = DbfCharacterFieldDef()
	elif (fType=='N'): fd = DbfNumericFieldDef()
	elif (fType=='L'): fd = DbfLogicalFieldDef()
	elif (fType=='M'): fd = DbfMemoFieldDef()
	elif (fType=='D'): fd = DbfDateFieldDef()
	else: raise ValueError, 'Unknown Field Type: '+fType
	fd.fromRawData(rawFieldDef, startPos)
	return(fd)

class DbfFieldDef:
	'''superclass for field definition classes
	jjk  02/18/98'''

	def __init__(self):
		'''public: initialize the receiver
		jjk  02/18/98'''
		self._reset()

	def _reset(self):
		'''system: reset the receiver data
		jjk  02/18/98'''
		self.name = ''
		dataAddress = 0
		self.length = 0
		self.decimalCount = 0
		self.start = 0
		self.end = 0

	def fromRawData(self, rawFieldDef, startPos):
		'''system: decode dbf field definition from 32-byte raw dbf data
		jjk  02/18/98'''
		self.name = strutil.unzfill(rawFieldDef[:11])
		dataAddress = binnum.unsigned_from_Intel4(rawFieldDef[12:16])
		self.length = ord(rawFieldDef[16])
		self.start = startPos
		self.end = startPos + self.length
		self.decimalCount = ord(rawFieldDef[17])

	def asRawData(self):
		'''system: encode and answer decode dbf field definition 
		as 32-byte raw dbf data
		jjk  02/19/98'''
		rdl = [strutil.padTrailing(self.name, 11, chr(0)), 
			self.typeCode(),
			binnum.unsigned_as_Intel4(0),		#data address
			chr(self.length), 
			chr(self.decimalCount), 
			14*chr(0)]
		return(string.joinfields(rdl,''))

	def reportOn(self, outs=sys.stdout, indent=0):
		'''Public: report info about the receiver
		jjk  02/18/98'''
		outs.write(indent*'\t')
		outs.write('%11s     %1s  %3d  %3d\n'%self.fieldInfo())

	def typeCode(self):
		'''Public: answer one-character type code of the receiver
		jjk  02/18/98'''
		raise NameError, 'typeCode() must be implemented by subclass'

	def fieldInfo(self):
		'''Public: answer tuple of basic info about the receiver
		jjk  02/18/98'''
		return((self.name, self.typeCode(), self.length, self.decimalCount))

	def decodeFromRecord(self, rawrec):
		'''system: decode and answer the field value from rawrec
		jjk  02/20/98'''
		rawval = rawrec[self.start:self.end]
		return(self.decodeValue(rawval))

	def decodeValue(self, rawval):
		'''system: answer field value decoded from raw value string 
		jjk  02/20/98'''
		raise NameError, 'decodeValue() must be implemented by subclass'

	def encodeValue(self, fieldValue):
		'''system: answer raw data string encoded from a field value
		jjk  02/19/98'''
		raise NameError, 'encodeValue() must be implemented by subclass'

	def defaultValue(self):
		'''Public: answer the default value for fields defined by the receiver
		jjk  02/19/98'''
		raise NameError, 'defaultValue() must be implemented by subclass'

class DbfCharacterFieldDef(DbfFieldDef):

	def typeCode(self):
		'''Public: answer one-character type code of the receiver
		jjk  02/18/98'''
		return('C')

	def decodeValue(self, rawval):
		'''system: decode and answer the field value from rawrec
		jjk  02/18/98'''
		return(strutil.stripTrailing(rawval, ' '))

	def defaultValue(self):
		'''Public: answer the default value for fields defined by the receiver
		jjk  02/19/98'''
		return('')

	def encodeValue(self, fieldValue):
		'''system: answer raw data string encoded from a field value
		jjk  02/19/98'''
		rv = str(fieldValue)[:self.length]
		return(strutil.padTrailing(rv, self.length))

class DbfNumericFieldDef(DbfFieldDef):

	def typeCode(self):
		'''Public: answer one-character type code of the receiver
		jjk  02/18/98'''
		return('N')

	def decodeValue(self, rawval):
		'''system: decode and answer the field value from rawrec
		jjk  06/08/98'''
		if (self.decimalCount == 0):
			rawval = string.strip(rawval)
			if (rawval==''): return(0)
			''' patch from 
			Steve Jibson <stevej@arcos.parlant.com> '''
			try: return(string.atoi(rawval))
			except ValueError:
				return(string.atol(rawval))
		if (string.find(rawval, '.')<0):
			rv1 = rawval[:-self.decimalCount]
			rv2 = rawval[-self.decimalCount:]
			rawval = string.strip(rv1+'.'+rv2)
			if (rawval=='.'): return(0.0)
		return string.atof(rawval)

	def defaultValue(self):
		'''Public: answer the default value for fields defined by the receiver
		jjk  02/19/98'''
		return(0)

	def encodeValue(self, fieldValue):
		'''system: answer raw data string encoded from a field value
		jjk  08/24/98'''
		fl = self.length
		# excel and arcview say, there is a point! (fiby)
		#if (self.decimalCount>0):
		#	fl = fl + 1
		fmt = '%%%d.%df'%(fl,self.decimalCount)
		rv = fmt%fieldValue
		# excel and arcview say, there is a point! (fiby)
		#if (self.decimalCount>0): 
		#	p1 = self.length-self.decimalCount
		#	rv = rv[:p1] + "." + rv[p1+1:]
		return(rv)

class DbfLogicalFieldDef(DbfFieldDef):

	def typeCode(self):
		'''Public: answer one-character type code of the receiver
		jjk  02/18/98'''
		return('L')

	def decodeValue(self, rawval):
		'''system: decode and answer the field value from rawrec
			(1 for true, 0 for false, -1 for dont know)
		jjk  02/18/98'''
		if (rawval=='?'): return(-1)
		if (rawval in 'YyTt'): return(1)
		if (rawval in 'NnFf'): return(0)
		raise ValueError, 'invalid logical value: '+rawval

	def defaultValue(self):
		'''Public: answer the default value for fields defined by the receiver
		jjk  02/19/98'''
		return(-1)

	def encodeValue(self, fieldValue):
		'''system: answer raw data string encoded from a field value
		jjk  08/24/98'''
		if (fieldValue==-1): return('?')
		if (fieldValue==1): return('T')
		else: return('F')

class DbfMemoFieldDef(DbfFieldDef):

	def typeCode(self):
		'''Public: answer one-character type code of the receiver
		jjk  02/18/98'''
		return('M')

	def decodeValue(self, rawval):
		'''system: answer .dbt block number
		jjk  02/18/98'''
		try:
			return(string.atoi(string.strip(rawval)))
		except ValueError:
			return(string.atol(string.strip(rawval)))

	def defaultValue(self):
		'''Public: answer the default value for fields defined by the receiver
		jjk  02/19/98'''
		return(0)

	def encodeValue(self, fieldValue):
		'''system: answer raw data string encoded from a field value
		jjk  02/19/98'''
		rv = str(fieldValue)[:self.length]
		return(strutil.padTrailing(rv, self.length))

class DbfDateFieldDef(DbfFieldDef):

	def typeCode(self):
		'''Public: answer one-character type code of the receiver
		jjk  02/18/98'''
		return('D')

	def decodeValue(self, rawval):
		'''system: answer (year, month, day) tuple
		jjk  06/08/98'''
		try: year = string.atoi(rawval[:4])
		except ValueError: year = 0
		try: month = string.atoi(rawval[4:6])
		except ValueError: month = 0
		try: day = string.atoi(rawval[6:])
		except ValueError: day = 0
		return((year,month,day))

	def defaultValue(self):
		'''Public: answer the default value for fields defined by the receiver
		jjk  02/19/98'''
		timeA = time.localtime(time.time())
		year = timeA[0]
		month = timeA[1]
		day = timeA[2]
		return((year,month,day))

	def encodeValue(self, fieldValue):
		'''system: answer raw data string encoded from a field value
		jjk  08/24/98'''
		year = fieldValue[0]
		if (year < 50): year = year + 2000
		if (year < 100): year = year + 1900
		ys = str(year)
		ms = ('00'+str(fieldValue[1]))[-2:]
		ds = ('00'+str(fieldValue[2]))[-2:]
		return(ys+ms+ds)

class DbfRecord:
	'''system: a Dbf file record
	jjk  02/18/98'''

	def __init__(self, aDbf):
		'''public: initialize the receiver
		jjk  02/19/98'''
		self.dbf = aDbf
		self._reset()

	def _reset(self):
		'''private: reset the receiver data
		jjk  02/19/98'''
		self.recordIndex = -1
		self.isDeleted = 0
		self.fieldData = []
		for fd in self.dbf.header.fieldDefs:
			self.fieldData.append(fd.defaultValue())

	def store(self):
		'''public: [re]store the receiver in its dbf
		jjk  02/19/98'''
		if (self.recordIndex<0): self.dbf.append(self)
		else: self.dbf[self.recordIndex] = self

	def writeData(self):
		'''system: write the receiver data to its recordIndex
		jjk  02/19/98'''
		if (self.recordIndex<0): 
			raise IndexError, 'Dbf record numbers must be >=0'
		len = self.dbf.header.recordLength
		pos = self.dbf.header.headerLength+(self.recordIndex*len)
		rawData = self.asRawData()
		self.dbf.dbfStream.seek(pos)
		self.dbf.dbfStream.write(rawData)

	def readData(self, recordIndex):
		'''system: read the receiver data from the specified index
		jjk  02/19/98'''
		if (recordIndex<0): 
			raise IndexError, 'Dbf record numbers must be >=0'
		if (recordIndex>=self.dbf.header.recordCount):
			raise IndexError, 'Only '+str(self.dbf.header.recordCount)+' records in Dbf'
		len = self.dbf.header.recordLength
		pos = self.dbf.header.headerLength+(recordIndex*len)
		self.dbf.dbfStream.seek(pos)
		rawData = self.dbf.dbfStream.read(len)
		self.fromRawData(rawData)
		self.recordIndex = recordIndex

	def fromRawData(self, rawDataString):
		'''system: instantiate the receiver from a raw data string
		jjk  02/19/98'''
		self._reset()
		self.isDeleted = (rawDataString[0]=='0x2A')  #del='*'  notDel=' '
		for fieldIx in range(len(self.fieldData)):
			fd = self.dbf.header.fieldDefs[fieldIx]
			self.fieldData[fieldIx] = fd.decodeFromRecord(rawDataString)

	def asRawData(self):
		'''system: answer a raw dbf string generated from the receiver
		jjk  02/19/98'''
		rawFields = []
		if (self.isDeleted): rawFields.append(chr(0x2A))	# '*'
		else: rawFields.append(chr(0x20))	# ' '
		for fieldIx in range(len(self.fieldData)):
			fdef = self.dbf.header.fieldDefs[fieldIx]
			fdat = fdef.encodeValue(self.fieldData[fieldIx])
			rawFields.append(fdat)
		return(string.joinfields(rawFields,''))

	def asList(self):
		'''Public: answer a list of receiver's fields
		jjk  02/18/98'''
		return(self.fieldData)

	def asDict(self):
		'''Public: answer a dictionary of receiver's fields
		jjk  02/19/98'''
		dict = {}
		for fldName in self.dbf.fieldNames():
			dict[fldName] = self[fldName]
		return(dict)

	def __getitem__(self, fieldName):
		'''public: answer the value for specified field in the receiver
		jjk  02/13/98'''
		fldIx = self.dbf.indexOfFieldName(fieldName)
		return(self.fieldData[fldIx])

	def __setitem__(self, fieldName, fieldValue):
		'''public: set the value for specified field in the receiver
		jjk  02/13/98'''
		fldIx = self.dbf.indexOfFieldName(fieldName)
		self.fieldData[fldIx] = fieldValue
			
def demo1():
	dbf1 = Dbf()
	dbf1.openFile('county.dbf', readOnly=1)
	dbf1.reportOn()
	print 'sample records:'
	for i1 in range(min(3,len(dbf1))):
		rec = dbf1[i1]
		for fldName in dbf1.fieldNames():
			print '%s:\t %s'%(fldName, rec[fldName])
		print
	dbf1.close()

if (__name__=='__main__'):
	import pdb
	demo1()

