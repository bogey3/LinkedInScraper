# LinkedIn Scraper
I know it's not a very creative name, but it sure is descriptive.

## How it works
This script scrapes employees from linkedin pages using either the company ID, or by searching the company name. It accomplishes this by emulating API calls made by the LinkedIn app on iOS.

## How to use it
Running the script with no parameters, or incorrect parameters will result in the following instructions:
```
LinkedIn Scraper

        Required:
                -u              Username for logging in

        Pick One:
                -c              The company ID to scrape
                -s              The search term to use for scraping

        Optional:
                -o              The CSV file to write results to
                -p              Password for logging in

        Example Usage:
                .\linkedin.py -u user@email.com -p Password1 -c 1234567 -o ./output.csv
                .\linkedin.py -u user@email.com -p Password1 -s "Company Name Inc." -o ./output.csv
                .\linkedin.py -u user@email.com -s "Company Name Inc."
```
If you do not include a password argument, you will be prompted for the account's password.

## Output
Console output will appear as below, you can also use the `-o` flag to output to a CSV file. 
```
First Name      | Last Name         | Headline                                                                                                | Location                                     
=============================================================================================================================================================================================
Name            | Removed           | CEO                                                                                                     | Greater Chicago Area                         
Name            | Removed           | Growth-focused CMO & GM                                                                                 | San Francisco Bay Area                       
Name            | Removed           | Recruiting Manager                                                                                      | Norfolk, Virginia Area                       
Name            | Removed           | Founder                                                                                                 | Other                                        
Name            | Removed           | Customer Success executive & team leader passionate about growing mission-driven, technology businesses | San Francisco Bay Area                       
Name            | Removed           | Engineering                                                                                             | Greater Los Angeles Area                     
Name            | Removed           | Principal                                                                                               | Greater Boston Area                          
Name            | Removed           | Account Manager                                                                                         | Greater New York City Area                   
Name            | Removed           | Senior Director, Human Resources                                                                        | Greater New York City Area                   
Name            | Removed           | Experienced content creator and product marketing manager                                               | Dallas/Fort Worth Area                       
Name            | Removed           | Director of Software Engineering                                                                        | Greater Philadelphia Area                    
Name            | Removed           | Student Success Advisor                                                                                 | Tampa/St. Petersburg, Florida Area           
Name            | Removed           | B2B Marketing Manager                                                                                   | Albany, New York Area                        
Name            | Removed           | Project Editor                                                                                          | Albany, New York Area                        

```