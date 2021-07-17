#!/usr/bin/env python

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import splunk
import splunk.entity
import requests
import time
import hashlib
import random

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

    dedup = Option(
        doc='''
        **Syntax:** **dedup=****
        **Description:** uses an hash based logic to prevent inserting records already known to the KVstore and avoid generating duplicates.
        Default is True.
        If true, the hash used for the records is based on the raw message, the same hash cannot be added more than once.
        If false, use a random record for the key generation.
        .''',
        require=False, validate=validators.Match("dedup", r"^(True|False)$"))

    validation_required = Option(
        doc='''
        **Syntax:** **validation_required=****
        **Description:** set a boolean flag to allow the batch to be processed, default is False
        If true, the field validation_required is set to the boolean value 1, the batch will not be processed until it is validate and the value set to 0 in the KVstore.
        If false, the validation_required field is set to the False boolean value 0 and will be processed as soon as possible.
        .''',
        require=False, validate=validators.Match("dedup", r"^(True|False)$"))

    def checkstr(self, i):

        if i is not None:
            i = i.replace("\\", "\\\\")
            # Manage line breaks
            i = i.replace("\n", "\\n")
            i = i.replace("\r", "\\r")
            # Manage tabs
            i = i.replace("\t", "\\t")
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

        # Set url
        kv_url = 'https://localhost:' + str(splunkd_port) \
                        + '/servicesNS/nobody/' \
                        'TA-dhl-mq/storage/collections/data/kv_mq_publish_backlog/'

        # Set headers
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
        if not self.validation_required:
            validation_required = 0
        elif self.validation_required == 'True':
            validation_required = 1
        elif self.validation_required == 'False':
            validation_required = 0

        # generate a unique ID for this batch
        batch_uuid = random.getrandbits(128)

        # Loop in the results
        for record in records:

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

            action = None
            result = None

            status = "pending"
            no_attempts = "0"

            # Insert in the KV
            if message and (message_len>0 and appname_len>0 and region_len>0 and manager_len>0 and queue_len>0):

                # Update the KVstore record with the increment, and the new mtime
                record = '{' \
                        '"_key": "' + str(keyrecord) +\
                        '", "ctime": "' + str(ctime) +\
                        '", "mtime": "' + str(mtime) +\
                        '", "status": "' + str(status) +\
                        '", "manager": "' + str(manager) +\
                        '", "queue": "' + str(queue) +\
                        '", "appname": "' + str(appname) +\
                        '", "region": "' + str(region) +\
                        '", "no_attempts": "' + str(no_attempts) +\
                        '", "no_max_retry": "' + str(no_max_retry) +\
                        '", "user": "' + str(user) +\
                        '", "message": "' + str(self.checkstr(message)) +\
                        '", "multiline": "' + str(multiline) +\
                        '", "batch_uuid": "' + str(batch_uuid) +\
                        '", "validation_required": "' + str(validation_required) +\
                        '"}'

                session = requests.Session()
                session.verify = True
                response = session.post(kv_url, headers=headers, data=record,
                                        verify=False)
                if response.status_code not in (200, 201, 204):
                    self.logger.fatal('KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
                        'content={}'.format(kv_url, record, response.status_code, response.text))
                    action = "failure"
                    result = "KVstore saving has failed!. Exception: " + str(response.text)
                    status = None
                else:
                    action = "success"
                    result = "record key: " + str(keyrecord) + " successfully added to the MQ publishing KVstore"

            else:
                action = "failure"
                result = "Is either message/appname/region/manager/queue empty?"
                status = "refused"

            # yield - return in Splunk a resulting table
            yield {'_time': time.time(), 'action': str(action), 'result': str(result), 'key': str(keyrecord), 'message_length': str(message_len), 'message': str(message), 'multiline': str(multiline), 'appname': str(appname), 'region': str(region), 'ctime': str(time.time()), 'mtime': str(time.time()), 'manager': str(manager), 'status': str(status), 'queue': str(queue), 'no_max_retry': str(no_max_retry), 'no_attempts': '0', 'user': str(user), 'batch_uuid': str(batch_uuid), 'validation_required': str(validation_required)}

dispatch(PutMqRelay, sys.argv, sys.stdin, sys.stdout, __name__)
