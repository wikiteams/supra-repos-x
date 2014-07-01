'''
WikiTeams.pl scientific dataset creator
Calculating attributes x for developers
at one static moment on time (now)
If you are interested in dymanic data, please visit
https://github.com/wikiteams/github-data-tools/tree/master/pandas

@since 1.4.0408
@author Oskar Jarczyk

@update 1.07.2014
'''

version_name = 'Version 2.3.S1 codename: Tomato Slim'

from intelliRepository import MyRepository
from github import Github, UnknownObjectException, GithubException
import urllib2
import json
import csv
from Queue import Queue
import getopt
import scream
import gc
import os
import os.path
import sys
import codecs
import cStringIO
from bs4 import BeautifulSoup
from lxml import html, etree
from pyvirtualdisplay import Display
from selenium import webdriver
import __builtin__
import socket
import time
import threading
import traceback

'''
Niezaimplementowane wymiary oraz wyjasnienie czemu nie

7.  Wplyw na jakosc kodu globalnie i w repo
    [to jest oddzielnie i implementuje Blazej][generlanie nie wiem jak by to mialo wygladac]

10. Ilosc dyskusji pod kodem w repo
    [dyskusje to oddzielny temat badan i watpie by byly latwo dostepne przez skrypty tego typu]

16. Ilosc commitow w rozbiciu na jezyki programowania (skills)
    [...]

'''

count___ = 'selenium'
result_filename__ = 'developers_revealed_from_top_s.csv'
punch_card__filename__ = 'developers_revealed_punch_card.csv'


auth_with_tokens = True
use_utf8 = True

resume_on_repo = None
resume_on_repo_inclusive = True
reverse_queue = False

resume_stage = None
resume_entity = None

no_of_threads = 20
intelli_no_of_threads = False

github_clients = list()
github_clients_ids = list()

safe_margin = 100
timeout = 50
sleepy_head_time = 25
force_raise = False
show_trace = False

result_writer = None
result_punch_card_writer = None


def parse_number(s):
    return int(float(s))


def is_number(s):
    try:
        float(s)  # for int, long and float
    except ValueError:
        try:
            complex(s)  # for complex
        except ValueError:
            return False
    return True


def analyze_tag(tag):
    number = filter(lambda x: x.isdigit(), str(tag).strip(',').strip())
    return number


def usage():
    f = open('usage.txt', 'r')
    for line in f:
        print line


try:
    opts, args = getopt.getopt(sys.argv[1:], "ht:u:r:s:e:vx:z:qim:j:d:y", ["help", "tokens=",
                               "utf8=", "resume=", "resumestage=", "entity=", "verbose",
                               "threads=", "timeout=", "reverse", "intelli", "safemargin=",
                               "sleep=", "fraise=", "trace", "resumeinclusive"])
except getopt.GetoptError as err:
    # print help information and exit:
    print str(err)  # will print something like "option -a not recognized"
    usage()
    sys.exit(2)

for o, a in opts:
    if o in ("-v", "--verbose"):
        __builtin__.verbose = True
        scream.ssay('Enabling verbose mode.')
    elif o in ("-h", "--help"):
        usage()
        sys.exit()
    elif o in ("-t", "--tokens"):
        auth_with_tokens = (a in ['true', 'True'])
    elif o in ("-u", "--utf8"):
        use_utf8 = (a not in ['false', 'False'])
    elif o in ("-r", "--resume"):  # if running after a long pause, consider starting from new
        resume_on_repo = a  # remember dataset is a static one point in time
        scream.ssay('Resume on repo? ' + str(resume_on_repo))
    elif o in ('--resumeinclusive'):
        resume_on_repo_inclusive = True
        scream.ssay('Resume on repo with inclusion')
    elif o in ("-s", "--resumestage"):
        resume_stage = a
        scream.ssay('Resume on repo with stage ' + str(resume_stage))
    elif o in ("-x", "--threads"):
        no_of_threads = int(float(a))
        scream.ssay('Number of threads to engage ' + str(no_of_threads))
    elif o in ("-z", "--timeout"):
        timeout = int(float(a))
        scream.ssay('Connection timeout ' + str(timeout))
    elif o in ("-m", "--safemargin"):
        safemargin = int(float(a))
        scream.ssay('Connection timeout ' + str(timeout))
    elif o in ("-j", "--sleep"):
        sleepy_head_time = int(float(a))
        scream.ssay('Retry time: ' + str(sleepy_head_time))
    elif o in ("-i", "--intelli"):
        intelli_no_of_threads = True
        scream.ssay('Matching thread numbers to credential? ' + str(intelli_no_of_threads))
    elif o in ("-d", "--fraise"):
        force_raise = (a not in ['false', 'False'])
        scream.ssay('Execution error will lead to program terminate? ' + str(force_raise))
    elif o in ("-y", "--trace"):
        show_trace = True
        scream.ssay('Enable traceback and inspect? ' + str(show_trace))
    elif o in ("-e", "--entity"):
        resume_entity = a
        scream.ssay('Resume on stage with entity ' + str(resume_entity))
    elif o in ("-q", "--reverse"):
        reverse_queue = (a not in ['false', 'False'])
        result_filename__ = 'developers_revealed_from_bottom_s.csv'
        scream.ssay('Queue will be reversed, program will start from end ' + str(reverse_queue))

repos = Queue()

'''
Explanation of an input data, theye are CSV file with data
retrieved from Google BigQuery consisted of repo name, owner
and sorted by number of forks and watchers, for analysis we
take around 32k biggest GitHub repositories
'''
input_filename = 'result_stargazers_2013_final_mature.csv'
repos_reported_nonexist = open('reported_nonexist_fifo.csv', 'ab', 0)
repos_reported_execution_error = open('reported_execution_error_fifo.csv', 'ab', 0)


class Stack:
    def __init__(self):
        self.__storage = []

    def isEmpty(self):
        return len(self.__storage) == 0

    def push(self, p):
        self.__storage.append(p)

    def pop(self):
        return self.__storage.pop()


class WriterDialect(csv.Dialect):
    strict = True
    skipinitialspace = True
    quoting = csv.QUOTE_MINIMAL
    delimiter = ','
    escapechar = '\\'
    quotechar = '"'
    lineterminator = '\n'


class RepoReaderDialect(csv.Dialect):
    strict = True
    skipinitialspace = True
    quoting = csv.QUOTE_ALL
    delimiter = ';'
    escapechar = '\\'
    quotechar = '"'
    lineterminator = '\n'


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and re-encodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")


class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self


class UnicodeWriter:
    """
    A CSV writer which will write rows to CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=WriterDialect, encoding="utf-8", **kwds):
        # Redirect output to a queue
        self.queue = cStringIO.StringIO()
        self.writer = csv.writer(self.queue, dialect=dialect, **kwds)
        self.stream = f
        self.encoder = codecs.getincrementalencoder(encoding)()

    def writerow(self, row):
        self.writer.writerow([s.encode("utf-8") for s in row])
        # Fetch UTF-8 output from the queue ...
        data = self.queue.getvalue()
        data = data.decode("utf-8")
        # ... and reencode it into the target encoding
        data = self.encoder.encode(data)
        # write to the target stream
        self.stream.write(data)
        # empty queue
        self.queue.truncate(0)

    def writerows(self, rows):
        for row in rows:
            self.writerow(row)

'''
developer_revealed(repository, repo, contributor, result_writer)
return nothing, but writes final result row to a csv file
repository = github object, repo = my class object, contributor = nameduser
'''
def developer_revealed(thread_getter_instance, repository, repo, contributor):
    global result_writer
    global result_punch_card_writer

    assert result_punch_card_writer is not None

    developer_login = contributor.login
    scream.log_debug('Assigning a contributor: ' + str(developer_login) + ' to a repo: ' + str(repository.name), True)
    developer_name = contributor.name
    # 1. Ilosc osob, ktore dany deweloper followuje [FollowEvent]
    developer_followers = contributor.followers
    # 2. Ilosc osob, ktore followuja dewelopera [FollowEvent]
    developer_following = contributor.following

    developer_location = contributor.location
    developer_total_private_repos = contributor.total_private_repos
    developer_total_public_repos = contributor.public_repos

    # 5.  Ilosc repo, ktorych nie tworzyl, w ktorych jest team member [TeamAddEvent] [MemberEvent]
    developer_collaborators = contributor.collaborators
    # 6.  Ilosc repo, ktorych nie tworzyl, w ktorych jest contributorem [PushEvent] [IssuesEvent] [PullRequestEvent] [GollumEvent]
    developer_contributions = contributor.contributions

    # his_repositories - Ilosc projektow przez niego utworzonych / ktorych jest wlascicielem
    his_repositories = contributor.get_repos()

    # 17. Czy commituje w godzinach pracy (zaleznie od strefy czasowej)?
    developer_works_during_bd = None
    developer_works_period = None
    response = urllib2.urlopen('http://osrc.dfm.io/' + str(developer_login) + '.json')
    data = json.load(response)
    time_of_activity_per_hours = [0 for i in xrange(23)]
    for day_entry_element in data['usage']['events']:
        for day___ in day_entry_element['day']:
            time_of_activity_per_hours[day_entry_element['day'].index(day___)] += parse_number(day___)
    # count activity during business day
    count_bd__ = 0
    count_bd__ += (time_of_activity_per_hours[i] for i in range(9, 17))
    # now count activity during not-busines hours :)
    count_nwh__ = 0
    count_nwh__ += (time_of_activity_per_hours[i] for i in range(0, 8))
    count_nwh__ += (time_of_activity_per_hours[i] for i in range(18, 23))
    developer_works_during_bd = True if count_bd__ >= count_nwh__ else False
    # -----------------------------------------------------------------------

    while True:
        total_his_repositories = 0
        total_his_stars = 0
        total_his_watchers = 0
        total_his_forks = 0
        total_his_has_issues = 0
        total_his_has_wiki = 0
        total_his_open_issues = 0
        total_network_count = 0
        total_his_collaborators = 0
        total_his_contributors = 0

        '''
        total_his_commits = 0
        total_his_branches = 0
        total_his_releases = 0
        '''
        total_his_issues = 0
        total_his_pull_requests = 0

        '''
        total_his_commits = 'N/A'
        total_his_branches = 'N/A'
        total_his_releases = 'N/A'
        total_his_issues = 'N/A'
        total_his_pull_requests = 'N/A'
        total_his_contributors = 'N/A'
        '''

        '''
        There are couple of statistics cards
        def get_stats_punch_card(self):
            (Get the number of commits per hour in each day)
            http://developer.github.com/v3/repos/statistics/#get-the-number-of-commits-per-hour-in-each-day

        def get_stats_participation(self):
            (Get the weekly commit count for the repo owner and everyone else)
            http://developer.github.com/v3/repos/statistics/#get-the-weekly-commit-count-for-the-repo-owner-and-everyone-else

        def get_stats_code_frequency(self):
            (Get the number of additions and deletions per week)
            http://developer.github.com/v3/repos/statistics/#get-the-number-of-additions-and-deletions-per-week

        def get_stats_commit_activity(self):
            (Get the number of commits per hour in each day)
            developer.github.com/v3/repos/statistics/#get-the-number-of-commits-per-hour-in-each-day

        def get_stats_contributors(self):
            (Get contributor list with additions deletions and commit counts)
            http://developer.github.com/v3/repos/statistics/#get-contributors-list-with-additions-deletions-and-commit-counts
        '''

        try:
            for his_repo in his_repositories:  # iteracja po repozytoriach ktorych jest wlascicielem

                total_his_repositories += 1
                total_his_forks += his_repo.forks_count
                total_his_stars += his_repo.stargazers_count
                total_his_watchers += his_repo.watchers_count
                total_his_has_issues += 1 if his_repo.has_issues else 0
                total_his_has_wiki += 1 if his_repo.has_wiki else 0
                total_his_open_issues += his_repo.open_issues
                total_network_count += his_repo.network_count

                try:
                    stats = his_repo.get_stats_contributors()
                    for s in stats:
                        ad___c = 0
                        ad___a = 0
                        ad___d = 0
                        for w in s.weeks:
                            ad___c += w.c
                            ad___a += w.a
                            ad___d += w.d
                        result_punch_card_writer.writerow([str(his_repo.owner.login), str(his_repo.name),
                                                          str(developer_login), str(s.author.login), str(s.total), str(ad___c), str(ad___a), str(ad___d)])
                except GithubException as e:
                    freeze(str(e) + ' in try per repo of x-dev repos')
                    if ("message" in e.data) and (e.data["message"].strip() == "Repository access blocked"):
                        scream.log_debug("It is a private repo.. Skip!")
                        continue
                    if force_raise:
                        raise
                except Exception as e:
                    freeze(str(e) + ' in try per repo of x-dev repos')
                    # probably punch card not ready
                    if force_raise:
                        raise
            break
        except Exception as e:
            freeze(str(e) + ' in main loop of developer_revealed()')
            his_repositories = contributor.get_repos()
            if force_raise:
                raise

    # Developer company (if any given)
    company = contributor.company
    created_at = contributor.created_at
    # Does the developer want to be hired?
    hireable = contributor.hireable

    scream.log_debug('Thread ' + str(thread_getter_instance.threadId) +
                     ' Finished revealing contributor: ' + str(developer_login) + ' in a repo: ' + str(repository.name), True)

    if show_trace:
        scream.log_debug('Printing traceback stack', True)
        traceback.print_stack()
        scream.log_debug('Printing traceback exc pathway', True)
        traceback.print_exc()

    if not use_utf8:
        result_writer.writerow([str(repo.getUrl()), str(repo.getName()), str(repo.getOwner()),
                               str(repo.getStargazersCount()), str(repo.getWatchersCount()), str(developer_login),
                               (str(developer_name) if developer_name is not None else ''), str(developer_followers), str(developer_following),
                               str(developer_collaborators), (str(company) if company is not None else ''), str(developer_contributions),
                               str(created_at), (str(hireable) if hireable is not None else ''),
                               str(total_his_repositories), str(total_his_stars), str(total_his_collaborators), str(total_his_contributors),
                               str(total_his_watchers), str(total_his_forks), str(total_his_has_issues),
                               str(total_his_has_wiki), str(total_his_open_issues), str(total_network_count),
                               (str(developer_location) if developer_location is not None else ''),
                               str(developer_total_private_repos), str(developer_total_public_repos),
                               str(total_his_issues), str(total_his_pull_requests), str(developer_works_during_bd), str(developer_works_period)])
    else:
        result_writer.writerow([repo.getUrl(), repo.getName(), repo.getOwner(), str(repo.getStargazersCount()), str(repo.getWatchersCount()), developer_login,
                               (developer_name if developer_name is not None else ''), str(developer_followers), str(developer_following),
                               str(developer_collaborators), (company if company is not None else ''), str(developer_contributions),
                               str(created_at), (str(hireable) if hireable is not None else ''),
                               str(total_his_repositories), str(total_his_stars), str(total_his_collaborators), str(total_his_contributors),
                               str(total_his_watchers), str(total_his_forks), str(total_his_has_issues),
                               str(total_his_has_wiki), str(total_his_open_issues), str(total_network_count),
                               (developer_location if developer_location is not None else ''),
                               str(developer_total_private_repos), str(developer_total_public_repos),
                               str(total_his_issues), str(total_his_pull_requests), str(developer_works_during_bd), str(developer_works_period)])

    scream.log_debug('Wrote row to CSV.', True)


def freeze(message):
    global sleepy_head_time
    scream.say('Sleeping for ' + str(sleepy_head_time) + ' seconds. Reason: ' + str(message))
    time.sleep(sleepy_head_time)


def make_headers(filename_for_headers):
    with open(filename_for_headers, 'ab') as output_csvfile:
        devs_head_writer = UnicodeWriter(output_csvfile) if use_utf8 else csv.writer(output_csvfile, dialect=WriterDialect)
        tempv = ('repo_url', 'repo_name', 'repo_owner', 'stargazers_count', 'watchers_count', 'developer_login', 'developer_name',
                 'developer_followers', 'developer_following', 'developer_collaborators', 'developer_company', 'developer_contributions',
                 'created_at', 'developer_is_hireable', 'total_his_repositories', 'total_in-his-repos_stars',
                 'total_in-his-repos_collaborators', 'total_in-his-repos_contributors',
                 'total_in-his-repos_watchers', 'total_in-his-repos_forks', 'total_in-his-repos_has_issues',
                 'total_in-his-repos_has_wiki', 'total_in-his-repos_open_issues', 'total_network_count',
                 'developer_location', 'developer_total_private_repos',
                 'developer_total_public_repos', 'total_in-his-repos_issues', 'total_in-his-repos_pull_requests',
                 'developer_works_during_bd', 'developer_works_period')
        devs_head_writer.writerow(tempv)


class GeneralGetter(threading.Thread):
    finished = False
    repository = None
    repo = None
    github_client = None
    display = None
    browser = None

    def __init__(self, threadId, repository, repo, github_client):
        scream.say('Initiating GeneralGetter, running __init__ procedure.')
        self.threadId = threadId
        threading.Thread.__init__(self)
        self.daemon = True
        self.finished = False
        self.repository = repository
        self.repo = repo
        self.github_client = github_client

    def run(self):
        scream.cout('GeneralGetter starts work...')
        self.finished = False
        # it is quite reasonable to initiate a display driver for selenium
        # per one getter, threads work on jobs linear so its the max partition of driver
        # we can allow, multiple threads working on one virtual display - its without sense
        #self.initiate_selenium()
        # now its ok to start retrieving data.. allonsy !
        self.get_data()

    def initiate_selenium(self):
        scream.say('Initiating selenium...')
        self.display = Display(visible=0, size=(800, 600))
        self.display.start()
        self.browser = webdriver.Firefox()
        self.browser.implicitly_wait(15)
        scream.say('Selenium ready for action')

    def analyze_with_selenium(self, repository):
        result = dict()
        scream.say('Starting webinterpret for ' + repository.html_url + '..')
        assert repository is not None
        url = repository.html_url
        assert url is not None
        while True:
            try:
                self.browser.set_page_load_timeout(15)
                self.browser.get(url)
                scream.say('Data from web retrieved')
                doc = html.document_fromstring(unicode(self.browser.page_source))
                scream.log_debug(str(url), True)
                scream.say('Continue to work on ' + url)
                scream.say('Page source sent further')

                scream.say('Verify if 404 (repo deleted) otherwise keep on going')
                parallax = doc.xpath('//div[@id="parallax_illustration"]')

                if (len(parallax) > 0):
                    scream.say('Verified that 404 (repo deleted)')
                    result['status'] = '404'
                    break

                scream.say('Verified that not 404')

                scream.say('Verify if repo empty otherwise keep on going')
                repo_empty = doc.xpath('//div[@class="blankslate has-fixed-width"]')

                if (len(repo_empty) > 0):
                    scream.say('Verified that repo is empty')
                    result['status'] = 'EMPTY'
                    break

                scream.say('Verified that repo not empty')

                ns = doc.xpath('//ul[@class="numbers-summary"]')
                sunken = doc.xpath('//ul[@class="sunken-menu-group"]')

                scream.say('XPath made some search for ' + url + ' .. move on to bsoup..')
                scream.say('Xpath done searching')
                scream.say('Element found?: ' + str(len(ns) == 1))

                element = ns[0]
                element_sunken = sunken[0]
                local_soup = BeautifulSoup(etree.tostring(element))
                local_soup_sunken = BeautifulSoup(etree.tostring(element_sunken))

                enumarables = local_soup.findAll("li")
                enumarables_more = local_soup_sunken.findAll("li")

                commits = enumarables[0]
                scream.say('enumarables[0]')
                commits_number = analyze_tag(commits.find("span", {"class": "num"}))
                scream.say('analyze_tag finished execution for commits_number')
                scream.say('Before parse number: ' + str(commits_number))
                result['commits'] = parse_number(commits_number)
                scream.log_debug(result['commits'], True)
                scream.say('enumarables[1]')
                branches = enumarables[1]
                branches_number = analyze_tag(branches.find("span", {"class": "num"}))
                scream.say('Before parse number: ' + str(branches_number))
                result['branches'] = parse_number(branches_number)
                scream.log_debug(result['branches'], True)
                scream.say('enumarables[2]')
                releases = enumarables[2]
                releases_number = analyze_tag(releases.find("span", {"class": "num"}))
                scream.say('Before parse number: ' + str(releases_number))
                result['releases'] = parse_number(releases_number)
                scream.log_debug(result['releases'], True)
                scream.say('enumarables[3]')
                contributors = enumarables[3]
                contributors_number = analyze_tag(contributors.find("span", {"class": "num"}))
                scream.say('Before parse number: ' + str(contributors_number))
                result['contributors'] = parse_number(contributors_number)
                scream.log_debug(result['contributors'], True)

                result['issues'] = 0
                result['pulls'] = 0

                for enumerable___ in enumarables_more:
                    if enumerable___["aria-label"] == "Pull Requests":
                        pulls_tag = enumerable___
                        pulls_number = analyze_tag(pulls_tag.find("span", {"class": "counter"}))
                        scream.say('Before parse number: ' + str(pulls_number))
                        result['pulls'] = parse_number(pulls_number)
                    elif enumerable___["aria-label"] == "Issues":
                        issues_tag = enumerable___
                        issues_number = analyze_tag(issues_tag.find("span", {"class": "counter"}))
                        scream.say('Before parse number: ' + str(issues_number))
                        result['issues'] = parse_number(issues_number)

                result['status'] = 'OK'
                break
            except TypeError as ot:
                scream.say(str(ot))
                scream.say('Scrambled results (TypeError). Maybe GitHub down. Retry')
                time.sleep(5.0)
                if force_raise:
                    raise
            except Exception as e:
                scream.say(str(e))
                scream.say('No response from selenium. Retry')
                time.sleep(2.0)
                if force_raise:
                    raise

        assert 'status' in result
        return result


    def is_finished(self):
        return self.finished if self.finished is not None else False

    def set_finished(self, finished):
        scream.say('Marking the thread ' + str(self.threadId) + ' as finished..')
        self.finished = finished

    def cleanup(self):
        # try:
        #     self.browser.close()
        #     self.browser.quit()
        #     self.display.stop()
        #     self.display.popen.kill()
        # except:
        #     scream.say('Did my best to clean up after selenium and pyvirtualdisplay')
        #     if force_raise:
        #         raise
        scream.say('Marking thread on ' + self.repo.getKey() + ' as finished..')
        self.finished = True
        scream.say('Terminating thread on ' + self.repo.getKey() + ' ...')
        self.terminate()


    '''
    def build_list_of_programmers(result_set_programmers,
                                  repo_key, repository)
    returns dict (github user name -> User object) 1..1
    key is a string contributor username (login)
    second object is actuall PyGithub User instance, meow !
    '''
    def build_list_of_programmers(self, result_set_programmers, repo_key, repository):
        result_set = dict()
        contributors__ = result_set_programmers

        while True:
            result_set.clear()
            try:
                for contributor in contributors__:
                    result_set[contributor.login] = contributor
                break
            except TypeError as e:
                scream.log_error('Repo + Contributor TypeError, or paginated through' +
                                 ' contributors gave error. ' + key + ', error({0})'.
                                 format(str(e)), True)
                repos_reported_execution_error.write(key + os.linesep)
                if force_raise:
                    raise
                #break
            except socket.timeout as e:
                scream.log_error('Timeout while revealing details.. ' +
                                 ', error({0})'.format(str(e)), True)
                freeze('build_list_of_programmers will retry')
                if force_raise:
                    raise
                #break
            except Exception as e:
                scream.log_error('Exception while revealing details.. ' +
                                 ', error({0})'.format(str(e)), True)
                freeze('build_list_of_programmers will retry')
                if force_raise:
                    raise
                #break
        return result_set


    def get_data(self):
        global resume_stage

        scream.say('Executing inside-thread method get_data() for: ' + str(self.threadId))
        if resume_stage in [None, 'contributors']:
            #try:
            scream.ssay('Checking size of a ' + str(self.repo.getKey()) + ' team')
            '1. Team size of a repository'
            self.contributors = self.repository.get_contributors()
            assert self.contributors is not None

            self.repo_contributors = set()
            self.contributors_static = self.build_list_of_programmers(self.contributors, self.repo.getKey(), self.repository)
            for contributor in self.contributors_static.items():
                scream.log_debug('move with contributor to next from contributors_static.items()', True)
                while True:
                    scream.say('Inside while True: (line 674)')
                    try:
                        self.contributor_login = contributor[0]
                        self.contributor_object = contributor[1]
                        scream.say(str(self.contributor_login))
                        self.repo_contributors.add(self.contributor_login)
                        scream.say(str(self.repo_contributors))
                        developer_revealed(threading.current_thread(), self.repository, self.repo, self.contributor_object)
                        scream.say('Finished revealing developer')
                        break
                    except TypeError as e:
                        scream.log_error('Repo + Contributor TypeError, or paginated through' +
                                         ' contributors gave error. ' + key + ', error({0})'.
                                         format(str(e)), True)
                        repos_reported_execution_error.write(key + os.linesep)
                        if force_raise:
                            raise
                        #break
                    except socket.timeout as e:
                        scream.log_error('Timeout while revealing details.. ' +
                                         ', error({0})'.format(str(e)), True)
                        freeze('socket.timeout in paginate through x contributors')
                        if force_raise:
                            raise
                        #break
                    except Exception as e:
                        scream.log_error('Exception while revealing details.. ' +
                                         ', error({0})'.format(str(e)), True)
                        freeze(str(e) + ' in paginate through x contributors')
                        if force_raise:
                            raise
                        #break

            assert self.repo_contributors is not None
            self.repo.setContributors(self.repo_contributors)
            self.repo.setContributorsCount(len(self.repo_contributors))
            scream.log('Added contributors of count: ' + str(len(self.repo_contributors)) + ' to a repo ' + key)
        self.cleanup()


def all_finished(threads):
    are_finished = True
    for thread in threads:
        if not thread.is_finished():
            return False
    return are_finished


def num_working(threads):
    are_working = 0
    for thread in threads:
        if not thread.is_finished():
            are_working += 1
    return are_working


def num_modulo(thread_id_count__):
    global no_of_threads
    return thread_id_count__ % no_of_threads


if __name__ == "__main__":
    '''
    Starts process of work on CSV files which are output of Google Bigquery
    whenever intelliGit.py is executed as an standalone program
    the program reads through the input and gets all data bout programmers
    '''
    scream.say('Start main execution')
    scream.say('Welcome to WikiTeams.pl GitHub repo analyzer!')
    scream.say(version_name)

    secrets = []

    credential_list = []
    # reading the secrets, the Github factory objects will be created in next paragraph
    with open('pass.txt', 'r') as passfile:
        line__id = 0
        for line in passfile:
            line__id += 1
            secrets.append(line)
            if line__id % 4 == 0:
                login_or_token__ = str(secrets[0]).strip()
                pass_string = str(secrets[1]).strip()
                client_id__ = str(secrets[2]).strip()
                client_secret__ = str(secrets[3]).strip()
                credential_list.append({'login': login_or_token__, 'pass': pass_string, 'client_id': client_id__, 'client_secret': client_secret__})
                del secrets[:]

    scream.say(str(len(credential_list)) + ' full credentials successfully loaded')

    # with the credential_list list we create a list of Github objects, github_clients holds ready Github objects
    for credential in credential_list:
        if auth_with_tokens:
            local_gh = Github(login_or_token=credential['pass'], client_id=credential['client_id'],
                              client_secret=credential['client_secret'], user_agent=credential['login'],
                              timeout=timeout)
            github_clients.append(local_gh)
            github_clients_ids.append(credential['login'])
            scream.say(local_gh.rate_limiting)
        else:
            local_gh = Github(credential['login'], credential['pass'])
            github_clients.append(local_gh)
            scream.say(local_gh.rate_limiting)

    scream.cout('How many Github objects in github_clients: ' + str(len(github_clients)))
    scream.cout('Assigning current github client to the first object in a list')

    github_client = github_clients[0]
    lapis = local_gh.get_api_status()
    scream.say('Current status of GitHub API...: ' + lapis.status + ' (last update: ' + str(lapis.last_updated) + ')')

    if intelli_no_of_threads:
        scream.say('Adjusting no of threads to: ' + str(len(github_clients)))
        no_of_threads = len(github_clients)
        scream.say('No of threads is currently: ' + str(no_of_threads))

    is_gc_turned_on = 'turned on' if str(gc.isenabled()) else 'turned off'
    scream.ssay('Garbage collector is ' + is_gc_turned_on)

    scream.say('WORKING WITH INPUT FILE : ' + input_filename)  # simply 'result_stargazers_2013_final_mature.csv'
    scream.say('This can take a while, max aprox. 2 minutes...')
    filename_ = 'data/' if sys.platform == 'linux2' else 'data\\'
    filename__ = filename_ + input_filename  # remember it is in a /data subdir
    with open(filename__, 'rb') as source_csvfile:
        reposReader = UnicodeReader(f=source_csvfile, dialect=RepoReaderDialect)
        reposReader.next()
        previous = ''
        for row in reposReader:
            scream.log('Processing row: ' + str(row))
            url = row[1]
            owner = row[0]
            name = row[2]

            key = owner + '/' + name
            scream.log('Key built: ' + key)

            repo = MyRepository()
            repo.setKey(key)
            repo.setInitials(name, owner)
            repo.setUrl(url)

            #check here if repo dont exist already in dictionary!
            if key == previous:
                scream.log('We already found rep ' + key +
                           ' in the dictionary..')
            else:
                repos.put(repo)
                previous = key

    scream.say('Finished creating queue, size of fifo construct is: ' +
               str(repos.qsize()))

    iteration_step_count = 1

    if not os.path.isfile(result_filename__):
        make_headers(result_filename__)

    if reverse_queue:
        aux_stack = Stack()
        while not repos.empty():
            aux_stack.push(repos.get())
        while not aux_stack.isEmpty():
            repos.put(aux_stack.pop())

    with open(result_filename__, 'ab', 0) as result_file:
        threads = []
        thread_id_count = 0

        result_punch_card = open(punch_card__filename__, 'ab', 0)
        result_punch_card_writer = UnicodeWriter(result_punch_card)

        result_writer = UnicodeWriter(result_file)
        while not repos.empty():
            repo = repos.get()
            key = repo.getKey()

            # resume on repo is implemented, just provide parameters in argvs
            if resume_on_repo is not None:
                resume_on_repo_owner = resume_on_repo.split('/')[0]
                resume_on_repo_name = resume_on_repo.split('/')[1]
                # here basicly we pass already processed repos
                # hence the continue directive till resume_on_repo pass
                if not ((resume_on_repo_name == repo.getName()) and
                        (resume_on_repo_owner == repo.getOwner())):
                    iteration_step_count += 1
                    continue
                else:
                    resume_on_repo = None
                    iteration_step_count += 1
                    if resume_on_repo_inclusive:
                        scream.say('Not skipping the ' + str(resume_on_repo_name))
                    else:
                        scream.say('Starting from the next from ' + str(resume_on_repo_name))
                        continue

            try:
                while True:
                    if show_trace:
                        scream.log_debug('Printing traceback stack', True)
                        traceback.print_stack()
                        scream.log_debug('Printing traceback exc pathway', True)
                        traceback.print_exc()
                        #scream.log_warning(inspect.getargvalues(sys.exc_info()[2].tb_frame))
                    scream.say('Creating Repository.py instance from API result..')
                    scream.say('Working at the moment on repo: ' + str(repo.getKey()))
                    current_ghc = github_clients[num_modulo(thread_id_count)]
                    current_ghc_desc = github_clients_ids[num_modulo(thread_id_count)]
                    repository = current_ghc.get_repo(repo.getKey())
                    scream.log_debug('Got a repository from API', True)
                    repo.setRepoObject(repository)
                    repo.setStargazersCount(repository.stargazers_count)
                    scream.say('There are ' + str(repo.getStargazersCount()) + ' stargazers.')
                    assert repo.getStargazersCount() is not None
                    repo.setWatchersCount(repository.watchers_count)  # PyGithub must be joking, this works, watchers_count not
                    scream.say('There are ' + str(repo.getWatchersCount()) + ' watchers.')
                    assert repo.getWatchersCount() is not None
                    # from this line move everything to a thread!
                    scream.say('Create instance of GeneralGetter with ID ' + str(thread_id_count) + ' and token ' + str(current_ghc_desc))
                    scream.log_debug('Make GeneralGetter object', True)
                    gg = GeneralGetter(thread_id_count, repository, repo, current_ghc)
                    scream.say('Creating instance of GeneralGetter complete')
                    scream.say('Appending thread to collection of threads')
                    threads.append(gg)
                    scream.say('Append complete, threads[] now have size: ' + str(len(threads)))
                    thread_id_count += 1
                    scream.log_debug('Starting thread ' + str(thread_id_count-1) + '....', True)
                    gg.start()
                    break
            except UnknownObjectException as e:
                scream.log_warning('Repo with key + ' + key +
                                   ' not found, error({0}): {1}'.
                                   format(e.status, e.data), True)
                repos_reported_nonexist.write(key + os.linesep)
                continue
            except GithubException as e:
                scream.log_warning('Repo with key + ' + key +
                                   ' made exception in API, error({0}): {1}'.
                                   format(e.status, e.data), True)
                repos_reported_execution_error.write(key + os.linesep)
                freeze(str(e) + ' in the main loop (most top try-catch)')
                scream.say('Trying again with repo ' + str(key))
                if show_trace:
                    scream.log_debug('Printing traceback stack', True)
                    traceback.print_stack()
                    scream.log_debug('Printing traceback exc pathway', True)
                    traceback.print_exc()
                if force_raise:
                    raise
            except Exception as e:
                scream.log_warning('Repo with key + ' + key +
                                   ' made other error ({0})'.
                                   format(str(e).decode('utf-8')), True)
                repos_reported_execution_error.write(key + os.linesep)
                freeze(str(e) + ' in the main loop (most top try-catch)')
                scream.say('Trying again with repo ' + str(key))
                if show_trace:
                    scream.log_debug('Printing traceback stack', True)
                    traceback.print_stack()
                    scream.log_debug('Printing traceback exc pathway', True)
                    traceback.print_exc()
                if force_raise:
                    raise

            iteration_step_count += 1
            scream.ssay('Step no ' + str(iteration_step_count) +
                        '. Ordered working on a repo: ' + key)

            scream.say('threads[] have size: ' + str(len(threads)))

            while num_working(threads) >= no_of_threads:
                time.sleep(0.2)

            scream.say('Inviting new thread to the pool...')

            scream.ssay('Finished processing repo: ' + key + '.. moving on... ')
            #result_file.flush()

            #del repos[key]
            'Dictionary cannot change size during iteration'
            'TO DO: associated fields purge so GC will finish the job'
            'implement reset() in intelliRepository.py'
