#!/usr/bin/env python

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import splunk
import splunk.entity
import requests
import time
import datetime
import hashlib
import random
import json
import csv
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, StreamingCommand, Configuration, Option, validators
from splunklib import six
import splunklib.client as client

@Configuration()
class FlushRemoteRecords(StreamingCommand):

    field_remote_splsearch = Option(
        doc='''
        **Syntax:** **field_remote_splsearch=****
        **Description:** field name containing the remote spl search to be performed.''',
        require=True)

    field_local_splsearch = Option(
        doc='''
        **Syntax:** **field_local_splsearch=****
        **Description:** field name containing the local spl search to be performed.''',
        require=True)

    def stream(self, records):

        # Get the session key
        session_key = self._metadata.searchinfo.session_key

        # Get splunkd port
        entity = splunk.entity.getEntity('/server', 'settings',
                                            namespace='TA-dhl-mq', sessionKey=session_key, owner='-')
        splunkd_port = entity['mgmtHostPort']

        # home
        SPLUNK_HOME = os.environ["SPLUNK_HOME"]

        # Get conf
        conf_file = "ta_dhl_mq_settings"
        confs = self.service.confs[str(conf_file)]
        storage_passwords = self.service.storage_passwords
        kvstore_instance = None
        bearer_token = None
        for stanza in confs:
            if stanza.name == "advanced_configuration":
                for key, value in stanza.content.items():
                    if key == "kvstore_instance":
                        kvstore_instance = value
        
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
            local_header = 'Splunk ' + str(session_key)

            # run a Splunk control search, get the number of record matching the batch_uuid
            url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"
            local_url = "https://localhost:" + str(splunkd_port) + "/services/search/jobs/export"

            # loop in records (note: we expect one record only)
            for record in records:
            
                # Define and run a Splunk search
                search = str(record[self.field_remote_splsearch])
                self.logger.fatal(str(search))
                output_mode = "csv"
                exec_mode = "oneshot"
                response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                if response.status_code not in (200, 201, 204):
                    logmsg = "Remote KVstore update has failed, server response: " + str(response.text)
                    yield {'_time': time.time(), '_raw': str(logmsg)}

                else:
                    logmsg = "Remote KVstore update was successful, server response status code: " + str(response.status_code)

                    # run the local update
                    # Define and run a Splunk search
                    search = str(record[self.field_local_splsearch])
                    output_mode = "csv"
                    exec_mode = "oneshot"
                    response = requests.post(local_url, headers={'Authorization': local_header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                    # output the remote search results only
                    yield {'_time': time.time(), '_raw': str(logmsg)}

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This report is designed to be running on the consumer nodes only, it can be safety disabled.\"}"}
            yield data

dispatch(FlushRemoteRecords, sys.argv, sys.stdin, sys.stdout, __name__)
