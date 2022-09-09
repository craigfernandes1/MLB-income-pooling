from collections import OrderedDict
import pandas as pd
import numpy as np
import requests, bs4
import regex as re
import os
import lxml
import time
import seaborn as sns
import matplotlib.pyplot as plt


# %%

def findTables(url):
    res = requests.get(url)
    ## The next two lines get around the issue with comments breaking the parsing.
    comm = re.compile("<!--|-->")
    soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')
    divs = soup.findAll('div', id="content")
    divs = divs[0].findAll("div", id=re.compile("^all"))
    ids = []
    for div in divs:
        searchme = str(div.findAll("table"))
        x = searchme[searchme.find("id=") + 3: searchme.find(">")]
        x = x.replace("\"", "")
        if len(x) > 0:
            ids.append(x)
    return (ids)


def pullTable(url, tableID):
    res = requests.get(url)
    ## Work around comments
    comm = re.compile("<!--|-->")
    soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')
    tables = soup.findAll('table', id=tableID)
    data_rows = tables[0].findAll('tr')
    data_header = tables[0].findAll('thead')
    data_header = data_header[0].findAll("tr")
    data_header = data_header[0].findAll("th")
    game_data = [[td.getText() for td in data_rows[i].findAll(['th', 'td'])]
                 for i in range(len(data_rows))
                 ]
    data = pd.DataFrame(game_data)
    header = []
    for i in range(len(data.columns)):
        header.append(data_header[i].getText())
    data.columns = header
    data = data.loc[data[header[0]] != header[0]]
    data = data.reset_index(drop=True)
    return (data)


def findMinorLeagueTeamsURLS(url):
    res = requests.get(url)
    ## The next two lines get around the issue with comments breaking the parsing.
    comm = re.compile("<!--|-->")
    soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')
    divs = soup.findAll('div', id="content")
    divs = divs[0].findAll("div", id=re.compile("^all"))
    for div in divs:
        table = div.find("table")
        links = table.findAll('a')
        team_urls = []
        for link in links:
            if 'poptip' in str(link):
                link = str(link)
                url = link[link.find("href=") + 6: link.find(">") - 1]
                full_url = "https://www.baseball-reference.com" + url
                team_urls.append(full_url)
    return (team_urls)


def pullMinorURLS(url, tableID):
    res = requests.get(url)
    ## Work around comments
    comm = re.compile("<!--|-->")
    soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')
    table = soup.findAll('table', id=tableID)[0]

    links = table.findAll('a')
    minor_urls = []
    for link in links:
        link = str(link)
        url = link[link.find("href=") + 6: link.find(">") - 1]
        full_url = "https://www.baseball-reference.com" + url
        minor_urls.append(full_url)
    return (minor_urls)


def pullMajorURLS(df):
    major_urls = []

    for url in df.minor_urls:
        res = requests.get(url)
        ## The next two lines get around the issue with comments breaking the parsing.
        comm = re.compile("<!--|-->")
        soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')

        links = soup.findAll('a')

        # Filter for the links that have the 'overview' hyperlink
        link = list(filter(lambda a: 'Overview' in str(a),
                           links))  # only grab the links for the "overview" page and make it a list
        # If link is not empty
        if link:
            link = str(link[0])  # take one of the elements (they're the same) and make it a string
            major_url = link[link.find("href=") + 6: link.find(">") - 1]
        else:
            major_url = '#'  # if it is empty, just add the # sign to the link
        # If a player never made the majors, there is no overview link
        if major_url == '#':
            full_url = 'nan'
        else:
            full_url = "https://www.baseball-reference.com" + major_url
        major_urls.append(full_url)

    return (major_urls)


def pullSalaries(df):
    pd.options.mode.chained_assignment = None
    # Get the Salaries
    inflation_data = 815.5 / np.array(
        [116.7, 121.7, 125.7, 133.4, 148.2, 161.7, 171.0, 182.1, 196.0, 218.1, 247.6, 273.2, 290.0,
         299.3, 312.2, 323.2, 329.4, 341.4, 355.4, 372.5, 392.6, 409.3, 421.7, 434.1, 445.4, 457.9,
         471.3, 482.4, 489.8, 500.6, 517.5, 532.1, 540.5, 552.8, 567.6, 586.9, 605.8, 623.1, 647.0,
         644.7, 655.3, 676.0, 689.9, 700.0, 711.4, 712.3, 721.2, 736.6, 754.6, 768.3, 777.7, 815.5])
    df_inflation = pd.DataFrame(data=inflation_data, columns=['Inflation'], dtype='float', )
    df_inflation['Year'] = np.arange(1970, 2022, 1)

    salary_list = []

    i = 0

    for url in df.major_urls:
        url = str(url)
        # print(i, url)
        i = i + 1
        if url != 'nan':
            ids = findTables(url)
            if 'br-salaries' in ids:
                df_salary = pullTable(url, 'br-salaries')
                # Replace the Year and Salary columns with numerics
                df_salary['Year'] = df_salary['Year'].str.extract('(\d+)').astype(float)
                df_salary = df_salary.dropna(subset=["Year"])
                df_salary['Salary'] = df_salary['Salary'].str.replace('*', '')
                df_salary = df_salary[
                    df_salary.Salary != ''].copy()  # remove any rows that has a year but empty salary value
                df_salary['Salary'] = df_salary['Salary'].replace('[\$,]', '', regex=True).astype(float)

                # Adjust the salaries for inflation
                df_salary = pd.merge(df_salary, df_inflation, how="left", on=["Year"])
                df_salary['Salary_adj'] = df_salary['Salary'] * df_salary['Inflation']

                if df_salary[df_salary['Year'] < 2000]['Salary_adj'].sum() > 0:
                    salary_list.extend([-1 * df_salary[df_salary['Year'] < 2000][
                        'Salary_adj'].sum()])  # Get all the salaries (if any) from before 2000 and negate it
                else:
                    salary_list.extend([df_salary[df_salary['Year'] >= 2000][
                                            'Salary_adj'].sum()])  # Get all the salaries (if any) from 2000 onwards
            else:
                salary_list.extend([0])  # if no salaries table, add a zero salary
        else:
            salary_list.extend([0])  # if no majors url, add a zero salary

    pd.options.mode.chained_assignment = 'warn'

    return (salary_list)


def pullDraftRound(df):
    draft_round_list = []

    for url in df.minor_urls:

        res = requests.get(url)
        ## The next two lines get around the issue with comments breaking the parsing.
        comm = re.compile("<!--|-->")
        soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')

        links = soup.findAll('a')  # find all href links
        link = list(filter(lambda a: 'draft/?year_ID' in str(a),
                           links))  # only grab the links for the "overview" page and make it a list

        if link:
            draft = str(link[-1])  # grab the link outlining the latest draft year for the player
            draft_round_string = draft[draft.find(">") + 1: draft.find(
                "</a>")]  # grab the round the player was drafted as a string
            draft_round_number = int(re.sub("[^0-9]", "", draft_round_string))  # just keep the round number
        else:
            draft_round_number = 'np.nan'  # if it is empty, just add the np.nan as they dont have draft data

        draft_round_list.append(draft_round_number)

    return draft_round_list


def pullYearsInMinors(df):

  years_in_minors_list = []

  for url in df.minor_urls:

    # Pull the first table from the players minor league page
    df_tmp = pullTable(url, 'standard_batting')
    # Grab the entries that says Minors or All Levels, this contains the number of seasons
    df_tmp = df_tmp.loc[df_tmp['Year'].str.contains('|'.join(["Minors", "All Levels"]), case=False)]

    # Extract the number from the text (the first row from the df_tmp)
    for i in df_tmp.iloc[0]['Year'].split():
      for j in i.split('('):
        if j.isdigit():
          years_in_minors_list.append(j)

  return (years_in_minors_list)

def pullPositionsInMinors(df):

  positions_in_minors_list = []

  for url in df.minor_urls:
    res = requests.get(url)
    ## The next two lines get around the issue with comments breaking the parsing.
    comm = re.compile("<!--|-->")
    soup = bs4.BeautifulSoup(comm.sub("", res.text), 'lxml')

    links = soup.find_all('p') # find all <p>

    position = list(filter(lambda a: 'Position' in str(a), links)) # grab the string with "Positions"

    if position:
      position = str(position[-1]) # convert into a string
      position_string = position[position.find("</strong>\n") + 11: position.find("\n  \n</p>")] # filter string to just the positions
      position_string = position_string.replace("and", ",")  # convert the "ands" into commas
      position_string = position_string.replace(" ", "") # remove all trailiing and leading spaces

    else:
      position_string = "na"


    positions_in_minors_list.append(position_string)

  return (positions_in_minors_list)

# %%

# Start timer
tic = time.perf_counter()

# Get urls for all minor league teams in 2000
team_urls = findMinorLeagueTeamsURLS('https://www.baseball-reference.com/register/affiliate.cgi?year=2000')

# Loop through URLs, and get players
df = pd.DataFrame()
minor_urls = []
for team_url in team_urls[1:2]:  # take away [.] to get all the team_urls
    ids = findTables(team_url)
    if 'standard_roster' in ids:
        # print(team_url)
        df = df.append(pullTable(team_url, 'standard_roster'))
        minor_urls.extend(pullMinorURLS(team_url, 'standard_roster'))

# Clean up df and player_urls
df['minor_urls'] = minor_urls
df = df.drop_duplicates(subset=['minor_urls'])
df = df.reset_index()
df = df.drop(['index', 'Stint', 'From', 'To'], axis=1)
minor_urls = list(df['minor_urls'])

# Get years in Minors
years_in_minors_list = pullYearsInMinors(df)
df.loc[:,'years_in_minors'] = years_in_minors_list

# Get positions in Minors
positions_in_minors_list = pullPositionsInMinors(df)
df.loc[:,'positions_in_minors'] = positions_in_minors_list

# Get the Overview Links
major_urls = pullMajorURLS(df)
df.loc[:, 'major_urls'] = major_urls

# Get Salaries
salary_list = pullSalaries(df)
df.loc[:, 'salary'] = salary_list

# Get Draft Round
draft_round_list = pullDraftRound(df)
df.loc[:, 'draft_round'] = draft_round_list

# End Timer
toc = time.perf_counter()
print(f"Completed the web scraping in {(toc - tic) / 60:0.4f} minutes")

# %%
