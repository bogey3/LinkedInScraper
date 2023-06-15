# LinkedIn Scraper
I know it's not a very creative name, but it sure is descriptive.

## How it works
This script scrapes employees from linkedin pages using either the company ID, or by searching the company name. It accomplishes this by emulating API calls made by the LinkedIn app on iOS.

## How to use it
Running the script with no parameters, or incorrect parameters will result in the following instructions:
```
LinkedIn Scraper

        Required:
                -c              The company ID to scrape

        Optional:
                -o              The CSV file to write results to
                -u              Username for logging in
                -p              Password for logging in
                --clear         Clear the stored cookies and force reauthentication

    A username an password will be required if the stored cookies have expired, or if this is your first time running this script.

        Example Usage:
                .\linkedin.py -u user@email.com -p Password1 -c 1234567 -o ./output.csv
```

If you do not include a username or password argument and you don't already have a valid cookie, you will be prompted for the account's credentials.

## Output
Console output will appear as below, you can also use the `-o` flag to output to a CSV file. 
```
Name           | Headline                                                                                                | Location                                     
========================================================================================================================================================================
Name           | CEO                                                                                                     | Greater Chicago Area                         
Name           | Growth-focused CMO & GM                                                                                 | San Francisco Bay Area                       
Name           | Recruiting Manager                                                                                      | Norfolk, Virginia Area                       
Name           | Founder                                                                                                 | Other                                        
Name           | Customer Success executive & team leader passionate about growing mission-driven, technology businesses | San Francisco Bay Area                       
Name           | Engineering                                                                                             | Greater Los Angeles Area                     
Name           | Principal                                                                                               | Greater Boston Area                          
Name           | Account Manager                                                                                         | Greater New York City Area                   
Name           | Senior Director, Human Resources                                                                        | Greater New York City Area                   
Name           | Experienced content creator and product marketing manager                                               | Dallas/Fort Worth Area                       
Name           | Director of Software Engineering                                                                        | Greater Philadelphia Area                    
Name           | Student Success Advisor                                                                                 | Tampa/St. Petersburg, Florida Area           
Name           | B2B Marketing Manager                                                                                   | Albany, New York Area                        
Name           | Project Editor                                                                                          | Albany, New York Area                        

```
