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
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
            storage_passwords = self.service.storage_passwords
            kvstore_instance = None
            bearer_token = None
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value
                        if key == "kvstore_instance":
                            kvstore_instance = value
                        if key == "kvstore_search_filters":
                            kvstore_search_filters = value
                        if key == "kvstore_eviction":
                            kvstore_eviction = value
                        if key == "kvstore_retention":
                            kvstore_retention = value

            
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
            else:
                header = 'Splunk ' + str(session_key)

            # Define the url
            url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

            # Get data
            search = "| inputlookup mq_publish_backlog"

            # if mqpassthrough is enabled, search for successful records only
            if str(mqpassthrough) == 'enabled':            
                # optimization: to avoid Splunk using resources cycles, restrict to successful or canceled records depending on the eviction policy
                if str(kvstore_eviction) == 'delete':
                    search = str(search) + " where (status=\"success\" OR status=\"canceled\" OR status=\"permanent_failure\")"
                else:
                    search = str(search) + " where (status=\"success\" OR status=\"canceled\" OR status=\"permanent_failure\")" + '| eval record_age=now()-ctime | eval retention=' + str(kvstore_retention) + '*3600 | where record_age>retention'

            elif kvstore_search_filters:
                search = str(search) + " where (status!=\"success\" AND status!=\"canceled\" AND status!=\"permanent_failure\") | where (validation_required=0) AND ( (multiline=0 AND no_attempts>0) OR (multiline=1) ) | search " + str(kvstore_search_filters)

            # logging
            self.logger.fatal(str(search))
            output_mode = "csv"
            exec_mode = "oneshot"
            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
            csv_data = response.text

            # Use the CSV dict reader
            readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

            # For row in CSV, generate the _raw
            for row in readCSV:
                message = str(row['message']).replace('\\\"', '\"')
                yield {'_time': time.time(), '_raw': str(row), '_key': str(row['_key']), 'message': str(message), 'multiline': str(row['multiline']), 'appname': str(row['appname']), 'region': str(row['region']), 'ctime': str(row['ctime']), 'mtime': str(row['mtime']), 'manager': str(row['manager']), 'status': str(row['status']), 'queue': str(row['queue']), 'no_max_retry': str(row['no_max_retry']), 'no_attempts': str(row['no_attempts']), 'user': str(row['user']), 'batch_uuid': str(row['batch_uuid']), 'validation_required': str(row['validation_required'])}

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(GetMqReplay, sys.argv, sys.stdin, sys.stdout, __name__)
