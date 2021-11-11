#!/usr/bin/env python
# coding=utf-8

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
import hashlib
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

class GetHaGroups(GeneratingCommand):


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

            if str(mqpassthrough) == 'enabled':
                # output a report to Splunk
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This instance is configured in passthrough mode, you can disable the execution of the search.}"}
                yield data
                sys.exit(0)

            else:

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

                # Set header
                header = 'Bearer ' + str(bearer_token)

                # Set url
                url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

                # create or update the record
                search = "| inputlookup mq_publish_ha_groups | eval key=_key"
                output_mode = "csv"
                exec_mode = "oneshot"
                response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
                csv_data = response.text

                if response.status_code not in (200, 201, 204):
                    logmsg = "sending keepalive has failed, server response: " + str(response.text)
                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(logmsg) + "\"}"}
                    yield data
                    sys.exit(0)

                else:

                    # Use the CSV dict reader
                    readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

                    #
                    # IN RECORDS
                    #

                    # For row in CSV, generate the _raw
                    for row in readCSV:
                        yield {'_time': time.time(), '_raw': json.dumps(row)}
        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data

dispatch(GetHaGroups, sys.argv, sys.stdin, sys.stdout, __name__)
