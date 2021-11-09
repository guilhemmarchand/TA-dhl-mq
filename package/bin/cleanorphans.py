#!/usr/bin/env python
# coding=utf-8

# REST API SPL handler for TrackMe, allows interracting with the TrackMe API endpoints with get / post / delete calls
# See: https://trackme.readthedocs.io/en/latest/rest_api_reference.html

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import splunk
import splunk.entity
import requests
import time
import datetime
import csv
import subprocess
import uuid
import hashlib
import re
import glob
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client
from solnlib import conf_manager

@Configuration(distributed=False)

class CleanOrphans(GeneratingCommand):


    def generate(self, **kwargs):

        if self:

            # Get the session key
            session_key = self._metadata.searchinfo.session_key

            # Get splunkd port
            entity = splunk.entity.getEntity('/server', 'settings',
                                                namespace='TA-dhl-mq', sessionKey=session_key, owner='-')
            splunkd_port = entity['mgmtHostPort']

            # Get conf
            conf_file = "ta_dhl_mq_settings"
            confs = self.service.confs[str(conf_file)]
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value

            # if passthrough, do nothing
            if str(mqpassthrough) == 'enabled':
                # output a report to Splunk
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This instance is configured in passthrough mode, you can disable the execution of the search.}"}
                yield data
                sys.exit(0)

            # SPLUNK_HOME
            SPLUNK_HOME = os.environ["SPLUNK_HOME"]

            #
            # massbatch orphan files search and clean: batch files are not supposed to be remaining in the file system
            # we can safety remove any file in the folder older>1h
            #

            batchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/massbatch"
            clean_massbatch = False
            massbatch_files = 0
            massbatch_filespurged = 0
            # if the path does not exist, we have nothing to do for massbatch
            if not os.path.isdir(batchfolder):
                clean_massbatch = False
            else:
                clean_massbatch = True

            if clean_massbatch:

                # cd to directory, exit if we can't
                try:
                    os.chdir(batchfolder)
                except Exception as e:
                    self.logger.fatal('failed to chdir in: ' + str(batchfolder))
                    sys.exit(1)

                # Verify we have data to manage
                massbatch_files = len(glob.glob1(batchfolder, "*"))
                # self.logger.fatal('massbatch_files: ' + str(massbatch_files))

                # print (counter)
                if massbatch_files != 0:
                    # self.logger.fatal('handle files:')

                    for xfile in glob.glob('*'):
                        # removal logic

                        # refuse to remove a file younger than 15 minutes
                        filemtime = os.path.getmtime(xfile)
                        if time.time() - filemtime > 900:

                            try:
                                os.remove(xfile)
                                massbatch_filespurged +=1
                            except Exception as e:
                                self.logger.fatal('Failed to remove file! ' + xfile)

            batchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/batch"
            clean_singlebatch = False
            singlebatch_files = 0
            singlebatch_filespurged = 0
            # if the path does not exist, we have nothing to do for massbatch
            if not os.path.isdir(batchfolder):
                clean_singlebatch = False
            else:
                clean_singlebatch = True

            if clean_singlebatch:

                # cd to directory, exit if we can't
                try:
                    os.chdir(batchfolder)
                except Exception as e:
                    self.logger.fatal('failed to chdir in: ' + str(batchfolder))
                    sys.exit(1)

                # Verify we have data to manage
                singlebatch_files = len(glob.glob1(batchfolder, "*"))
                # self.logger.fatal('massbatch_files: ' + str(massbatch_files))

                # print (counter)
                if singlebatch_files != 0:
                    # self.logger.fatal('handle files:')

                    for xfile in glob.glob('*'):
                        # removal logic

                        # refuse to remove a file younger than 15 minutes
                        filemtime = os.path.getmtime(xfile)
                        if time.time() - filemtime > 900:

                            try:
                                os.remove(xfile)
                                singlebatch_filespurged +=1
                            except Exception as e:
                                self.logger.fatal('Failed to remove file! ' + xfile)

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Clean Orphans operation done, " + str(singlebatch_filespurged) + " file(s) were purged from the massbatch directory, " + str(singlebatch_filespurged) + " file(s) were purged from the batch directory\"}"}
            yield data

dispatch(CleanOrphans, sys.argv, sys.stdin, sys.stdout, __name__)
