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
class PutMqRelay(StreamingCommand):

    field_appname = Option(
        doc='''
        **Syntax:** **field_appname=****
        **Description:** field name containing the appname to be published.''',
        require=True)

    field_region = Option(
        doc='''
        **Syntax:** **field_region=****
        **Description:** field name containing the region to be published.''',
        require=True)

    field_manager = Option(
        doc='''
        **Syntax:** **field_manager=****
        **Description:** field name containing the MQ manager value to be used.''',
        require=True)

    field_queue = Option(
        doc='''
        **Syntax:** **field_queue=****
        **Description:** field name containing the MQ queue value to be used.''',
        require=True)

    field_message = Option(
        doc='''
        **Syntax:** **field_message=****
        **Description:** field name containing the message to be published.''',
        require=True)

    max_batchsize = Option(
        doc='''
        **Syntax:** **max_batchsize=****
        **Description:** Define the maximal number of messages in a single batch (from the batch_uuid point of view).
        When this value is reached, an additional batch_uuid value is created.''',
        require=False, default=100000, validate=validators.Match("max_batchsize", r"^\d*$"))

    dedup = Option(
        doc='''
        **Syntax:** **dedup=****
        **Description:** uses an hash based logic to prevent inserting records already known to the KVstore and avoid generating duplicates.
        Default is True.
        If true, the hash used for the records is based on the raw message, the same hash cannot be added more than once.
        If false, use a random record for the key generation.
        .''',
        require=False, validate=validators.Match("dedup", r"^(True|False)$"))

    # Initially, validation_required was optional. It is now mandatory, and left commented for information
    #validation_required = Option(
    #    doc='''
    #    **Syntax:** **validation_required=****
    #    **Description:** set a boolean flag to allow the batch to be processed, default is False
    #    If true, the field validation_required is set to the boolean value 1, the batch will not be processed until it is validate and the value set to 0 in the KVstore.
    #    If false, the validation_required field is set to the False boolean value 0 and will be processed as soon as possible.
    #    .''',
    #    require=False, validate=validators.Match("dedup", r"^(True|False)$"))

    comment = Option(
        doc='''
        **Syntax:** **comment=****
        **Description:** comment message for auditing purposes.''',
        require=True, validate=validators.Match("comment", r"\w+"))


    def checkstr(self, i):

        if i is not None:
            i = i.replace("\\", "\\\\")
            # Manage breaking delimiters
            i = i.replace("\"", "\\\"")
            return i


    def stream(self, records):

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
        splunklogfile = SPLUNK_HOME + "/var/log/splunk/mq_publish_message_putmqrelay.log"

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

            headers = {
                'Authorization': 'bearer %s' % bearer_token,
                'Content-Type': 'application/json'}
        else:
            headers = {
                'Authorization': 'Splunk %s' % session_key,
                'Content-Type': 'application/json'}

        # Get conf
        conf_file = "ta_dhl_mq_settings"
        confs = self.service.confs[str(conf_file)]
        no_max_retry = None
        for stanza in confs:
            if stanza.name == "advanced_configuration":
                for key, value in stanza.content.items():
                    if key == "no_max_retry":
                        no_max_retry = value

        # Set the dedup mode
        if not self.dedup:
            self.dedup = 'True'

        # Set the validation required
        #if not self.validation_required:
        #    validation_required = 0
        #elif self.validation_required == 'True':
        #    validation_required = 1
        #elif self.validation_required == 'False':
        #    validation_required = 0
        # validation_required is now mandatory
        validation_required = 1

        # comment
        comment = str(self.comment)

        # generate a list to store all batch_uuid
        batch_uuid_list = []

        # generate a dictionnary of processed count per batch_uuid
        batch_uuid_dict = {}

        # generate a unique ID for this batch
        batch_uuid = random.getrandbits(80)

        # append the first batch
        batch_uuid_list.append(batch_uuid)

        # empty array to store our processed records
        records_list = []

        # Loop in the results
        records_count = 0
        for record in records:

            # if the max batch size is not unlimited
            if int(self.max_batchsize) !=0:
                if records_count>=int(self.max_batchsize):
                    # insert the current batch in the dict
                    dict = {batch_uuid: records_count}
                    batch_uuid_dict.update(dict)
                    # generate a new batch
                    batch_uuid = random.getrandbits(80)
                    batch_uuid_list.append(batch_uuid)
                    # reset
                    records_count = 0

            # increment
            records_count +=1

            appname = str(record[self.field_appname])
            region = str(record[self.field_region])
            manager = str(record[self.field_manager])
            queue = str(record[self.field_queue])
            message = str(record[self.field_message])
            if message.count('\n')>2:
                multiline = 1
            else:
                multiline = 0

            # status is pending for an addition
            status = 'pending'

            # use the MD5 sum of the message as a unique key identifier
            if self.dedup == 'True':
                keyrecord = hashlib.md5(message.encode('utf-8')).hexdigest()
            else:
                keyrecord = random.getrandbits(128)

            # Get some requires fields length for reporting and verification purposes
            appname_len = len(appname)
            region_len = len(region)
            manager_len = len(manager)
            queue_len = len(queue)
            message_len = len(message)
            
            # define ctime, mtime
            ctime = time.time()
            mtime = str(ctime)

            # default values for status and number of attempts
            status = "pending"
            no_attempts = "0"

            # Insert in the KV
            if message and (message_len>0 and appname_len>0 and region_len>0 and manager_len>0 and queue_len>0):

                # Update the KVstore record with the increment, and the new mtime
                record = {
                            "_key": str(keyrecord),
                            "ctime": str(ctime),
                            "mtime": str(mtime),
                            "status": str(status),
                            "manager": str(manager),
                            "queue": str(queue),
                            "appname": str(appname),
                            "region": str(region),
                            "no_attempts": str(no_attempts),
                            "no_max_retry": str(no_max_retry),
                            "user": str(user),
                            "message": str(self.checkstr(message)),
                            "multiline": str(multiline),
                            "batch_uuid": str(batch_uuid),
                            "validation_required": str(validation_required),
                            "comment": str(comment)
                            }

                records_list.append(record)


            else:
                action = "failure"
                result = "Is either message/appname/region/manager/queue empty?"
                status = "refused"

        # Add the last batch to the dict
        dict = {batch_uuid: records_count}
        batch_uuid_dict.update(dict)

        # batch insert into the KVstore

        # total number of messages to be processed
        results_count = len(records_list)

        # Set uri
        kv_url = 'https://localhost:' + str(splunkd_port) \
                        + '/servicesNS/nobody/' \
                        'TA-dhl-mq/storage/collections/data/kv_mq_publish_backlog/batch_save'

        # to report processed messages
        processed_count = 0

        # process by chunk
        chunks = [records_list[i:i + 500] for i in range(0, len(records_list), 500)]
        for chunk in chunks:

            chunk_len = len(chunk)
            session = requests.Session()
            session.verify = True
            response = session.post(kv_url, headers=headers, data=json.dumps(chunk), verify=False)
            if response.status_code not in (200, 201, 204):
                self.logger.fatal('KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
                    'content={}'.format(kv_url, record, response.status_code, response.text))
            else:
                processed_count = processed_count + chunk_len

        for batch_uuid_unique in batch_uuid_list:

            # run a Splunk control search, get the number of record matching the batch_uuid
            url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

            # process_count is handled differently if processing by batches
            if int(self.max_batchsize) !=0:
                processed_count = batch_uuid_dict[batch_uuid_unique]
                results_count = processed_count

            # Define and run a Splunk search
            kvstore_count = 0
            search = "| inputlookup mq_publish_backlog where batch_uuid=\"" + str(batch_uuid_unique) + "\" | stats count"
            output_mode = "csv"
            exec_mode = "oneshot"
            response = requests.post(url, headers=headers, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
            try:
                # Use the CSV dict reader
                readCSV = csv.DictReader(response.text.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))
                for row in readCSV:
                    kvstore_count = int(row['count'])

            except Exception as e:
                kvstore_count = -1

            if (results_count == processed_count) and (results_count == kvstore_count):
                action = "success"
                result = "MQ KVstore publication success, all messages were successfully inserted in the collection."
            elif (kvstore_count<results_count) and self.dedup == 'False' and kvstore_count!=-1:
                action = "failure"
                result = "MQ KVstore publication failure, not all messages could be inserted into the collection, run this job again with dedup=True if due to a temporary error."
            elif (kvstore_count<results_count) and self.dedup == 'True' and kvstore_count!=-1:
                action = "failure"
                result = "MQ KVstore publication failure, not all messages could be inserted into the collection, dedup is enabled so this likely is caused by duplicate messages provided as part of the results, review the messages that were submitted."
            elif kvstore_count == -1:
                action = "failure"
                result = "MQ KVstore publication failure, the number of messages inserted in the KVstore could not be verified, maybe the Splunk search has failed, review the job inspector for more information."
            else:
                action = "failure"
                result = "MQ KVstore publication failure, not all messages could be processed, review the job inspector for more information."

            raw = {
                "action": str(action),
                "result": str(result),
                "results_count": str(results_count),
                "processed_count": str(processed_count),
                "kvstore_count": str(kvstore_count),
                "batch_uuid": str(batch_uuid_unique),
                "user": str(user)
            }

            outputlog = open(splunklogfile, "a")
            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
            raw_kv_message = 'action=\"' + str(action) + '\", result=\"' + str(result) \
                + '\", results_count=\"' + str(results_count) \
                + '\", processed_count=\"' + str(processed_count) \
                + '\", kvstore_count=\"' + str(kvstore_count) \
                + '\", batch_uuid=\"' + str(batch_uuid_unique) \
                + '\", user=\"' + str(user) + '\"'
            outputlog.write(str(t[:-3]) + " INFO file=putmqrelay.py | customaction - signature=\"putmqrelay custom command called, " + str(raw_kv_message) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\" action_status=\"success\"\"\n")
            outputlog.close()

            yield {'_time': time.time(), '_raw': json.dumps(raw, indent=4), 'action': str(action), 'result': str(result), 'result_count': str(results_count), 'process_count': str(processed_count), 'kvstore_count': str(kvstore_count), 'batch_uuid': str(batch_uuid_unique)}

dispatch(PutMqRelay, sys.argv, sys.stdin, sys.stdout, __name__)
