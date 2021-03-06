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
import json
import subprocess
import uuid
import re
import socket
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client
from solnlib import conf_manager

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

            # my hostname
            myhostname = socket.gethostname()

            # Get conf
            conf_file = "ta_dhl_mq_settings"
            confs = self.service.confs[str(conf_file)]
            storage_passwords = self.service.storage_passwords
            kvstore_instance = None
            bearer_token = None
            ha_group = None
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value
                        if key == "kvstore_instance":
                            kvstore_instance = value
                        if key == "kvstore_search_filters":
                            kvstore_search_filters = value
                        if key == "mqclient_bin_path":
                            mqclient_bin_path = value
                        if key == "q_bin_path":
                            q_bin_path = value
                        if key == "ha_group":
                            ha_group = value

            # Define the headers, use bearer token if instance is not local
            if str(kvstore_instance) != "localhost:8089":

                # The bearer token is stored in the credential store
                # However, likely due to the number of chars, the credential.content.get SDK command is unable to return its value in a single operation
                # As a workaround, we concatenate the different values return to form a complete object, finally we use a regex approach to extract its clear text value
                credential_realm = '__REST_CREDENTIAL__#TA-dhl-mq#configs/conf-ta_dhl_mq_settings'
                bearer_token_rawvalue = ""

                for credential in storage_passwords:
                    if credential.content.get('realm') == str(credential_realm):
                        bearer_token_rawvalue = bearer_token_rawvalue + str(credential.content.clear_password)

                # extract a clean json object
                bearer_token_rawvalue_match = re.search('\{\"bearer_token\":\s*\"(.*)\"\}', bearer_token_rawvalue)
                if bearer_token_rawvalue_match:
                    bearer_token = bearer_token_rawvalue_match.group(1)
                else:
                    bearer_token = None

                header = 'Bearer ' + str(bearer_token)

                # Verify the HA group, if is unset, it will be equal to the hostname of the consumer
                if not ha_group:
                    ha_group = myhostname

            else:
                header = 'Splunk ' + str(session_key)

            # Define the url
            url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

            # Get data
            search = "| inputlookup mq_publish_backlog"

            # if mqpassthrough is enabled we have nothing to do
            if str(mqpassthrough) == 'enabled':
                # output a report to Splunk
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This instance is configured in passthrough mode, you can disable the execution of the search.}"}
                yield data
                sys.exit(0)
            elif kvstore_search_filters:
                search = str(search) + " where (status=\"pending\" validation_required=0 AND multiline=0 AND no_attempts=0) | head 10000 | search " + str(kvstore_search_filters)
            output_mode = "csv"
            exec_mode = "oneshot"
            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
            csv_data = response.text

            # local cache service
            ha_group_collection_name = "kv_mq_publish_local_cache_ha_groups"
            service = client.connect(
                token=str(session_key),
                owner="nobody",
                app="TA-dhl-mq",
                host="localhost",
                port=splunkd_port
            )
            ha_group_collection = service.kvstore[ha_group_collection_name]

            # get the existing record, if any
            query_string = '{ "ha_group_name": "' + str(ha_group) + '" }'
            record = None
            try:
                record = ha_group_collection.data.query(query=str(query_string))

            except Exception as e:
                record = None

            # Proceed
            ha_group_elected_manager = None
            ha_group_elected_manager = record[0].get('ha_group_elected_manager')

            # Only proceed either we run in standalone, or we are the manager
            if ha_group_elected_manager:

                if str(ha_group_elected_manager) != str(myhostname):

                    data = {'_time': time.time(), '_raw': "{\"response\": \"Nothing to do, this consumer is not the current manager for the HA group " \
                        + str(ha_group) + ", the current manager is: " + str(ha_group_elected_manager) + "\"}"}
                    yield data
                    sys.exit(0)
            
            # first, let's create a folder to temporary store our batch files
            SPLUNK_HOME = os.environ["SPLUNK_HOME"]
            batchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/massbatch"
            if not os.path.isdir(batchfolder):
                try:
                    os.makedirs(batchfolder)
                except Exception as e:
                    self.logger.fatal('batch folder coult not be created!: %s', self)  # logs command line
                    sys.exit(1)

            # generate a random uuid to name the batch
            import uuid
            uuid = uuid.uuid4()

            # Generate Shell and batch files
            splunklogfile = SPLUNK_HOME + "/var/log/splunk/mq_publish_message_relay_massbatch.log"

            # Use the CSV dict reader
            readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

            #
            # IN RECORDS
            #

            # For row in CSV, generate the _raw
            for row in readCSV:

                # dynamic destination
                deststr = "@" + str(uuid) + "@" + str(row['manager']) + "@" + str(row['queue']) + "@"
                destfile = str(batchfolder) + "/" + str(deststr) + ".raw"
                destkeys = str(batchfolder) + "/" + str(deststr) + ".keys"
                destlog = str(batchfolder) + "/" + str(deststr) + ".log"

                # append to the batchfile
                with open(str(destfile), 'a') as f:
                    message=str(row['message']).strip('\n') + '\n'
                    message=message.replace('\\\"', '\"')
                    f.write(str(message))

                # write keys to the log file
                with open(str(destkeys), 'a') as f:
                    f.write(str(row['_key']) + "\n")
                
                # append to the logfile
                with open(str(destlog), 'a') as f:
                    logmsg = "queue_manager=" + str(row['manager']) \
                        + ", queue=" + str(row['queue']) \
                        + ", batch_uuid=" + str(row['batch_uuid']) \
                        + ", user=" + str(row['user']) \
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

                    # define associated files
                    instance_keyfile = str(batchfolder) + "/" + "@" + str(uuid) + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.keys"
                    instance_logfile = str(batchfolder) + "/" + "@" + str(uuid) + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.log"
                    instance_rawfile = str(batchfolder) + "/" + "@" + str(uuid) + "@" + str(mqmanager) + "@" + str(mqqueuedest) + "@.raw"

                    # get the configuration for this account
                    # Get conf, fail if does not exist
                    isfound = False
                    conf_file = "ta_dhl_mq_account"
                    confs = self.service.confs[str(conf_file)]
                    for stanza in confs:
                        if stanza.name == str(mqmanager):
                            isfound = True
                            for key, value in stanza.content.items():
                                if key == "mqchannel":
                                    mqchannel = value
                                if key == "mqhost":
                                    mqhost = value
                                if key == "mqport":
                                    mqport = value

                    # Send if the configuration allows it
                    if not isfound:
                        self.logger.fatal('This Queue manager has not been configured on this instance, cannot proceed!: %s', self)
                        # remove log and keys
                        os.remove(instance_keyfile)
                        os.remove(instance_logfile)
                        os.remove(instance_rawfile)

                    # proceed
                    else:

                        # our shell wrapper
                        shellbatchname = str(batchfolder) + "/" + str(uuid) + "-wrapper.sh"

                        # our shell script content
                        shellcontent = '#!/bin/bash\n' +\
                        '. ' + str(mqclient_bin_path) + '/bin/setmqenv -s\n' +\
                        'export MQSERVER=\"' + str(mqchannel) + '/TCP/' + str(mqhost) + '(' + str(mqport) + ')\"\n' +\
                        str(q_bin_path) + '/q -m ' + str(mqmanager) + ' -l mqic -o ' + str(mqqueuedest) + ' -f ' + str(batchfolder) + "/" + str(filename) + ' 2>&1\n' +\
                        'RETCODE=$?\n' +\
                        'if [ $RETCODE -ne 0 ]; then\n' +\
                        'echo "Failure with exit code $RETCODE"\n' +\
                        'else\n' +\
                        'echo "Success"\n' +\
                        'fi\n' +\
                        'exit 0'

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
                        keys_list = open(instance_keyfile).read().splitlines()
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

                            search = "| inputlookup mq_publish_backlog where (" + str(search_filter) + ") | eval key=_key, status=\"success\", mtime=now() | outputlookup mq_publish_backlog append=t key_field=key | stats c"
                            output_mode = "csv"
                            exec_mode = "oneshot"
                            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                            if response.status_code not in (200, 201, 204):
                                self.logger.fatal('Error in KVstore mass update!: %s', self)

                            # log
                            inputlog = open(instance_logfile, "r")
                            outputlog = open(splunklogfile, "a")
                            import datetime
                            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                            for line in inputlog:
                                outputlog.write(str(t[:-3]) + " INFO file=getmqbatch.py | customaction - signature=\"message publication success, " + str(line.strip()) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\" action_status=\"success\"\n")
                            inputlog.close()
                            outputlog.close()

                            # output a report to Splunk
                            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "MQ batch successful with " \
                                + str(count) + " messages processed, consult the logs for more information.}"}
                            yield data

                        else:
                            self.logger.fatal('MQ send has failed!: %s', self)
                            search = "| inputlookup mq_publish_backlog where (" + str(search_filter) + ") | eval key=_key, status=\"temporary_failure\", mtime=now(), no_attempts=\"1\" | outputlookup mq_publish_backlog append=t key_field=key | stats c"
                            # for logging
                            # self.logger.fatal(str(search))
                            output_mode = "csv"
                            exec_mode = "oneshot"
                            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                            if response.status_code not in (200, 201, 204):
                                self.logger.fatal('Error in KVstore mass update!: %s', self)

                            # log
                            inputlog = open(instance_logfile, "r")
                            outputlog = open(splunklogfile, "a")
                            import datetime
                            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                            for line in inputlog:
                                outputlog.write(str(t[:-3]) + " ERROR file=getmqbatch.py | customaction - signature=\"failure in message publication, " + str(line.strip()) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\" action_status=\"failure\"\n")
                            inputlog.close()
                            outputlog.close()

                            # output a report to Splunk
                            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "ERROR: MQ batch batch has failed, consult the logs for more information.}"}

                            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "ERROR: MQ batch has failed to process " \
                                + str(count) + " messages, consult the logs for more information.}"}
                            yield data


                        # remove log and keys
                        os.remove(instance_keyfile)
                        os.remove(instance_logfile)

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(GetMqReplay, sys.argv, sys.stdin, sys.stdout, __name__)
