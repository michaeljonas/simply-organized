#!/user/bin/env python

import wsgiref.handlers
from google.appengine.ext import db	
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.api import users
import sys
from datetime import date
import re, os, time

from jinja2 import Environment, FileSystemLoader, TemplateNotFound
template_dirs = []
template_dirs.append(os.path.join(os.path.dirname(__file__), 'templates'))

TodaysDate = date.today()
ErrorCode = 0

def parseDate(Date):
	global TodaysDate
	rDate = []
	if '/' in Date:
		strDate = str(Date)
		lDate = re.findall(r'\d+', strDate)
		if len(lDate) >=2 and int(lDate[0]) <=12 and int(lDate[1]) <=31:		
			if len(lDate) == 3:
				if int(lDate[2]) < 100:
					lDate[2] = int(lDate[2]) + 2000
				rDate.append(date(int(lDate[2]), int(lDate[0]), int(lDate[1])))
				return rDate
			elif len(lDate) == 2:
				rDate.append(date(TodaysDate.year, int(lDate[0]), int(lDate[1])))
				return rDate
			else:
				rDate.append(TodaysDate)
				return rDate
		else:
			global ErrorCode
			ErrorCode = 1
			return -100
	else:
		return dateCode(Date)

def setTodaysDate():
	global TodaysDate
	lTime = re.findall(r'\d+', time.strftime('%X'))
	if int(lTime[0]) < 7:
		TodaysDate = TodaysDate.fromordinal(TodaysDate.toordinal() -1)

setTodaysDate()

class Main(webapp.RequestHandler):
	def get(self):
		userAgent = str(self.request.headers['User-Agent'])
		if "iPhone" in userAgent or "Android" in userAgent:
			(past, today, future, todo) = getEntries()
			errorMsg = errorMessage()
			env = Environment(loader = FileSystemLoader(template_dirs))
			template_name = 'mobile.html'
			try:
				template = env.get_template(template_name)
			except TemplateNotFound:
				raise TemplateNotFound(template_name)
			content = template.render({'past': past, 'today': today, 'future': future, 'todo': todo, 'errorMsg':errorMsg })
			self.response.out.write(content)
		else:
			(past, today, future, todo) = getEntries()
			errorMsg = errorMessage()
			env = Environment(loader = FileSystemLoader(template_dirs))
			template_name = 'desktop.html'
			try:
				template = env.get_template(template_name)
			except TemplateNotFound:
				raise TemplateNotFound(template_name)
			content = template.render({'past': past, 'today': today, 'future': future, 'todo': todo, 'errorMsg':errorMsg})
			self.response.out.write(content)
	def post(self):
		strikeKey = self.request.get('entryKey')
		delKey = self.request.get('deleteKey')
		if strikeKey:
			update(strikeKey)
		if self.request.get('add'):
			insert(self.request.get('raw_date'), self.request.get('raw_entry'))
		elif delKey:
			delete(delKey)
		self.redirect('/')

class About(webapp.RequestHandler):
	def get(self):
		env = Environment(loader = FileSystemLoader(template_dirs))
		template_name = 'about.html'
		try:
			template = env.get_template(template_name)
		except TemplateNotFound:
			raise TemplateNotFound(template_name)
		content = template.render()
		self.response.out.write(content)

class MobileAbout(webapp.RequestHandler):
	def get(self):
		env = Environment(loader = FileSystemLoader(template_dirs))
		template_name = 'mobileAbout.html'
		try:
			template = env.get_template(template_name)
		except TemplateNotFound:
			raise TemplateNotFound(template_name)
		content = template.render()
		self.response.out.write(content)

class Entries(db.Model):
	text = db.StringProperty(required=True)
	entry_date = db.DateProperty()
	print_date = db.StringProperty()
	dotw = db.StringProperty()
	struck = db.BooleanProperty()
	milTime = db.IntegerProperty()
	print_time = db.StringProperty()
	who = db.StringProperty(required=True)

def insert(raw_date, raw_entry):
	global ErrorCode
	user = users.get_current_user()
	if raw_entry != "":
		listText = parseTime(raw_entry)
		listDate = parseDate(raw_date)
		txtList = textSplit(listText)
	else:
		ErrorCode = 4
	
	if ErrorCode == 0:
		for j in range(0,len(txtList)):
			for i in range(0,len(listDate)):
				entries = Entries(	text=txtList[j], 
									entry_date = listDate[i],
									print_date = prtDate(listDate[i]),
									dotw = dayOfTheWeek(listDate[i]),
									struck = False,
									milTime = listText[0],
									print_time = str(listText[2]),
									who=user.user_id()					) 
				entries.put()

def getEntries():
	past = []
	today = []
	future = []
	todo = []
	cur_user = users.get_current_user()
	user = cur_user.user_id()
	global TodaysDate
	entries = db.GqlQuery('SELECT * FROM Entries WHERE who=:1 ORDER BY entry_date ASC, milTime ASC', user)
	for e in entries:
		e.key=e.key()
		if e.entry_date < TodaysDate:
			past.append(e)
		elif e.entry_date == TodaysDate and e.milTime != 0:
			today.append(e)
		elif e.entry_date > TodaysDate:
			future.append(e)
		if (e.entry_date == TodaysDate and e.milTime ==0) or (e.entry_date < TodaysDate and e.milTime ==0 and e.struck==False):
			todo.append(e)
	return (past, today, future, todo)
	
def update(ikey):
	try:
		entry = db.get(ikey)
		if entry.struck == True:
			entry.struck = False
		else:
			entry.struck = True
		entry.put()
	except:
		global ErrorCode
		ErrorCode = 5

def delete(key):
	try:
		db.delete(key)
	except:
		global ErrorCode
		ErrorCode = 5

def parseTime(text):
	strText = str(text)
	returnList = [0, 0, 0]
	global ErrorCode
	if str(strText[0]).isdigit():
		i = strText.find(' ')
		if i >= 0:
			textTime = strText[0:i]
			textText = strText[i+1:len(strText)]
		else:
			ErrorCode = 3
			textTime = '0'
			textText = '0'
	else:
		returnList[1] = strText
		return returnList
	if 'p' in textTime or 'P' in textTime or 'a' in textTime or 'A' in textTime:
		ugTime = signedTime(textTime)
	else:
		textTime = oneNum(textTime)
		ugTime = unsignedTime(textTime)
	returnList[0] = ugTime
	returnList[1] = textText
	returnList[2] = prtTime(ugTime)
	return returnList

def signedTime(strTime):
	i = strTime.find(':')
	if i >= 0:
		if 'a' in strTime or 'A' in strTime:
			intTime = int(strTime[0:i])
			return (intTime*100)+int(strTime[i+1:i+3])
		else:
			intTime = int(strTime[0:i])
			return (intTime*100)+int(strTime[i+1:i+3])+1200
	else:
		if 'a' in strTime:
			i = strTime.find('a')
			return int(oneNum(strTime[0:i]))
		elif 'A' in strTime:
			i = strTime.find('A')
			return int(oneNum(strTime[0:i]))
		elif 'p' in strTime:
			i = strTime.find('p')
			return int(oneNum(strTime[0:i]))+1200
		else:
			i = strTime.find('P')
			return int(oneNum(strTime[0:i]))+1200

def unsignedTime(strTime):
	i = strTime.find(':')
	if i >= 0:
		intTime = int(strTime[0:i])
		intTime = (intTime*100)+int(strTime[i+1:len(strTime)])
	else:
		intTime = int(strTime)
	if intTime < 1300 and intTime >= 800:
		uglyTime = intTime
		return uglyTime
	else:
		uglyTime = intTime+1200
		return uglyTime

def prtTime(uTime):
	if uTime < 1200:
		hours = (uTime/100)
		minutes = uTime-((uTime/100)*100)
		if minutes < 10:
			return ("%s:0%s %s") %(hours, minutes, "AM")
		else:
			return ("%s:%s %s") %(hours, minutes, "AM")
	elif uTime >=1200 and uTime < 1300:
		hours = (uTime/100)
		minutes = uTime-((uTime/100)*100)
		if minutes < 10:
			return ("%s:0%s %s") %(hours, minutes, "PM")
		else:
			return ("%s:%s %s") %(hours, minutes, "PM")
	else:
		hours = (uTime/100) - 12
		minutes = uTime-((uTime/100)*100)
		if minutes < 10:
			return ("%s:0%s %s") %(hours, minutes, "PM")
		else:
			return ("%s:%s %s") %(hours, minutes, "PM")
		
def oneNum(textTime):
	if len(textTime) == 1:
		return ("%s00") %(textTime)
	elif len(textTime) == 2 and textTime[1].isdigit():
		return ("%s00") %(textTime)
	else:
		return textTime

def dateCode(iDate):
	rDate = []
	Date = iDate.upper()
	global TodaysDate
	if len(Date) == 1:
		code = codeToNum(Date)
		fDate = date.fromordinal(TodaysDate.toordinal() + code)
		rDate.append(fDate)
		return rDate
	elif Date[0:1] == 'N':
		code = codeToNum(Date[1:2])
		code += 7
		fDate = date.fromordinal(TodaysDate.toordinal() + code)
		rDate.append(fDate)
		return rDate
	elif Date[0:1].isdigit():
		lNum = re.findall(r'\d+', Date)
		iNum = int(lNum[0])
		if iNum>=10:
			code = codeToNum(Date[2:3])
		else:
			code = codeToNum(Date[1:2])
		fDate = date.fromordinal(TodaysDate.toordinal() + code)
		rDate.append(fDate)
		for i in range(1,iNum):
			code += 7
			fDate = date.fromordinal(TodaysDate.toordinal() + code)
			rDate.append(fDate)
		return rDate
				
def codeToNum(Date):
	global TodaysDate
	if Date == 'M':
		return int(0 - TodaysDate.weekday())
	elif Date == 'T':
		return int(1 - TodaysDate.weekday())
	elif Date == 'W':
		return int(2 - TodaysDate.weekday())
	elif Date == 'R':
		return int(3 - TodaysDate.weekday())
	elif Date == 'F':
		return int(4 - TodaysDate.weekday())
	elif Date == 'S':
		return int(5 - TodaysDate.weekday())
	elif Date == 'U':
		return int(6 - TodaysDate.weekday())
	else:
		global ErrorCode
		ErrorCode = 1
		return -100

def prtDate(dtDate):
	month = dtDate.month
	if month == 1:
		strMonth = "Jan."
	elif month == 2:
		strMonth = "Feb."
	elif month == 3:
		strMonth = "Mar."
	elif month == 4:
		strMonth = "Apr."
	elif month == 5:
		strMonth = "May"
	elif month == 6:
		strMonth = "Jun."
	elif month == 7:
		strMonth = "Jul."
	elif month == 8:
		strMonth = "Aug."
	elif month == 9:
		strMonth = "Sept."
	elif month == 10:
		strMonth = "Oct."
	elif month == 11:
		strMonth = "Nov."
	else:
		strMonth = "Dec."
	return ("%s %s, %s" %(strMonth, dtDate.day, dtDate.year))

def dayOfTheWeek(dDate):
	intValue = dDate.weekday()
	if intValue == 0:
		dotw = "Mon"
	elif intValue == 1:
		dotw = "Tues"
	elif intValue == 2:
		dotw = "Wed"
	elif intValue == 3:
		dotw = "Thurs"
	elif intValue == 4:
		dotw = "Fri"
	elif intValue == 5:
		dotw = "Sat"
	else:
		dotw = "Sun"		
	return dotw

def textSplit(listText):
	strText = str(listText[1])
	if ";" in strText:
		if strText[len(strText)-1] != ';':
			return strText.split(";")
		else:
			global ErrorCode
			ErrorCode = 2
			rlist = [strText,]
			return rlist
	else:
		rlist = [strText,]
		return rlist

def errorMessage():
	global ErrorCode
	if ErrorCode == 1:
		ErrorCode = 0
		return "Error - Inproper Date Entry, please see the <a href=\"about.html\" class=\"ERROR\">about</a> page for proper formatting of date entries."
	elif ErrorCode == 2:
		ErrorCode = 0
		return "Error - Inproper Text Entry, do not end a text entry with a semicolon(;)"
	elif ErrorCode == 3:
		ErrorCode = 0
		return "Error - Inproper Time Entry, please see the <a href=\"about.html\" class=\"ERROR\">about</a> page for proper formatting of time entries"
	elif ErrorCode == 4:
		ErrorCode = 0
		return "Error - Inproper Time or Text Entry, please see the <a href=\"about.html\" class=\"ERROR\">about</a> page for proper formatting of time & text entries"
	elif ErrorCode == 5:
		ErrorCode = 0
		return "Item does not exists or has been deleted."
	else:
		return " "

def main():
	app = webapp.WSGIApplication([('/', Main), 
								('/about.html', About),
								('/mobileAbout.html', MobileAbout)], 
								debug=False)
	wsgiref.handlers.CGIHandler().run(app)
	
if __name__ == "__main__":
	main()