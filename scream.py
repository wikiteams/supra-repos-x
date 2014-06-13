import sys
import logging
import logging.handlers
import logging.config

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


def ssay(s):
    if intelliTag_verbose:
        print str(s)
        logger.info(str(s))


def log_error(s):
    if intelliTag_verbose:
        logger.error(s)


def log_warning(s):
    if intelliTag_verbose:
        logger.warning(s)


def log_debug(s):
    if intelliTag_verbose:
        logger.debug(s)


def std_write(s):
    if (intelliTag_verbose) and (not DISABLE__STD):
        sys.stdout.write(s)
        sys.stdout.flush()
