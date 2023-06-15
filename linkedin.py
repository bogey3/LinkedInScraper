#!/usr/bin/python3
import datetime
import requests
import sys
import json
import getpass
import os
from http import cookiejar


class linkedInClient():
    def __init__(self):
        self.cookieJarFile = os.path.dirname(os.path.abspath(__file__)) + str(os.sep) + "linkedin-cookies.cookies"
        self.session = requests.session()
        self.jar = cookiejar.LWPCookieJar(filename=self.cookieJarFile)
        self.jar.load(self.cookieJarFile)
        self.session.cookies = self.jar
        self.outFile = ""
        self.apiHeaders = {
            "X-Li-User-Agent": "LIAuthLibrary:3.2.4 com.linkedin.LinkedIn:8.8.1 iPhone:8.3",
            "User-Agent": "LinkedIn/8.8.1 CFNetwork/711.3.18 Darwin/14.0.0",
            "X-User-Language": "en",
            "X-User-Locale": "en_US",
            "Accept-Language": "en-us",
            "x-restli-protocol-version": "2.0.0",
        }
        cookies = requests.utils.dict_from_cookiejar(self.session.cookies)
        if "JSESSIONID" in cookies:
            self.apiHeaders["Csrf-Token"] = cookies["JSESSIONID"][1:-1]

    def checkLoggedIn(self):
        URL = "https://www.linkedin.com/voyager/api/voyagerMe"
        resp = self.session.get(URL, headers=self.apiHeaders)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            print(f"Reusing session, logged in as {data['miniProfile']['firstName']} {data['miniProfile']['lastName']}")
        self.session.cookies.save()
        return resp.status_code == 200

    def login(self, username, password):
        print("Logging in")
        self.username = username
        self.password = password
        URL = "https://www.linkedin.com/uas/authenticate"
        self.session.get(URL, headers=self.apiHeaders)
        postParameters = {
            "session_key": self.username,
            "session_password": self.password,
            "JSESSIONID": requests.utils.dict_from_cookiejar(self.session.cookies)["JSESSIONID"]
        }
        response = self.session.post(URL, data=postParameters, headers=self.apiHeaders)


        self.session.cookies.save()

        if json.loads(response.text)["login_result"] == "PASS":
            print("Login succeeded")
            return True
        print("Login failed")
        return False



    def scrapeCompany(self, companyID):
        increase = 50
        total = 1
        offset = 0
        self.apiHeaders["X-Li-Graphql-Pegasus-Client"] = "true"

        employees = []
        while offset < total:
            URL = f"https://www.linkedin.com:443/voyager/api/graphql?queryId=voyagerSearchDashClusters.8883e32cfbde6e9879cab4622bf735a6&queryName=SearchClusterCollection&variables=(query:(queryParameters:(currentCompany:List({companyID}),resultType:List(PEOPLE)),flagshipSearchIntent:SEARCH_SRP,includeFiltersInResponse:false),count:{increase},origin:COMPANY_PAGE_CANNED_SEARCH,start:{offset})"
            response = self.session.get(URL, headers=self.apiHeaders)
            data = json.loads(response.text)
            data = data["data"]['searchDashClustersByAll']
            total = data["paging"]["total"]
            users = []
            for list in data["elements"]:
                if len(list["items"]) > 0 and "item" in list["items"][0] and "entityResult" in list["items"][0]["item"]:
                    users = list["items"]
                    break
            #users = data["elements"][1]["items"]

            for user in users:
                name = user["item"]["entityResult"]["title"]["text"]
                if name == 'LinkedIn Member':
                    continue
                tagline = user['item']['entityResult']['primarySubtitle']['text']
                location = user['item']['entityResult']['secondarySubtitle']['text']
                employees.append([name, tagline, location])
                if self.outFile:
                    with open(arguments["outfile"], "a", encoding='utf8') as f:
                        f.write('"' + '","'.join(employees[-1]) + '"\n')
            offset += increase
        return employees


def usage():
    print(f"""LinkedIn Scraper

	Required:
	\t-c\t\tThe company ID to scrape

	Optional:
	\t-o\t\tThe CSV file to write results to
	\t-u\t\tUsername for logging in
	\t-p\t\tPassword for logging in
	\t--clear\t\tClear the stored cookies and force reauthentication

    A username an password will be required if the stored cookies have expired, or if this is your first time running this script.

	Example Usage:
	\t{sys.argv[0]} -u user@email.com -p Password1 -c 1234567 -o ./output.csv
	""")
    sys.exit(0)


def parseArgs():
    out = {}
    required = {"-c": "company"}
    optional = {"-u": "username", "-o": "outfile", "-p": "password"}
    if "--clear" in sys.argv:
        out["clear"] = True

    for item in required:
        if item in sys.argv:
            out[required[item]] = sys.argv[sys.argv.index(item) + 1]
        else:
            usage()

    for item in optional:
        if item in sys.argv:
            out[optional[item]] = sys.argv[sys.argv.index(item) + 1]

    return (out)


if __name__ == '__main__':
    client = linkedInClient()
    arguments = parseArgs()
    if "clear" in arguments:
        client.session.cookies.clear()
    employees = []
    if not client.checkLoggedIn():
        if "username" not in arguments:
            arguments["username"] = input(f"Username [{arguments['username']}]: ")
            arguments["password"] = getpass.getpass(prompt='Password: ', stream=None)
        while not client.login(arguments["username"], arguments["password"]):
            print("Login attempt failed, please enter your LinkedIn Credentials")
            # Default to already submitted username if not provided
            arguments["username"] = input(f"Username [{arguments['username']}]: ")
            arguments["password"] = getpass.getpass(prompt='Password: ', stream=None)

    if "company" in arguments or "search" in arguments:
        if "outfile" in arguments:
            with open(arguments["outfile"], "a", encoding='utf8') as f:
                f.write('"Name","Headline","Location"\n')
            client.outFile = arguments["outfile"]
        if "company" in arguments:
            employees = client.scrapeCompany(arguments["company"])
    else:
        usage()

    lengths = [19, 8, 8]

    day = datetime.date.today()
    with open(f"employees-{day.strftime('%Y-%m-%d')}.json", "w") as f:
        f.write(json.dumps(employees))

    for employee in employees:
        for i in range(len(employee)):
            if lengths[i] < len(employee[i])+1:
                lengths[i] = len(employee[i])+1
    lengths = list(map(str, lengths))
    outFormat = "{:<" + lengths[0] + "} | {:<" + lengths[1] + "} | {:<" + lengths[2] + "}"
    header = outFormat.format("Name", "Headline", "Location")
    print("\n" + header)
    print("=" * len(header))
    for employee in employees:
        print(outFormat.format(employee[0], employee[1], employee[2]))
