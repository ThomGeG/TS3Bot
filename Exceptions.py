'''
Created on 4 Jul 2016

@author: Tom
'''

class IllegalStateException(Exception):
    '''
    Signals that a method has been invoked at an inappropriate time.
    In other words, the application/environment is not in an appropriate state for the requested operation.
    '''

    def __init__(self, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)

class TS3Exception(Exception):
    '''
    TS3 threw an exception, so I'm throwing it to you...
    '''
    error_ID = -1

    def __init__(self, message, error_ID):
        self.errorID = error_ID
        super(Exception, self).__init__(message)
