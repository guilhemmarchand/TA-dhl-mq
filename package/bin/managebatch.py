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

class ManagePendingBatch(GeneratingCommand):

    batch_uuid = Option(
        doc='''
        **Syntax:** **batch_uuid=****
        **Description:** Unique identifier for the batch to be managed.''',
        require=True)

    action = Option(
        doc='''
        **Syntax:** **action=****
        **Description:** The action to be performed, valid actions are: submit | cancel''',
        require=True)

    comment = Option(
        doc='''
        **Syntax:** **comment=****
        **Description:** A comment to be provided for auditing purposes, this is mandatory''',
        require=True, validate=validators.Match("comment", r"\w+"))


    def generate(self, **kwargs):

        if self:

            # Get the session key
            session_key = self._metadata.searchinfo.session_key

            # Get the current user        
            user = self._metadata.searchinfo.username

            # get the list of roles for the user
            user_roles = []
            kwargs = {"sort_key":"realname", "sort_dir":"asc"}
            users = self.service.users.list(count=-1,**kwargs)
            for username in users:
                if user == username.name:
                    for role in username.role_entities:
                        user_roles.append(role.name)

            # for debug
            #for role in user_roles:
            #    self.logger.fatal("DEBUG: " + str(role))

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

            # comment
            comment = str(self.comment)
            if comment == "provide a comment for this operation":
                comment = "The approver did not provide with a comment for this operation"

            # RBAC: whatever the action the user requests, we need to verify permissions first
            # For this, get the appname for this batch with additional information

            # Define and run a Splunk search
            search = "| inputlookup mq_publish_backlog where batch_uuid=\"" + str(self.batch_uuid) + "\"" \
                + " | stats first(appname) as appname, first(status) as status, first(validation_required) as validation_required"
            output_mode = "csv"
            exec_mode = "oneshot"
            response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
            csv_data = response.text

            # Use the CSV dict reader
            readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

            # get batch information
            batch_appname = None
            batch_status = None
            batch_validation_required = None
            
            for row in readCSV:
                batch_appname = str(row['appname'])
                batch_status = str(row['status'])
                batch_validation_required = str(row['validation_required'])

            #self.logger.fatal("DEBUG: batch_appname is " + batch_appname)
            #self.logger.fatal("DEBUG: batch_status is " + batch_status)
            #self.logger.fatal("DEBUG: batch_validation_required is " + batch_validation_required)

            # Break here if we didn't get a result
            if not batch_appname or not batch_status or not batch_validation_required:
                # yield
                response = "Error: This batch could not be found in the collection or an exception was encountered (check the job inspector), please verify your input and retry."
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(response) + "\"}"}
                yield data
                sys.exit(0)

            # RBAC: build the required Splunk role
            role_required = "mqsubmission_" + batch_appname.lower() + "_approver"

            # If the user is not a member of this role, no action are allowed
            if not role_required in user_roles:

                # yield
                response = "Error: You do no have the permission to perform any action on this batch, the role " \
                    + str(role_required) + " is required, you are a member of the following roles: " \
                    + ",".join(user_roles) + "."
                data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(response) + "\"}"}
                yield data

            else:

                # invalid action requested
                if not self.action in ("submit", "cancel"):
                    # yield
                    response = "Error: invalid action requested, allowed actions are: submit|cancel" + "."
                    data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(response) + "\"}"}
                    yield data                

                # depending on the action
                elif self.action == 'submit':

                    if str(batch_status) == "pending" and str(batch_validation_required) == "1":

                        # Define and run a Splunk search
                        search = "| inputlookup mq_publish_backlog where batch_uuid=\"" + str(self.batch_uuid) + "\"" \
                            + " | eval key=_key | eval validation_required=0, mtime=now() | outputlookup append=t key_field=key mq_publish_backlog" \
                            + " | stats values(region) as region, values(appname) as appname, values(validation_required) as validation_required, count, values(manager) as manager, values(queue) as queue, values(user) as submitter, last(comment) as submitter_comment by batch_uuid" \
                            + " | eval action=if(count>0 AND validation_required=0, \"success\", \"failure\") | fields action, *"
                        output_mode = "csv"
                        exec_mode = "oneshot"
                        response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
                        csv_data = response.text

                        # Use the CSV dict reader
                        readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

                        # For row in CSV, generate the _raw
                        for row in readCSV:

                            outputlog = open(splunklogfile, "a")
                            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                            raw_kv_message = 'action=\"' + str(row['action']) \
                                + '\", count=\"' + str(row['count']) \
                                + '\", manager=\"' + str(row['manager']) \
                                + '\", queue=\"' + str(row['queue']) \
                                + '\", submitter_comment=\"' + str(row['submitter_comment']) \
                                + '\", batch_uuid=\"' + str(row['batch_uuid']) \
                                + '\", region=\"' + str(row['region']) \
                                + '\", validation_required=\"' + str(row['validation_required']) \
                                + '\", submitter=\"' + str(row['submitter']) + '\"' \
                                + '\", approver=\"' + str(user) + '\"'
                            outputlog.write(str(t[:-3]) + " INFO file=managebatch.py | customaction - signature=\"managebatch custom command called, " + str(raw_kv_message) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\" action_status=\"success\", approver_comment=\"" + str(comment) + "\", approver=\"" + str(user) + "\", action_performed=\"" + str(self.action) + "\"\n")
                            outputlog.close()

                            yield {'_time': time.time(), '_raw': str(row), 'action': str(row['action']), 'appname': str(row['appname']), 'batch_uuid': str(row['batch_uuid']), 'count': str(row['count']), 'submitter': str(row['submitter']), 'approver': str(user), 'manager': str(row['manager']), 'queue': str(row['queue']), 'region': str(row['region']), 'validation_required': str(row['validation_required'])}

                            # store a new record in the audit KV for reporting purposes
                            try:

                                collection_name = "kv_mq_publish_batch_history"            
                                service = client.connect(
                                    owner="nobody",
                                    app="TA-dhl-mq",
                                    port=splunkd_port,
                                    token=session_key
                                )
                                collection = service.kvstore[collection_name]

                                # Insert the record
                                collection.data.insert(json.dumps({                        
                                    "ctime": str(int(round(time.time() * 1000))),
                                    "submitter": str(row['submitter']),
                                    "approver": str(user),
                                    "appname": str(row['appname']),                                
                                    "count": str(row['count']),
                                    "manager": str(row['manager']),
                                    "queue": str(row['queue']),
                                    "batch_uuid": str(row['batch_uuid']),
                                    "region": str(row['region']),
                                    "action": str(self.action),
                                    "submitter_comment": str(row['submitter_comment']),
                                    "approver_comment": str(comment)
                                    }))

                            except Exception as e:
                                self.logger.fatal('Failed to insert a new record in the audit KVstore collection with exception: ' + str(e))

                    else:

                        # yield
                        response = "Error: invalid action requested, this batch is not pending for approval."
                        data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(response) + "\"}"}
                        yield data

                elif self.action == 'cancel':

                    if str(batch_status) == "pending" or str(batch_status) == "temporary_failure":

                        # Define and run a Splunk search
                        search = "| inputlookup mq_publish_backlog where batch_uuid=\"" + str(self.batch_uuid) + "\"" \
                            + " | eval key=_key | eval validation_required=0, status=\"canceled\", mtime=now() | outputlookup append=t key_field=key mq_publish_backlog" \
                            + " | stats values(status) as status, values(region) as region, values(appname) as appname, values(validation_required) as validation_required, count, values(manager) as manager, values(queue) as queue, values(user) as submitter, last(comment) as submitter_comment by batch_uuid" \
                            + " | eval action=if(count>0 AND validation_required=0 AND status=\"canceled\", \"success\", \"failure\") | fields action, *"
                        #self.logger.fatal('search: ' + str(search))
                        output_mode = "csv"
                        exec_mode = "oneshot"
                        response = requests.post(url, headers={'Authorization': header}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 
                        csv_data = response.text

                        # Use the CSV dict reader
                        readCSV = csv.DictReader(csv_data.splitlines(True), delimiter=str(u','), quotechar=str(u'"'))

                        # For row in CSV, generate the _raw
                        for row in readCSV:

                            outputlog = open(splunklogfile, "a")
                            t = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
                            raw_kv_message = 'action=\"' + str(row['action']) \
                                + '\", count=\"' + str(row['count']) \
                                + '\", manager=\"' + str(row['manager']) \
                                + '\", queue=\"' + str(row['queue']) \
                                + '\", submitter_comment=\"' + str(row['submitter_comment']) \
                                + '\", batch_uuid=\"' + str(row['batch_uuid']) \
                                + '\", region=\"' + str(row['region']) \
                                + '\", validation_required=\"' + str(row['validation_required']) \
                                + '\", submitter=\"' + str(row['submitter']) + '\"' \
                                + '\", approver=\"' + str(user) + '\"'
                            outputlog.write(str(t[:-3]) + " INFO file=managebatch.py | customaction - signature=\"managebatch custom command called, " + str(raw_kv_message) + "\", app=\"TA-dhl-mq\" action_mode=\"saved\" action_status=\"success\", approver_comment=\"" + str(comment) + "\", approver=\"" + str(user) + "\", action_performed=\"" + str(self.action) + "\"\n")
                            outputlog.close()

                            yield {'_time': time.time(), '_raw': str(row), 'action': str(row['action']), 'appname': str(row['appname']), 'batch_uuid': str(row['batch_uuid']), 'count': str(row['count']), 'submitter': str(row['submitter']), 'approver': str(user), 'manager': str(row['manager']), 'queue': str(row['queue']), 'region': str(row['region']), 'validation_required': str(row['validation_required'])}

                            # store a new record in the audit KV for reporting purposes
                            try:

                                collection_name = "kv_mq_publish_batch_history"            
                                service = client.connect(
                                    owner="nobody",
                                    app="TA-dhl-mq",
                                    port=splunkd_port,
                                    token=session_key
                                )
                                collection = service.kvstore[collection_name]

                                # Insert the record
                                collection.data.insert(json.dumps({                        
                                    "ctime": str(int(round(time.time() * 1000))),
                                    "submitter": str(row['submitter']),
                                    "approver": str(user),
                                    "appname": str(row['appname']),                                
                                    "count": str(row['count']),
                                    "manager": str(row['manager']),
                                    "queue": str(row['queue']),
                                    "batch_uuid": str(row['batch_uuid']),
                                    "region": str(row['region']),
                                    "action": str(self.action),
                                    "submitter_comment": str(row['submitter_comment']),
                                    "approver_comment": str(comment)
                                    }))

                            except Exception as e:
                                self.logger.fatal('Failed to insert a new record in the audit KVstore collection with exception: ' + str(e))

                    else:

                        # yield
                        response = "Error: invalid action requested, this batch is not in a stage that can be cancelled, or it has been cancelled already."
                        data = {'_time': time.time(), '_raw': "{\"response\": \"" + str(response) + "\"}"}
                        yield data

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request\"}"}
            yield data

dispatch(ManagePendingBatch, sys.argv, sys.stdin, sys.stdout, __name__)
