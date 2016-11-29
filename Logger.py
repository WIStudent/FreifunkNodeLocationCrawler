from threading import RLock, Thread
from time import time
from datetime import datetime

class Logger(object):
    def __init__(self, filename, print_to_console=False):
        self.filename = filename
        self.print_to_console = print_to_console
        self.lock = RLock()
        # Delete old file content
        open(filename, 'w').close()

    def log(self, string):
        self.lock.acquire()
        with open(self.filename, 'a') as file:
            timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d %H:%M:%S.%f')
            file.write(timestamp + ': ' + string + '\n')
            if self.print_to_console:
                print(timestamp + ': ' + string + '\n')
        file.close()
        self.lock.release()


def testLogger(logger, threadname):
    for i in range(0, 10):
        logger.log(threadname + ': ' + str(i))


def main():
    # Create new Logger
    logger = Logger('testlog.txt')
    thread1 = Thread(target=testLogger, args=(logger, 'Thread A'))
    thread2 = Thread(target=testLogger, args=(logger, 'Thread B'))
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

if __name__ == '__main__':
    main()