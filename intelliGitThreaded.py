'''
WikiTeams.pl scientific dataset creator
Calculating attributes x for developers
at one static moment on time (now)
If you are interested in dymanic data, please visit
https://github.com/wikiteams/github-data-tools/tree/master/pandas

@since 1.4.0408
@author Oskar Jarczyk

@update 12.06.2014
'''

version_name = 'Version 2.0 codename: PO(program-oskiego)'

from intelliRepository import MyRepository
from github import Github, UnknownObjectException, GithubException
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
import __builtin__
import socket
import time
import threading

auth_with_tokens = True
use_utf8 = True
resume_on_repo = None
resume_stage = None
resume_entity = None
#quota_check = 0
github_clients = list()
github_client = None


def usage():
    f = open('usage.txt', 'r')
    for line in f:
        print line


try:
    opts, args = getopt.getopt(sys.argv[1:], "ht:u:r:s:e:v", ["help", "tokens=",
                               "utf8=", "resume=", "resumestage=", "entity=", "verbose"])
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
    elif o in ("-s", "--resumestage"):
        resume_stage = a
        scream.ssay('Resume on repo with stage ' + str(resume_stage))
    elif o in ("-e", "--entity"):
        resume_entity = a
        scream.ssay('Resume on stage with entity ' + str(resume_entity))

repos = Queue()

'''
Explanation of an input data, theye are CSV file with data
retrieved from Google BigQuery consisted of repo name, owner
and sorted by number of forks and watchers, for analysis we
take around 32k biggest GitHub repositories
'''
input_filename = 'result_stargazers_2013_final_mature.csv'
repos_reported_nonexist = open('reported_nonexist_fifo.csv', 'ab')
repos_reported_execution_error = open('reported_execution_error_fifo.csv', 'ab')


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


def developer_revealed(repository, repo, contributor, result_writer):
    #repository = github object, repo = my class object, contributor = nameduser
    scream.say('assigning a contributor: ' + str(contributor) + ' to a repo: ' + str(repository) + ' and mock object ' + str(repo))
    login = contributor.login
    name = contributor.name
    #1
    followers = contributor.followers
    #2
    following = contributor.following
    scream.say(following)
    scream.say(followers)
    his_repositories = contributor.get_repos()
    #3
    total_his_repositories = 0
    total_his_stars = 0
    total_his_watchers = 0
    total_his_forks = 0
    total_network_count = 0
    for his_repo in his_repositories:
        # his_repo.get_stats_contributors()
        check_quota_limit()
        total_his_repositories += 1
        total_his_forks += his_repo.forks_count
        total_his_stars += his_repo.stargazers_count
        total_his_watchers += his_repo.watchers_count
        total_network_count += his_repo.network_count
    #4
    # as far as i know - almost impossible to get
    # 5
    # blazej task, not mine
    # 6
    collaborators = contributor.collaborators
    company = contributor.company
    contributions = contributor.contributions
    created_at = contributor.created_at
    hireable = contributor.hireable
    result_writer.writerow([repo.getUrl(), repo.getName(), repo.getOwner(), login,
                           (name if name is not None else ''), str(followers), str(following),
                           str(collaborators), (company if company is not None else ''), str(contributions),
                           str(created_at), (str(hireable) if hireable is not None else ''), str(total_his_repositories), str(total_his_stars),
                           str(total_his_watchers), str(total_his_forks), str(total_network_count)])


def check_quota_limit():
    global github_client
    limit = github_client.get_rate_limit()
    found_hope = False
    if limit.rate.remaining < 10:
        for quota_hope in github_clients:
            limit_hope = quota_hope.get_rate_limit()
            if limit_hope.rate.remaining > 9:
                github_client = quota_hope
                found_hope = True
                break
        if not found_hope:
            freeze()
    else:
        scream.say("Limit ok, " + str(limit.rate.remaining) + ' left.')


def freeze():
    global github_client
    sleepy_head_time = 60 * 60
    time.sleep(sleepy_head_time)
    limit = github_client.get_rate_limit()
    while limit.rate.remaining < 15:
        time.sleep(sleepy_head_time)


def make_headers(filename_for_headers):
    with open(filename_for_headers, 'ab') as output_csvfile:
        devs_head_writer = UnicodeWriter(output_csvfile) if use_utf8 else csv.writer(output_csvfile, dialect=WriterDialect)
        tempv = ('repo_url', 'repo_name', 'repo_owner', 'dev_login', 'dev_name',
                 'followers', 'following', 'collaborators', 'company', 'contributions', 'created_at', 'hireable',
                 'total_his_repositories', 'total_his_stars', 'total_his_watchers', 'total_his_forks', 'total_network_count')
        devs_head_writer.writerow(tempv)


class GeneralGetter(threading.Thread):
    finished = False
    repository = None
    repo = None

    def __init__(self, threadId, repository, repo):
        self.threadId = threadId
        threading.Thread.__init__(self)
        self.daemon = True
        self.finished = False
        self.repository = repository
        self.repo = repo
        #self.resume_stage = resume_stage

    def run(self):
        scream.cout('GeneralGetter starts work...')
        self.finished = False
        self.get_data()

    def is_finished(self):
        return self.finished if self.finished is not None else False  # i dont know why there are none types :/

    def set_finished(self, finished):
        self.finished = finished

    def get_data(self):
        global resume_stage
        scream.say('get_data for: ' + str(self.threadId))
        if resume_stage in [None, 'contributors']:
            try:
                scream.ssay('Checking size of a team')
                '1. Rozmiar zespolu'
                contributors = repository.get_contributors()
                check_quota_limit()
                repo_contributors = []
                try:
                    for contributor in contributors:
                        repo_contributors.append(contributor)
                        check_quota_limit()
                        developer_revealed(repository, repo, contributor, result_writer)
                except TypeError:
                    repos_reported_execution_error.write(key + os.linesep)
                except socket.timeout:
                    repos_reported_execution_error.write(key + os.linesep)
                except:
                    repos_reported_execution_error.write(key + os.linesep)
                repo.setContributors(repo_contributors)
                #repo.setContributorsCount(len(repo_contributors))
                'class fields are not garbage, '
                'its better to calculate count on demand'
                scream.log('Added contributors of count: ' +
                           str(len(repo_contributors)) +
                           ' to a repo ' + key)
            except GithubException as e:
                if 'repo_contributors' not in locals():
                    repo.setContributors([])
                else:
                    repo.setContributors(repo_contributors)
                scream.log_error('Repo didnt gave any contributors, ' +
                                 'or paginated through' +
                                 ' contributors gave error. ' + key +
                                 ', error({0}): {1}'.
                                 format(e.status, e.data), True)
            finally:
                resume_stage = None

        self.finished = True


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
            local_gh = Github(login_or_token=credential['pass'], client_id=credential['client_id'], client_secret=credential['client_secret'], user_agent=credential['login'])
            github_clients.append(local_gh)
            #scream.say(local_gh.get_api_status)
            scream.say(local_gh.rate_limiting)
        else:
            local_gh = Github(credential['login'], credential['pass'])
            github_clients.append(local_gh)
            scream.say(local_gh.rate_limiting)

    scream.cout('How many Github objects in github_clients: ' + str(len(github_clients)))
    scream.cout('Assigning current github client to the first object in a list')
    github_client = github_clients[0]
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

    if not os.path.isfile('developers_revealed_from_top.csv'):
        make_headers('developers_revealed_from_top.csv')

    with open('developers_revealed_from_top.csv', 'ab') as result_file:
        threads = []

        result_writer = UnicodeWriter(result_file)
        while not repos.empty():
            repo = repos.get()
            key = repo.getKey()

            # resume on repo is implemented, just provide parameters in argvs
            if resume_on_repo is not None:
                resume_on_repo_name = resume_on_repo.split(',')[0]
                resume_on_repo_owner = resume_on_repo.split(',')[1]
                # here basicly we pass already processed repos
                # hence the continue directive till resume_on_repo pass
                if not ((resume_on_repo_name == repo.getName()) and
                        (resume_on_repo_owner == repo.getOwner())):
                    iteration_step_count += 1
                    continue
                else:
                    resume_on_repo = None
                    iteration_step_count += 1
                    continue

            try:
                repository = github_client.get_repo(repo.getKey())
                repo.setRepoObject(repository)
                # from this line move everything to a thread!
                scream.say('Create instance of GeneralGetter')
                gg = GeneralGetter(iteration_step_count, repository, repo)
                scream.say('Creating GeneralGetter(*) complete')
                #gg = GeneralGetter(iteration_step_count, repository, repo, resume_stage)
                scream.say('Appending thread to collection of threads')
                threads.append(gg)
                scream.say('Append complete, threads[] now have size: ' + str(len(threads)))
                scream.say('Starting thread....')
                gg.start()
            except UnknownObjectException as e:
                scream.log_warning('Repo with key + ' + key +
                                   ' not found, error({0}): {1}'.
                                   format(e.status, e.data), True)
                repos_reported_nonexist.write(key + os.linesep)
                continue
            except:
                scream.log_warning('Repo with key + ' + key +
                                   ' not found, error({0}): {1}'.
                                   format(e.status, e.data), True)
                repos_reported_nonexist.write(key + os.linesep)
                continue

            iteration_step_count += 1
            scream.ssay('Step no ' + str(iteration_step_count) +
                        '. Ordered working on a repo: ' + key)

            scream.say('threads[] have size: ' + str(len(threads)))
            print threads
            print threads[:]
            print threads[0]
            print type(threads[0])

            while num_working(threads) > 9:
                time.sleep(0.2)

            #if resume_stage in [None, 'languages']:
            #    scream.ssay('Getting languages of a repo')
            #    languages = repository.get_languages()  # dict object (json? object)
            #    repo.setLanguage(languages)
            #    scream.log('Added languages ' + str(languages) + ' to a repo ' + key)
            #    resume_stage = None

            # to juz mamy
            # if resume_stage in [None, 'labels']:
            #     scream.ssay('Getting labels of a repo')
            #     'getting labels, label is a tag which you can put in an issue'
            #     try:
            #         labels = repository.get_labels()  # github.Label object
            #         repo_labels = []
            #         for label in labels:
            #             repo_labels.append(label)
            #             check_quota_limit()
            #         repo.setLabels(repo_labels)
            #         scream.log('Added labels of count: ' + str(len(repo_labels)) +
            #                    ' to a repo ' + key)
            #     except GithubException as e:
            #         if 'repo_labels' not in locals():
            #             repo.setLabels([])
            #         else:
            #             repo.setLabels(repo_labels)
            #         scream.log_error('Repo didnt gave any labels, ' +
            #                          'or paginated through' +
            #                          ' labels gave error. ' +
            #                          'Issues are disabled for this' +
            #                          ' repo? + ' + key +
            #                          ', error({0}): {1}'.
            #                          format(e.status, e.data))
            #     finally:
            #         resume_stage = None

            # nierealne - zabralo by za duzo czasu
            # if resume_stage in [None, 'commits']:
            #     scream.ssay('Getting commits of a repo')
            #     '2. Liczba commit'
            #     try:
            #         commits = repository.get_commits()
            #         repo_commits = []
            #         for commit in commits:
            #             repo_commits.append(commit)
            #             comments = commit.get_comments()
            #             commit_comments = []
            #             for comment in comments:
            #                 commit_comments.append(comment)
            #                 check_quota_limit()
            #             statuses = commit.get_statuses()
            #             commit_statuses = []
            #             for status in statuses:
            #                 commit_statuses.append(status)
            #                 check_quota_limit()
            #             'IMHO output to CSV already here...'
            #             output_commit_comments(commit_comments, commit.sha)
            #             output_commit_statuses(commit_statuses, commit.sha)
            #             output_commit_stats(commit.stats, commit.sha)
            #         repo.setCommits(repo_commits)
            #         scream.log('Added commits of count: ' + str(len(repo_commits)) +
            #                    ' to a repo ' + key)
            #     except GithubException as e:
            #         if 'repo_commits' not in locals():
            #             repo.setCommits([])
            #         scream.log_error('Paginating through comments, ' +
            #                          'comment comments or statuses' +
            #                          ' gave error. Try again? ' + key +
            #                          ', error({0}): {1}'.
            #                          format(e.status, e.data))
            #     finally:
            #         resume_stage = None

            # '3. Liczba Commit w poszczegolnych skill (wiele zmiennych)'
            # 'there is no evidence for existance in GitHub API'
            # 'of a function for getting skill stats in a commit'
            # 'TO DO: implement a workaround with BEAUTIFUL SOUP'

            # if resume_stage in [None, 'stargazers']:
            #     scream.ssay('Getting stargazers of a repo')
            #     '4. Liczba gwiazdek  (to zostanie uzyte jako jakosc zespolu)'
            #     stargazers = repository.get_stargazers()
            #     repo_stargazers = []
            #     for stargazer in stargazers:
            #         repo_stargazers.append(stargazer)
            #         check_quota_limit()
            #     repo.setStargazers(repo_stargazers)
            #     scream.log('Added stargazers of count: ' + str(len(repo_stargazers)) +
            #                ' to a repo ' + key)
            #     resume_stage = None

            # scream.say('Persisting a repo to CSV output...')

            # 'handle here writing to output, dont make it at end when stack'
            # 'is full of repos, but do it a repo by repo...'
            # output_data(repo)

            scream.ssay('Finished processing repo: ' + key + '.. moving on... ')

            #del repos[key]
            'Dictionary cannot change size during iteration'
            'TO DO: associated fields purge so GC will finish the job'
            'implement reset() in intelliRepository.py'
            #scream.ssay('(' + key + ' deleted)')

            # limit = gh.get_rate_limit()

            # scream.ssay('Rate limit (after whole repo is processed): ' +
            #             str(limit.rate.limit) +
            #             ' remaining: ' + str(limit.rate.remaining))

            # reset_time = gh.rate_limiting_resettime
            # reset_time_human_readable = (datetime.datetime.fromtimestamp(
            #                              int(reset_time)).strftime(
            #                              '%Y-%m-%d %H:%M:%S')
            #                              )
            # scream.ssay('Rate limit reset time is exactly: ' +
            #             str(reset_time) + ' which means: ' +
            #             reset_time_human_readable)

            # if iteration_step_count % 5 == 0:
            #     intelliNotifications.report_quota(str(limit.rate.limit),
            #                                       str(limit.rate.remaining))

            # if limit.rate.remaining < 15:
            #     freeze_more()
