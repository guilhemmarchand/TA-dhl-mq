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

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration(distributed=False)

class GetMqReplay(GeneratingCommand):


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
            kvstore_instance = None
            bearer_token = None
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value
                        if key == "kvstore_instance":
                            kvstore_instance = value
                        if key == "bearer_token":
                            bearer_token = value
                        if key == "kvstore_search_filters":
                            kvstore_search_filters = value
                        if key == "mqclient_bin_path":
                            mqclient_bin_path = value
                        if key == "q_bin_path":
                            q_bin_path = value
                        

            # Define the headers, use bearer token if instance is not local
            if str(kvstore_instance) != "localhost:8089":
                header = 'Bearer ' + str(bearer_token)
            else:
                header = 'Splunk ' + str(session_key)

            # Define the url
            url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

            # Get data
            search = "| inputlookup mq_publish_backlog"

            # if mqpassthrough is enabled, search for successful records only
            if str(mqpassthrough) == 'enabled':
                search = str(search) + " where status=\"success\""
            elif kvstore_search_filters:
                search = str(search) + " where status!=\"success\" | search " + str(kvstore_search_filters)
            output_mode = "csv"
            exec_mode = "oneshot"
            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
            csv_data = response.text

            # first, let's create a folder to temporary store our batch files
            SPLUNK_HOME = os.environ["SPLUNK_HOME"]
            batchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/massbatch"
            if not os.path.isdir(batchfolder):
                try:
                    os.makedirs(batchfolder)
                except Exception as e:
                    self.logger.fatal('batch folder coult not be created!: %s', self)  # logs command line

            # generate a random uuid to name the batch
            import uuid
            uuid = uuid.uuid4()

            # Generate Shell and batch files
            splunklogfile = SPLUNK_HOME + "/var/log/splunk/mq_publish_message_relay_massbatch.log"

            mqchannel = "DEV.APP.SVRCONN"
            mqhost = "mq1"
            mqport = "1414"

            # Use the CSV dict reader
            readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=','.encode('utf-8'), quotechar='"'.encode('utf-8'))

            #
            # IN RECORDS
            #

            # For row in CSV, generate the _raw
            for row in readCSV:

                # dynamic destination
                deststr = "@" + str(row['manager']) + "@" + str(row['queue']) + "@"
                destfile = str(batchfolder) + "/" + str(deststr) + ".raw"
                destkeys = str(batchfolder) + "/" + str(deststr) + ".keys"
                destlog = str(batchfolder) + "/" + str(deststr) + ".log"

                # append to the batchfile
                with open(str(destfile), 'a') as f:
                    f.write(str(row['message']))

                # write keys to the log file
                with open(str(destkeys), 'a') as f:
                    f.write(str(row['_key']) + "\n")
                
                # append to the logfile
                with open(str(destlog), 'a') as f:
                    logmsg = "queue_manager=" + str(row['manager']) \
                        + ", queue=" + str(row['queue']) \
                        + ", appname=" + str(row['appname']) + ", region=" + str(row['region']) \
                        + ", key=" + str(row['_key']) + "\n"
                    f.write(str(logmsg))

            #
            # OUT RECORDS
            #

            # iterate through the generated batches, create a shell wrapper, send and update the records
            for filename in os.listdir(batchfolder):            
                if filename.endswith(".raw"):
                    
                    # extract the manager and queue dest
                    mqmanager = re.split("[\@]", str(filename))[-3]
                    mqqueuedest = re.split("[\@]", str(filename))[-2]

                    # our shell wrapper
                    shellbatchname = str(batchfolder) + "/" + str(uuid) + "-wrapper.sh"

                    # our shell script content
                    shellcontent = '#!/bin/bash\n' +\
                    '. ' + str(mqclient_bin_path) + '/bin/setmqenv -s\n' +\
                    'export MQSERVER=\"' + str(mqchannel) + '/TCP/' + str(mqhost) + '(' + str(mqport) + ')\"\n' +\
                    str(q_bin_path) + '/q -m ' + str(mqmanager) + ' -l mqic -o ' + str(mqqueuedest) + ' -f ' + str(batchfolder) + "/" + str(filename) + '\n' +\
                    'RETCODE=$?\n' +\
                    'if [ $RETCODE -ne 0 ]; then\n' +\
                    'echo "Failure with exit code $RETCODE"\n' +\
                    'else\n' +\
                    'echo "Success"\n' +\
                    'fi\n' +\
                    'exit $RETCODE'

                    if os.path.isfile(str(shellbatchname)):
                        os.remove(str(shellbatchname))
                    else:
                        with open(str(shellbatchname), 'w') as f:
                            f.write(shellcontent)
                        os.chmod(str(shellbatchname), 0o740)

                    # Execute the Shell batch now
                    output = subprocess.check_output([str(shellbatchname)],universal_newlines=True)

                    # purge both files
                    os.remove(str(shellbatchname))
                    os.remove(str(batchfolder) + "/" + str(filename))

                    # load the record list from the file
                    keys_list = open(str(batchfolder) + "/" + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.keys").read().splitlines()
                    count = 0
                    search_filter = ""
                    # create a search filter
                    for key_record in keys_list:
                        count +=1
                        if count>1:
                            search_filter = str(search_filter) + " OR _key=\"" + str(key_record) + "\""
                        else:
                            search_filter = "_key=\"" + str(key_record) + "\""

                    # From the output of the subprocess, determine the publication status
                    # If an exception was raised, it will be added to the error message
                    if "Success" in str(output):
                        self.logger.fatal('success!: %s', self)
                        self.logger.fatal(str(search_filter), self)

                        search = "| inputlookup mq_publish_backlog where (" + str(search_filter) + ") | eval key=_key, status=\"success\", mtime=now() | outputlookup mq_publish_backlog append=t key_field=key | stats c"
                        output_mode = "csv"
                        exec_mode = "oneshot"
                        response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                        if response.status_code not in (200, 201, 204):
                            self.logger.fatal('Error in KVstore mass update!: %s', self)

                        # log
                        inputlog = open(str(batchfolder) + "/" + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.log", "r")
                        outputlog = open(splunklogfile, "a")
                        import datetime
                        t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                        for line in inputlog:
                            outputlog.write(str(t[:-3]) + " INFO file=sendmq.py | customaction - signature=\"message publication success, " + str(line.strip()) + ", app=\"TA-dhl-mq\" user=\"admin\" action_mode=\"saved\" action_status=\"success\"\"\n")
                        inputlog.close()
                        outputlog.close()

                    else:
                        self.logger.fatal('MQ send has failed!: %s', self)
                        self.logger.fatal(str(search_filter), self)

                        search = str(search) + " where (" + str(search_filter) + ") | eval key=_key, status=\"temporary_failure\", mtime=now(), no_attempts=\"1\" | outputlookup mq_publish_backlog append=t key_field=key | stats c"

                        output_mode = "csv"
                        exec_mode = "oneshot"
                        response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                        if response.status_code not in (200, 201, 204):
                            self.logger.fatal('Error in KVstore mass update!: %s', self)

                        # log
                        inputlog = open(str(batchfolder) + "/" + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.log", "r")
                        outputlog = open(splunklogfile, "a")
                        import datetime
                        t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                        for line in inputlog:
                            outputlog.write(str(t[:-3]) + " ERROR file=sendmq.py | customaction - signature=\"message publication success, " + str(line.strip()) + ", app=\"TA-dhl-mq\" user=\"admin\" action_mode=\"saved\" action_status=\"failure\"\"\n")
                        inputlog.close()
                        outputlog.close()

                        # output a report to Splunk
                        data = {'_time': time.time(), '_raw': "{\"response\": \"" + "MQ send successful}"}
                        yield data

                    # remove log and keys
                    os.remove(str(batchfolder) + "/" + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.keys")
                    os.remove(str(batchfolder) + "/" + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.log")

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(GetMqReplay, sys.argv, sys.stdin, sys.stdout, __name__)
