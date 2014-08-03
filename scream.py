import sys
import logging
import logging.config
from termcolor import colored
import portalocker

DISABLE__STD = False

logging.config.fileConfig('logging.conf')
logger = logging.getLogger(__name__)

intelliTag_verbose = True


def log(s):
    if intelliTag_verbose:
        logger.info(str(s))


def say(s):
    if intelliTag_verbose:
        print str(s)


def cout(s):
    if intelliTag_verbose:
        print str(s)


def progress_bar(current, left):
    with open('progress_bar.lock', 'w') as lockfile:
        portalocker.lock(lockfile, portalocker.LOCK_EX)
        progress = 1600 * (current/left)
        lockfile.write('[{0}] {1}%'.format('#' * (progress / 40), progress * 1600 * 100))
        portalocker.unlock(lockfile)


def ssay(s, current=None, left=None):
    if type(current) is str:
        current = int(current)
    if type(left) is str:
        left = int(left)

    if current is not None:
        progress_bar(current, left)
    if intelliTag_verbose:
        print colored(str(s), 'green')
        logger.info(str(s))


def log_error(s, cmd):
    if intelliTag_verbose:
        if cmd:
            print colored(str(s), 'red')
        logger.error(s)


def log_warning(s, cmd):
    if intelliTag_verbose:
        if cmd:
            print colored(str(s), 'yellow')
        logger.warning(s)


def log_debug(s, cmd):
    if intelliTag_verbose:
        if cmd:
            print colored(str(s), 'blue')
        logger.debug(s)


def std_write(s):
    if (intelliTag_verbose) and (not DISABLE__STD):
        sys.stdout.write(s)
        sys.stdout.flush()
