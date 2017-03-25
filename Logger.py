'''
    Created on 17 Jul 2016
    @author: Tom

    A small logger class to commit application output to file.

'''
import os
from datetime import datetime

class Logger(object):

    LOG_DIR = ""

    def log(self, line):

        #Get out current date & time and format it to look nice.
        date = datetime.today().strftime("%Y-%m-%d")
        timestamp = "[" + datetime.now().time().strftime("%H:%M") + "] "

        #Open the relevant log file in append mode.
        myFile = open(self.LOG_DIR + "/" + date + ".txt", 'a')

        #Put a timestamp on the string to be logged.
        line = timestamp + line.replace('\n', '\n' + ' ' * len(timestamp))

        print(line)                  #Log it in console...
        myFile.write(line + "\n")    #...and in our text files.

        #Close 'er up. We're done here.
        myFile.close()

    def __init__(self, LOG_DIR):

        self.LOG_DIR = LOG_DIR

        if not (os.path.exists(LOG_DIR) and os.path.isdir(LOG_DIR)):
            os.mkdir(LOG_DIR)
