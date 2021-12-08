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
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration(distributed=False)

class PurgeBacklog(GeneratingCommand):

    def generate(self, **kwargs):

        if self:

            # Get the session key
            session_key = self._metadata.searchinfo.session_key

            # Get splunkd port
            entity = splunk.entity.getEntity('/server', 'settings',
                                                namespace='TA-dhl-mq', sessionKey=session_key, owner='-')
            splunkd_port = entity['mgmtHostPort']

            # log all actions
            SPLUNK_HOME = os.environ["SPLUNK_HOME"]
            splunklogfile = SPLUNK_HOME + "/var/log/splunk/mq_publish_purge_kvstore_backlog.log"

            # Get conf
            conf_file = "ta_dhl_mq_settings"
            confs = self.service.confs[str(conf_file)]
            mqpassthrough = "disabled"
            kvstore_eviction = None
            kvstore_retention = None
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value
                        if key == "kvstore_eviction":
                            kvstore_eviction = value
                        if key == "kvstore_retention":
                            kvstore_retention = value
        
            # Define the headers
            header = 'Splunk ' + str(session_key)

            # Define the url
            url = "https://localhost:" + str(splunkd_port) + "/services/search/jobs/export"

            if mqpassthrough != 'enabled':

                # yield
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This report is designed to be running on the SHC nodes only, it can be safety disabled on consumers if necessary.\"}"}
                yield data

            elif mqpassthrough == 'enabled' and kvstore_eviction and kvstore_retention:

                # local service
                service = client.connect(
                    token=str(session_key),
                    owner="nobody",
                    app="TA-dhl-mq",
                    host="localhost",
                    port=splunkd_port
                )

                # local cache record submitted
                backlog_kvstore_name = "kv_mq_publish_backlog"
                backlog_kvstore = service.kvstore[backlog_kvstore_name]

                # Get data, purge any record older than 48 hours
                search = "| inputlookup mq_publish_backlog | eval key=_key"

                # complete the search dynamically with the parameters defined on the search head(s)
                if str(kvstore_eviction) == 'delete':
                    search = str(search) + "| where (status=\"success\" OR status=\"canceled\" OR status=\"permanent_failure\")"
                else:
                    search = str(search) + "| where (status=\"success\" OR status=\"canceled\" OR status=\"permanent_failure\")" + '| eval record_age=now()-ctime | eval retention=' + str(kvstore_retention) + '*3600 | where record_age>retention'

                self.logger.fatal(search)

                output_mode = "csv"
                exec_mode = "oneshot"
                response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
                csv_data = response.text

                # Use the CSV dict reader
                readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

                # For row in CSV, generate the _raw
                for row in readCSV:                    

                    try:
                        backlog_kvstore.data.delete(json.dumps({"_key": str(row['key'])}))

                        # get the record age in seconds
                        record_age = int(round(float(time.time()) - float(row['ctime']), 0))

                        # Set the raw message
                        raw = "purged record=" + str(row['key']) + " with status=" + str(row['status']) + ", batch_uuid=" + str(row['batch_uuid']) + ", ctime=" + str(row['ctime']) + ", record_age=" + str(record_age)

                        # write to log file
                        outputlog = open(splunklogfile, "a")
                        t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                        raw_kv_message = 'action=\"success"' \
                            + '\", ' + str(raw)
                        outputlog.write(str(t[:-3]) + " INFO file=purgebacklog.py | customaction - signature=\"purgebacklog custom command called, " + str(raw_kv_message) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\"\n")
                        outputlog.close()

                        # yield as output of the generation command
                        yield {'_time': time.time(), '_raw': str(raw)}

                    except Exception as e:
                        msg = "KVstore record with key: " + str(row['key']) + " failed to be deleted with exception: " + str(e)
                        self.logger.fatal(msg)

                        # write to log file
                        outputlog = open(splunklogfile, "a")
                        t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                        raw_kv_message = 'action=\"failure"' \
                            + '\", ' + str(raw)
                        outputlog.write(str(t[:-3]) + " INFO file=purgebacklog.py | customaction - signature=\"purgebacklog custom command called, " + str(msg) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\"\n")
                        outputlog.close()

                        data = {'_time': time.time(), '_raw': "{\"response\": \"" + msg + "}"}
                        yield data
                        sys.exit(1)

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(PurgeBacklog, sys.argv, sys.stdin, sys.stdout, __name__)
