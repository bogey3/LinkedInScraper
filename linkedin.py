#!/usr/bin/python3
import datetime
import requests
import sys
import json
import getpass

class linkedInClient():
	def __init__(self):
		self.session = requests.session()
		self.outFile = ""
		self.apiHeaders = {
			"X-Li-User-Agent": "LIAuthLibrary:3.2.4 com.linkedin.LinkedIn:8.8.1 iPhone:8.3",
			"User-Agent": "LinkedIn/8.8.1 CFNetwork/711.3.18 Darwin/14.0.0",
			"X-User-Language": "en",
			"X-User-Locale": "en_US",
			"Accept-Language": "en-us",
			"x-restli-protocol-version": "2.0.0"
		}

	def login(self, username, password):
		self.username = username
		self.password = password
		URL = "https://www.linkedin.com/uas/authenticate"
		self.session.get(URL, headers=self.apiHeaders)
		cookies = self.session.cookies.get_dict()
		self.apiHeaders["Csrf-Token"] = cookies["JSESSIONID"][1:-1]
		postParameters = {
			"session_key": self.username,
			"session_password": self.password,
			"JSESSIONID": cookies["JSESSIONID"]
		}
		response = self.session.post(URL, data=postParameters, headers=self.apiHeaders)

		if json.loads(response.text)["login_result"] == "PASS":
			return True
		return False

	def scrapeCompany(self, companyID):
		baseURL = f"https://www.linkedin.com/voyager/api/search/cluster?guides=List(v->PEOPLE,facetCurrentCompany->{companyID})&origin=OTHER&q=guided"
		increase = 49
		total = 1
		offset = 0
		employees = []
		while offset < total:
			url = baseURL + f"&count={increase}&start={offset}"
			response = self.session.get(url, headers=self.apiHeaders)
			data = json.loads(response.text)
			if data["elements"]:
				company = data["elements"][0]
				total = company["total"]
			for person in company["elements"]:
				data = person["hitInfo"]["com.linkedin.voyager.search.SearchProfile"]["miniProfile"]
				if data["firstName"] != "" or data["lastName"] != "":
					location = ""
					if "hitInfo" in person and "com.linkedin.voyager.search.SearchProfile" in person["hitInfo"] and "location" in person["hitInfo"]["com.linkedin.voyager.search.SearchProfile"]:
						location = person["hitInfo"]["com.linkedin.voyager.search.SearchProfile"]["location"]
					else:
						location = "Unknown"
					employees.append([data['firstName'], data['lastName'], data['occupation'], location])
					if self.outFile:
						with open(arguments["outfile"], "a", encoding='utf8') as f:
							f.write('"' + '","'.join(employees[-1]) + '"\n')
				else:
					pass
			offset += increase
		return employees

	def scrapeSearch(self, searchTerm):
		baseURL = f"https://www.linkedin.com/voyager/api/voyagerSearchBlendedSearchClusters?filters=List(resultType->PEOPLE)&keywords=\"{searchTerm}\"&origin=GLOBAL_SEARCH_HEADER&q=all&queryContext=List(kcardTypes-%3ECCOMPANY%7CJOB_TITLE)"
		increase = 49
		total = 1
		offset = 0
		employees = []
		while offset < total:
			url = baseURL + f"&count={increase}&start={offset}"
			offset += increase
			response = json.loads(self.session.get(url, headers=self.apiHeaders).text)
			total = response["paging"]["total"]
			if len(response["elements"]):
				people = response["elements"][0]
				for person in people["elements"]:
					miniProfile = person["image"]["attributes"][0]["miniProfile"]
					if miniProfile["firstName"] != "" or miniProfile["lastName"] != "":
						employees.append([miniProfile['firstName'], miniProfile['lastName'], miniProfile['occupation'], person["subline"]["text"]])
						if self.outFile:
							with open(arguments["outfile"], "a", encoding='utf8') as f:
								f.write('"' + '","'.join(employees[-1]) + '"\n')
		return employees

def usage():
	print(f"""LinkedIn Scraper
	
	Required:
	\t-u\t\tUsername for logging in
	
	Pick One:
	\t-c\t\tThe company ID to scrape
	\t-s\t\tThe search term to use for scraping
	
	Optional:
	\t-o\t\tThe CSV file to write results to
	\t-p\t\tPassword for logging in
	
	Example Usage:
	\t{sys.argv[0]} -u user@email.com -p Password1 -c 1234567 -o ./output.csv
	\t{sys.argv[0]} -u user@email.com -p Password1 -s "Company Name Inc." -o ./output.csv
	\t{sys.argv[0]} -u user@email.com -p Password1 -s "Company Name Inc."
	""")
	sys.exit(0)

def parseArgs():
	out = {}
	required = {"-u":"username"}
	oneOf = {"-c":"company", "-s":"search"}
	optional = {"-o":"outfile", "-p":"password"}
	for item in required:
		if item in sys.argv:
			out[required[item]] = sys.argv[sys.argv.index(item)+1]
		else:
			usage()
	count = 0
	for item in oneOf:
		if item in sys.argv:
			count +=1
			out[oneOf[item]] = sys.argv[sys.argv.index(item) + 1]

	for item in optional:
		if item in sys.argv:
			out[optional[item]] = sys.argv[sys.argv.index(item) + 1]

	while "password" not in out or out["password"] == "":
		out["password"] = getpass.getpass(prompt='Enter Password: ', stream=None)

	if count != 1 :
		usage()
	else:
		return(out)

if __name__ == '__main__':
	client = linkedInClient()
	arguments = parseArgs()
	employees = []
	while not client.login(arguments["username"], arguments["password"]):
		print("Login attempt failed, please enter your LinkedIn Credentials")
		# Default to already submitted username if not provided
		arguments["username"] = input(f"Username [{arguments['username']}]: ") or arguments["username"]
		arguments["password"] = getpass.getpass(prompt='Password: ', stream=None)

	if "company" in arguments or "search" in arguments:
		if "outfile" in arguments:
			with open(arguments["outfile"], "a", encoding='utf8') as f:
				f.write('"First Name","Last Name","Headline","Location"\n')
			client.outFile = arguments["outfile"]
		if "company" in arguments:
			employees = client.scrapeCompany(arguments["company"])
		elif "search" in arguments:
			employees = client.scrapeSearch(arguments["search"])
	else:
		usage()



	lengths = [10, 9, 8, 8]

	day = datetime.date.today()
	with open(f"employees-{day.strftime('%Y-%m-%d')}.json", "w") as f:
		f.write(json.dumps(employees))

	for employee in employees:
		for i in range(len(employee)):
			if lengths[i] < len(employee[i]):
				lengths[i] = len(employee[i])
	lengths = list(map(str, lengths))
	outFormat = "{:<" + lengths[0] + "} | {:<" + lengths[1] + "} | {:<" + lengths[2] + "} | {:<" + lengths[3] + "}"
	header = outFormat.format("First Name", "Last Name", "Headline", "Location")
	print(header)
	print("="*len(header))
	for employee in employees:
		print(outFormat.format(employee[0], employee[1], employee[2], employee[3]))

