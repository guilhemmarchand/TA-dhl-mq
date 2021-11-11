#!/usr/bin/env python
# coding=utf-8

# send keepalive

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import splunk
import splunk.entity
import requests
import time
import socket
import datetime
import json
import csv
import subprocess
import uuid
import hashlib
import re
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']
sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-dhl-mq', 'lib'))

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client
from solnlib import conf_manager

@Configuration(distributed=False)

class SendKeepAlive(GeneratingCommand):


    def generate(self, **kwargs):

        if self:

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
                        if key == "ha_group":
                            ha_group = value

            # If the ha_group is not defined, set it equal to the forwarder hostname
            if not ha_group:
                ha_group = socket.gethostname()

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

            # if mqpassthrough is enabled we have nothing to do
            if str(mqpassthrough) == 'enabled':
                # output a report to Splunk
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This instance is configured in passthrough mode, you can disable the execution of the search.\"}"}
                yield data
                sys.exit(0)

            else:
                # do something

                # set the header
                header = 'Bearer ' + str(bearer_token)

                # Define the url
                url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

                # get my hostname
                myhostname = socket.gethostname()

                # define a unique md5
                md5_str = str(myhostname)
                md5 = hashlib.md5(md5_str.encode('utf-8')).hexdigest()

                # create or update the record
                search = "| makeresults | eval key=\"" + str(md5) + "\", ha_group_name=\"" + str(ha_group) + "\", mtime=\"" + str(time.time()) + "\", consumer_name=\"" + str(myhostname) + "\" | fields - _time | outputlookup mq_publish_ha_consumers_keepalive append=t key_field=key"
                output_mode = "csv"
                exec_mode = "oneshot"
                response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                if response.status_code not in (200, 201, 204):
                    logmsg = "sending keepalive has failed, server response: " + str(response.text)
                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(logmsg) + "\"}"}
                    yield data
                    sys.exit(0)

                else:
                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + "keep alive sent successfully\"}"}
                    yield data
                    sys.exit(0)

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request\"}"}
            yield data

dispatch(SendKeepAlive, sys.argv, sys.stdin, sys.stdout, __name__)
