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

TodaysDate = date.today()		# holds today's date
ErrorCode = 0					# holds current error code, modified in errorMessage()

# parse the date entered by the user into a datetime data type
def parseDate(Date):
	global TodaysDate
	rDate = []
	if '/' in Date:
		strDate = str(Date)
		# parse the / out of the date and return it in a list
		lDate = re.findall(r'\d+', strDate)
		# check if date is valid
		if len(lDate) >=2 and int(lDate[0]) <=12 and int(lDate[1]) <=31:
			# if date has a year
			if len(lDate) == 3:
				# if the date's year is in format YY
				if int(lDate[2]) < 100:
					# format the year to YYYY
					lDate[2] = int(lDate[2]) + 2000
				rDate.append(date(int(lDate[2]), int(lDate[0]), int(lDate[1])))	
				return rDate
			# if the date does not have a year, use current year
			elif len(lDate) == 2:
				rDate.append(date(TodaysDate.year, int(lDate[0]), int(lDate[1])))
				return rDate
			# if no date was entered, use current date
			else:
				rDate.append(TodaysDate)
				return rDate
		# if the date entered was invalid, return error message
		else:
			global ErrorCode
			ErrorCode = 1
			return -100
	# if a dateCode was entered such as 5F
	else:
		return dateCode(Date)

# set the global variable TodaysDate with the current date
def setTodaysDate():
	global TodaysDate
	lTime = re.findall(r'\d+', time.strftime('%X'))
	if int(lTime[0]) < 7:
		TodaysDate = TodaysDate.fromordinal(TodaysDate.toordinal() -1)

setTodaysDate()

# handler for http requests for the main page
class Main(webapp.RequestHandler):
	# handles get requests
	def get(self):
		userAgent = str(self.request.headers['User-Agent'])
		# if the get request comes from an iphone or android mobile device
		if "iPhone" in userAgent or "Android" in userAgent:
			# get entries from the data base
			(past, today, future, todo) = getEntries()
			# check error messages
			errorMsg = errorMessage()
			env = Environment(loader = FileSystemLoader(template_dirs))
			template_name = 'mobile.html'
			try:
				template = env.get_template(template_name)
			except TemplateNotFound:
				raise TemplateNotFound(template_name)
			# pass data base entries into template
			content = template.render({'past': past, 'today': today, 'future': future, 'todo': todo, 'errorMsg':errorMsg })
			self.response.out.write(content)
		# handles get request not from a mobile request
		else:
			# get entries from the data base
			(past, today, future, todo) = getEntries()
			# check error messages
			errorMsg = errorMessage()
			env = Environment(loader = FileSystemLoader(template_dirs))
			template_name = 'desktop.html'
			try:
				template = env.get_template(template_name)
			except TemplateNotFound:
				raise TemplateNotFound(template_name)
			# pass data base entries into template
			content = template.render({'past': past, 'today': today, 'future': future, 'todo': todo, 'errorMsg':errorMsg})
			self.response.out.write(content)
	# handles post http requests
	def post(self):
		# if strike through button was pressed, sets variable with the data base entry key
		strikeKey = self.request.get('entryKey')
		# if delete button was pressed, sets variable with the data base entry key
		delKey = self.request.get('deleteKey')
		if strikeKey:
			update(strikeKey)
		# if the user added an entry
		elif self.request.get('add'):
			insert(self.request.get('raw_date'), self.request.get('raw_entry'))
		elif delKey:
			delete(delKey)
		self.redirect('/')

# handler for http requests for the about page
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

# handler for http requests for the about page
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

# data base template
class Entries(db.Model):
	text = db.StringProperty(required=True)
	entry_date = db.DateProperty()
	print_date = db.StringProperty()
	dotw = db.StringProperty()
	struck = db.BooleanProperty()
	milTime = db.IntegerProperty()
	print_time = db.StringProperty()
	who = db.StringProperty(required=True)

# insert date base entry
def insert(raw_date, raw_entry):
	global ErrorCode
	# get current user from google system
	user = users.get_current_user()
	# if entry is not empty, process and store data
	if raw_entry != "":
		# process time and text entry
		listText = parseTime(raw_entry)
		# process date entry
		listDate = parseDate(raw_date)
		# remove the time from the text
		txtList = textSplit(listText)
	# if entry was empty, present error message
	else:
		ErrorCode = 4
	# if there was no error, insert entry into the data base
	if ErrorCode == 0:
		# loop to handle multiple text entries at once
		for j in range(0,len(txtList)):
			# loop to handle multiple date entries at once
			for i in range(0,len(listDate)):
				# inserts entries into data base
				entries = Entries(	text=txtList[j], 
									entry_date = listDate[i],
									print_date = prtDate(listDate[i]),
									dotw = dayOfTheWeek(listDate[i]),
									struck = False,
									milTime = listText[0],
									print_time = str(listText[2]),
									who=user.user_id()					) 
				entries.put()

# retrive entries from data base
def getEntries():
	past = []		# entries dated in the past
	today = []		# today's entries
	future = []		# entries dated in the future
	todo = []		# todo list
	cur_user = users.get_current_user()
	user = cur_user.user_id()
	global TodaysDate
	# get the users entries from the data base ordered by entry date and time
	entries = db.GqlQuery('SELECT * FROM Entries WHERE who=:1 ORDER BY entry_date ASC, milTime ASC', user)
	# sort the entries into appropriate lists
	for e in entries:
		e.key=e.key()
		if e.entry_date < TodaysDate:
			past.append(e)
		# append entry to today if it has a time and date is today's date
		elif e.entry_date == TodaysDate and e.milTime != 0:
			today.append(e)
		elif e.entry_date > TodaysDate:
			future.append(e)
		# append entry to todo if it is dated today or past, and does not have a time, and has not been struck through
		if (e.entry_date == TodaysDate and e.milTime ==0) or (e.entry_date < TodaysDate and e.milTime ==0 and e.struck==False):
			todo.append(e)
	return (past, today, future, todo)

# if strike through button is pressed, toggle strike through
def update(ikey):
	try:
		entry = db.get(ikey)
		# toggle strike through
		if entry.struck == True:
			entry.struck = False
		else:
			entry.struck = True
		entry.put()
	# error message if entry was previously deleted
	except:
		global ErrorCode
		ErrorCode = 5

# delete entry associated to the given key
def delete(key):
	try:
		db.delete(key)
	# error message if entry was previously deleted
	except:
		global ErrorCode
		ErrorCode = 5
# parses the time from the raw entry and returns a list with 
# the time in military formate, print ready format, and the text of the entry
def parseTime(text):
	strText = str(text)
	returnList = [0, 0, 0]
	global ErrorCode
	# check if there is a time on the entry
	if str(strText[0]).isdigit():
		# split the time from the text
		i = strText.find(' ')
		if i >= 0:
			textTime = strText[0:i]
			textText = strText[i+1:len(strText)]
		# error message if there was no space after the time entered
		else:
			ErrorCode = 3
			textTime = '0'
			textText = '0'
	# return text if there is no time
	else:
		returnList[1] = strText
		return returnList
	# if am or pm was entered
	if 'p' in textTime or 'P' in textTime or 'a' in textTime or 'A' in textTime:
		ugTime = signedTime(textTime)
	# if am or pm was not entered
	else:
		textTime = oneNum(textTime)
		ugTime = unsignedTime(textTime)
	returnList[0] = ugTime
	returnList[1] = textText
	returnList[2] = prtTime(ugTime)
	return returnList

# return appropriate military time if am or pm was assisgned by the user
def signedTime(strTime):
	i = strTime.find(':')
	# if there is a colon in the time, create military time
	if i >= 0:
		# remove hour digits of time, multiply them by 100 and add minute digites
		if 'a' in strTime or 'A' in strTime:
			intTime = int(strTime[0:i])
			return (intTime*100)+int(strTime[i+1:i+3])
		# remove hour digits of time, multiply them by 100 and add minute digites and add 1200
		else:
			intTime = int(strTime[0:i])
			return (intTime*100)+int(strTime[i+1:i+3])+1200
	# if there is not a colon in the time, create military time
	# find a or p, then adjust time to military time
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

# returns appropriate military time if am or pm was not assigned
def unsignedTime(strTime):
	i = strTime.find(':')
	# if there is a colon in the time, remove it
	if i >= 0:
		intTime = int(strTime[0:i])
		intTime = (intTime*100)+int(strTime[i+1:len(strTime)])
	else:
		intTime = int(strTime)
	# adjust time for am or pm, add 1200 to time after 1259
	if intTime < 1300 and intTime >= 800:
		return intTime
	else:
		return intTime+1200

# create time in a ready to print format
def prtTime(uTime):
	# if time is am, seperate hours, minutes, and add am
	if uTime < 1200:
		hours = (uTime/100)
		minutes = uTime-((uTime/100)*100)
		# if the minutes are signal digit add a zero before it
		if minutes < 10:
			return ("%s:0%s %s") %(hours, minutes, "AM")
		else:
			return ("%s:%s %s") %(hours, minutes, "AM")
	# if time is during the hour 12, seperate hours, minutes, and add pm
	elif uTime >=1200 and uTime < 1300:
		hours = (uTime/100)
		minutes = uTime-((uTime/100)*100)
		# if the minutes are signal digit add a zero before it
		if minutes < 10:
			return ("%s:0%s %s") %(hours, minutes, "PM")
		else:
			return ("%s:%s %s") %(hours, minutes, "PM")
	# if time is pm, seperate hours, minutes, and add pm
	else:
		hours = (uTime/100) - 12
		minutes = uTime-((uTime/100)*100)
		# if the minutes are signal digit add a zero before it
		if minutes < 10:
			return ("%s:0%s %s") %(hours, minutes, "PM")
		else:
			return ("%s:%s %s") %(hours, minutes, "PM")

# used if the time is only in hours and returns the time with hours and minutes
def oneNum(textTime):
	# if the time is one digit, append two zeros
	if len(textTime) == 1:
		return ("%s00") %(textTime)
	# if the time is two digits, append two zeros
	elif len(textTime) == 2 and textTime[1].isdigit():
		return ("%s00") %(textTime)
	else:
		return textTime

# if a dateCode was entered, such as 5F, returns list of dates
def dateCode(iDate):
	rDate = []
	Date = iDate.upper()
	global TodaysDate
	# if a single letter code is entered, return the associated date
	if len(Date) == 1:
		code = codeToNum(Date)
		fDate = date.fromordinal(TodaysDate.toordinal() + code)
		rDate.append(fDate)
		return rDate
	# if a code for a next week date is entered, returns associated date
	elif Date[0:1] == 'N':
		code = codeToNum(Date[1:2])
		code += 7
		fDate = date.fromordinal(TodaysDate.toordinal() + code)
		rDate.append(fDate)
		return rDate
	# if a code for multiple dates is entered, returns associated dates
	elif Date[0:1].isdigit():
		lNum = re.findall(r'\d+', Date)
		iNum = int(lNum[0])
		# if code is two digits
		if iNum>=10:
			code = codeToNum(Date[2:3])
		# if code is a single digit
		else:
			code = codeToNum(Date[1:2])
		fDate = date.fromordinal(TodaysDate.toordinal() + code)
		rDate.append(fDate)
		# append dates for day of each week for the number of weeks designated
		for i in range(1,iNum):
			code += 7
			fDate = date.fromordinal(TodaysDate.toordinal() + code)
			rDate.append(fDate)
		return rDate

# returns number associated with the code entered
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
	# error message if code is invalid
	else:
		global ErrorCode
		ErrorCode = 1
		return -100

# creates print ready date with name of the month
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

# retuns the name of the day of the week
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

# splits the text if multiple entries were entered at once
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

# returns appropriate error message for given error code and resets the global variable to 0
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