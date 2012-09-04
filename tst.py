import logging
import sys

logger = logging.getLogger('')

class Myhandler(logging.Handler):
    def emit(self, record):
        print >>sys.stderr, 'emit: ' + record.getMessage()
        print 'dir(record) = {0}'.format(dir(record))
        print >>sys.stderr, 'levelname: ' + record.levelname
        print >>sys.stderr, 'levelno: {0}'.format(record.levelno)

logger.addHandler(Myhandler())

if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    logger.debug('this is a test')
