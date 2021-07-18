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

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration(distributed=False)

class ManagePendingBatch(GeneratingCommand):

    batch_uuid = Option(
        doc='''
        **Syntax:** **batch_uuid=****
        **Description:** Unique identifier for the batch to be managed.''',
        require=True)

    def generate(self, **kwargs):

        if self:

            # Get the session key
            session_key = self._metadata.searchinfo.session_key

            # Get the current user        
            user = self._metadata.searchinfo.username

            # Get splunkd port
            entity = splunk.entity.getEntity('/server', 'settings',
                                                namespace='TA-dhl-mq', sessionKey=session_key, owner='-')
            splunkd_port = entity['mgmtHostPort']

            # log all actions
            SPLUNK_HOME = os.environ["SPLUNK_HOME"]
            splunklogfile = SPLUNK_HOME + "/var/log/splunk/mq_publish_message_managebatch.log"

            # Get conf
            conf_file = "ta_dhl_mq_settings"
            confs = self.service.confs[str(conf_file)]
            kvstore_instance = None
            bearer_token = None
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "kvstore_instance":
                            kvstore_instance = value
                        if key == "bearer_token":
                            bearer_token = value
            
            # Define the headers, use bearer token if instance is not local
            if str(kvstore_instance) != "localhost:8089":
                header = 'Bearer ' + str(bearer_token)
            else:
                header = 'Splunk ' + str(session_key)

            # Define the url
            url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

            # Define and run a Splunk search
            search = "| inputlookup mq_publish_backlog where validation_required=1 AND batch_uuid=\"" + str(self.batch_uuid) + "\"" \
                + " | eval key=_key | eval validation_required=0, mtime=now() | outputlookup append=t key_field=key mq_publish_backlog" \
                + " | stats values(region) as region, values(appname) as appname, values(validation_required) as validation_required, count, values(manager) as manager, values(queue) as queue by batch_uuid" \
                + " | eval action=if(count>0 AND validation_required=0, \"success\", \"failure\") | fields action, *"
            output_mode = "csv"
            exec_mode = "oneshot"
            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
            csv_data = response.text

            # Use the CSV dict reader
            readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=','.encode('utf-8'), quotechar='"'.encode('utf-8'))

            # For row in CSV, generate the _raw
            for row in readCSV:

                outputlog = open(splunklogfile, "a")
                t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                raw_kv_message = 'action=\"' + str(row['action']) \
                    + '\", count=\"' + str(row['count']) \
                    + '\", manager=\"' + str(row['manager']) \
                    + '\", queue=\"' + str(row['queue']) \
                    + '\", batch_uuid=\"' + str(row['batch_uuid']) \
                    + '\", region=\"' + str(row['region']) \
                    + '\", validation_required=\"' + str(row['validation_required']) \
                    + '\", user=\"' + str(user) + '\"'
                outputlog.write(str(t[:-3]) + " INFO file=managebatch.py | customaction - signature=\"managebatch custom command called, " + str(raw_kv_message) + "\", app=\"TA-dhl-mq\" user=\"admin\" action_mode=\"saved\" action_status=\"success\"\"\n")
                outputlog.close()

            yield {'_time': time.time(), '_raw': str(row), 'action': str(row['action']), 'appname': str(row['appname']), 'batch_uuid': str(row['batch_uuid']), 'count': str(row['count']), 'manager': str(row['manager']), 'queue': str(row['queue']), 'region': str(row['region']), 'validation_required': str(row['validation_required'])}

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(ManagePendingBatch, sys.argv, sys.stdin, sys.stdout, __name__)