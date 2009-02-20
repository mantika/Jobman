from __future__ import with_statement

import signal
import sys
import os
import traceback

from tools import *



################################################################################
### JobError
################################################################################

class JobError(Exception):
    RUNNING = 0
    DONE = 1
    NOJOB = 2


################################################################################
### Channel base class
################################################################################

class Channel(object):

    COMPLETE = property(lambda s:None,
            doc=("Experiments should return this value to "
                "indicate that they are done (if not done, return `Incomplete`"))
    INCOMPLETE = property(lambda s:True,
            doc=("Experiments should return this value to indicate that "
            "they are not done (if done return `COMPLETE`)"))

    START = property(lambda s: 0,
            doc="dbdict.status == START means a experiment is ready to run")
    RUNNING = property(lambda s: 1,
            doc="dbdict.status == RUNNING means a experiment is running on dbdict_hostname")
    DONE = property(lambda s: 2,
            doc="dbdict.status == DONE means a experiment has completed (not necessarily successfully)")

    # Methods to be used by the experiment to communicate with the channel

    def save(self):
        """
        Save the experiment's state to the various media supported by
        the Channel.
        """
        raise NotImplementedError()

    def switch(self, message = None):
        """
        Called from the experiment to give the control back to the channel.
        The following return values are meaningful:
          * 'stop' -> the experiment must stop as soon as possible. It may save what
            it needs to save. This occurs when SIGTERM or SIGINT are sent (or in
            user-defined circumstances).
        switch() may give the control to the user. In this case, the user may
        resume the experiment by calling switch() again. If an argument is given
        by the user, it will be relayed to the experiment.
        """
        pass

    def __call__(self, message = None):
        return self.switch(message)

    def save_and_switch(self):
        self.save()
        self.switch()

    # Methods to run the experiment

    def setup(self):
        pass

    def __enter__(self):
        pass

    def __exit__(self):
        pass

    def run(self):
        pass


################################################################################
### Channel for a single experiment
################################################################################

class SingleChannel(Channel):

    def __init__(self, experiment, state):
        self.experiment = experiment
        self.state = state
        self.feedback = None

        #TODO: make this a property and disallow changing it during a with block
        self.catch_sigterm = True
        self.catch_sigint = True

    def switch(self, message = None):
        feedback = self.feedback
        self.feedback = None
        return feedback

    def run(self, force = False):
        self.setup()

        status = self.state.dbdict.get('status', self.START)
        if status is self.DONE and not force:
            # If you want to disregard this, use the --force flag (not yet implemented)
            raise JobError(JobError.RUNNING,
                           'The job has already completed.')
        elif status is self.RUNNING and not force:
            raise JobError(JobError.DONE,
                           'The job is already running.')
        self.state.dbdict.status = self.RUNNING

        v = self.COMPLETE
        with self: #calls __enter__ and then __exit__
            try:
                v = self.experiment(self.state, self)
            finally:
                self.state.dbdict.status = self.DONE if v is self.COMPLETE else self.START

        return v

    def on_sigterm(self, signo, frame):
        # SIGTERM handler. It is the experiment function's responsibility to
        # call switch() often enough to get this feedback.
        self.feedback = 'stop'

    def __enter__(self):
        # install a SIGTERM handler that asks the experiment function to return
        # the next time it will call switch()
        if self.catch_sigterm:
            self.prev_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, self.on_sigterm)
        if self.catch_sigint:
            self.prev_sigint = signal.getsignal(signal.SIGINT)
            signal.signal(signal.SIGINT, self.on_sigterm)
        return self

    def __exit__(self, type, value, tb_traceback, save = True):
        if type:
            try:
                raise type, value, tb_traceback
            except:
                traceback.print_exc()
        if self.catch_sigterm:
            signal.signal(signal.SIGTERM, self.prev_sigterm)
            self.prev_sigterm = None
        if self.catch_sigint:
            signal.signal(signal.SIGINT, self.prev_sigint)
            self.prev_sigint = None
        if save:
            self.save()
        return True


################################################################################
### Standard channel (with a path for the workdir)
################################################################################

class StandardChannel(SingleChannel):

    def __init__(self, path, experiment, state, redirect_stdout = False, redirect_stderr = False):
        super(StandardChannel, self).__init__(experiment, state)
        self.path = os.path.realpath(path)
        self.redirect_stdout = redirect_stdout
        self.redirect_stderr = redirect_stderr

    def realpath(self, path):
        if os.getcwd() == self.path:
            os.chdir(self.old_cwd)
            x = os.path.realpath(path)
            os.chdir(self.path)
            return x
        else:
            return os.path.realpath(path)

    def save(self):
        with open(os.path.join(self.path, 'current.conf'), 'w') as current:
            current.write(format_d(self.state))
            current.write('\n')

    def __enter__(self):
        self.old_cwd = os.getcwd()
        os.chdir(self.path)
        if self.redirect_stdout:
            self.old_stdout = sys.stdout
            sys.stdout = open('stdout', 'a')
        if self.redirect_stderr:
            self.old_stderr = sys.stderr
            sys.stderr = open('stderr', 'a')
        return super(StandardChannel, self).__enter__()

    def __exit__(self, type, value, traceback):
        rval = super(StandardChannel, self).__exit__(type, value, traceback, save = False)
        if self.redirect_stdout:
            sys.stdout.close()
            sys.stdout = self.old_stdout
        if self.redirect_stderr:
            sys.stderr.close()
            sys.stderr = self.old_stderr
        os.chdir(self.old_cwd)
        self.save()
        return rval

    def setup(self):
        if not os.path.isdir(self.path):
            os.makedirs(self.path)
        with self:
            origf = os.path.join(self.path, 'orig.conf')
            if not os.path.isfile(origf):
                with open(origf, 'w') as orig:
                    orig.write(format_d(self.state))
                    orig.write('\n')
            currentf = os.path.join(self.path, 'current.conf')
            if os.path.isfile(currentf):
                with open(currentf, 'r') as current:
                    state = expand(parse(*map(str.strip, current.readlines())))
                    defaults_merge(self.state, state)
