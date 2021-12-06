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
import csv
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration(distributed=False)

class PurgeLocalCache(GeneratingCommand):

    max_age = Option(
        doc='''
        **Syntax:** **max_age=****
        **Description:** max age of the records to be purged. (in seconds)''',
        require=True)

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
            storage_passwords = self.service.storage_passwords
            mqpassthrough = "disabled"
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value
        
            # Define the headers
            header = 'Splunk ' + str(session_key)

            # Define the url
            url = "https://localhost:" + str(splunkd_port) + "/services/search/jobs/export"

            if mqpassthrough == 'enabled':

                # yield
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This report is designed to be running on the consumer nodes only, it can be safety disabled.\"}"}
                yield data

            else:

                # local service
                service = client.connect(
                    token=str(session_key),
                    owner="nobody",
                    app="TA-dhl-mq",
                    host="localhost",
                    port=splunkd_port
                )

                # local cache record submitted
                local_cache_records_submitted_name = "kv_mq_publish_local_cache_records_submitted"
                local_cache_records_submitted = service.kvstore[local_cache_records_submitted_name]

                # Get data, purge any record older than 48 hours
                search = "| inputlookup mq_publish_local_cache_records_submitted | eval key=_key | eval record_age=now()-ctime | where record_age>" + str(self.max_age)
                output_mode = "csv"
                exec_mode = "oneshot"
                response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
                csv_data = response.text

                # Use the CSV dict reader
                readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

                # For row in CSV, generate the _raw
                for row in readCSV:                    
                    try:
                        local_cache_records_submitted.data.delete(json.dumps({"_key": str(row['key'])}))
                        raw = "purged record=" + str(row['key']) + " with status=" + str(row['status']) + ", ctime=" + str(row['ctime'])
                        yield {'_time': time.time(), '_raw': str(raw)}
                    except Exception as e:
                        msg = "KVstore record with key: " + str(row['key']) + " failed to be deleted with exception: " + str(e)
                        self.logger.fatal(msg)
                        data = {'_time': time.time(), '_raw': "{\"response\": \"" + msg + "}"}
                        yield data
                        sys.exit(1)

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(PurgeLocalCache, sys.argv, sys.stdin, sys.stdout, __name__)
