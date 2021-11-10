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
            for stanza in confs:
                if stanza.name == "advanced_configuration":
                    for key, value in stanza.content.items():
                        if key == "mqpassthrough":
                            mqpassthrough = value
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

            # turn the kvstore_instance into an object
            kvstore_instance_list = kvstore_instance.split(":")
            kvstore_remote_instance = kvstore_instance_list[0]
            kvstore_remote_port = kvstore_instance_list[1]

            # if mqpassthrough is enabled we have nothing to do
            if str(mqpassthrough) == 'enabled':
                # output a report to Splunk
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + "This instance is configured in passthrough mode, you can disable the execution of the search.\"}"}
                yield data
                sys.exit(0)

            else:
                # do something

                # first, attempt to login to the service, if failing there's nothing we can do
                try:

                    collection_name = "kv_mq_publish_ha_consumers_keepalive"            
                    service = client.connect(
                        splunkToken=str(bearer_token),
                        owner="nobody",
                        app="TA-dhl-mq",
                        host=kvstore_remote_instance,
                        port=kvstore_remote_port
                    )
                    collection = service.kvstore[collection_name]

                except Exception as e:

                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: logging to the service with exception " + str(e) + "\"}"}
                    yield data
                    sys.exit(1)

                # get my hostname
                myhostname = socket.gethostname()
                self.logger.fatal(str(myhostname))

                # loop through the configured account, and insert a keep alive record for the consumer

                # At least one account needs to be configured
                isconfigured = False
                conf_file = "ta_dhl_mq_account"
                confs = self.service.confs[str(conf_file)]
                for stanza in confs:

                    self.logger.fatal(str(stanza.name))
                    isconfigured = True
                    for key, value in stanza.content.items():
                        if key == "hagroup":
                            hagroup = value
                        if key == "mqhost":
                            mqhost = value

                    # define a unique md5
                    md5_str = str(hagroup) + ":" + str(myhostname)
                    md5 = hashlib.md5(md5_str.encode('utf-8')).hexdigest()
                    self.logger.fatal(str(md5))

                    # For every key manager, insert a keepalive record for this consumer

                    # get the existing record, if any
                    try:
                        record = json.dumps(collection.data.query_by_id(md5), indent=1)

                    except Exception as e:
                        record = None

                    # Proceed
                    if record is not None and len(record)>2:

                        try:
                            # update the record
                            collection.data.update(md5, json.dumps({
                                "ha_group_name": str(hagroup),
                                "account_name": str(stanza.name),
                                "consumer_name": str(myhostname),
                                "mqhost": str(mqhost),
                                "mtime": str(time.time())
                                }))

                        except Exception as e:
                            self.logger.fatal('Failed to update the keepalive record in the audit KVstore collection with exception: ' + str(e))

                    else:

                        try:
                            # Insert the record
                            collection.data.insert(json.dumps({
                                "_key": str(md5),
                                "ha_group_name": str(hagroup),
                                "account_name": str(stanza.name),
                                "consumer_name": str(myhostname),
                                "mqhost": str(mqhost),
                                "mtime": str(time.time())
                                }))

                        except Exception as e:
                            self.logger.fatal('Failed to insert a new keepalive record in the audit KVstore collection with exception: ' + str(e))


                if isconfigured:

                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + "keep alive sent successfully\"}"}
                    yield data
                    sys.exit(0)

                else:

                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error, there are no accounts configured yet\"}"}
                    yield data
                    sys.exit(1)

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request\"}"}
            yield data

dispatch(SendKeepAlive, sys.argv, sys.stdin, sys.stdout, __name__)
