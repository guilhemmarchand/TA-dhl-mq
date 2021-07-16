
# encoding = utf-8

# This function is required to handle special chars for storing the object in the KVstore
def checkstrforjson(i):

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

def delete_record(helper, key, record_url, headers, *args, **kwargs):

    # imports
    import requests

    helper.log_info("kvstore_eviction: permanently deleting the record with key=" + str(key))

    # delete the record
    response = requests.delete(record_url, headers=headers, verify=False)

    if response.status_code not in (200, 201, 204):
        helper.log_error(
            'KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
            'content={}'.format(record_url, response.status_code, response.text))
    else:
        helper.log_debug("Kvstore saving is successful")


def update_record(helper, record, record_url, headers, *args, **kwargs):

    # imports
    import requests    

    response = requests.post(record_url, headers=headers, data=record,
                            verify=False)
    if response.status_code not in (200, 201, 204):
        helper.log_error(
            'KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
            'content={}'.format(record_url, record, response.status_code, response.text))
    else:
        helper.log_debug("Kvstore saving is successful")


def process_event(helper, *args, **kwargs):

    helper.log_info("Alert action mq_publish_message_relay started.")

    # imports
    import solnlib
    import os
    import sys
    import uuid
    import hashlib
    import subprocess
    import splunk.entity
    import splunk.Intersplunk
    import splunklib.client as client
    import time
    import requests

    # Retrieve the session_key
    helper.log_debug("Get session_key.")
    session_key = helper.session_key

    # Get the user context
    user = helper.user
    helper.log_debug("user={}".format(user))

    # Get splunkd port
    entity = splunk.entity.getEntity('/server', 'settings',
                                    namespace='TA-dhl-mq', sessionKey=session_key, owner='-')
    mydict = entity
    splunkd_port = mydict['mgmtHostPort']
    helper.log_debug("splunkd_port={}".format(splunkd_port))

    # Create a service for SDK based actions
    service = client.connect(
        owner="nobody",
        app="TA-dhl-mq",
        port=splunkd_port,
        token=session_key
    )    

    # Get kvstore_instance
    kvstore_instance = helper.get_global_setting("kvstore_instance")
    helper.log_debug("kvstore_instance={}".format(kvstore_instance))

    # Get bearer_token
    bearer_token = helper.get_global_setting("bearer_token")
    helper.log_debug("bearer_token={}".format(bearer_token))

    # Define the headers and kv_url, use bearer token if instance is not local
    if str(kvstore_instance) != "localhost:8089":
        headers = {
            'Authorization': 'Bearer %s' % bearer_token,
            'Content-Type': 'application/json'}
        kv_url = 'https://' + str(kvstore_instance) \
                        + '/servicesNS/nobody/' \
                        'TA-dhl-mq/storage/collections/data/kv_mq_publish_backlog/'
    else:
        headers = {
            'Authorization': 'Splunk %s' % session_key,
            'Content-Type': 'application/json'}
        kv_url = 'https://localhost:' + str(splunkd_port) \
                        + '/servicesNS/nobody/' \
                        'TA-dhl-mq/storage/collections/data/kv_mq_publish_backlog/'

    # conf manager
    app = 'TA-dhl-mq'

    # Get mqclient_bin_path
    mqclient_bin_path = helper.get_global_setting("mqclient_bin_path")
    helper.log_debug("mqclient_bin_path={}".format(mqclient_bin_path))

    # Get q_bin_path
    q_bin_path = helper.get_global_setting("q_bin_path")
    helper.log_debug("q_bin_path={}".format(q_bin_path))

    # Get mqpassthrough
    mqpassthrough = helper.get_global_setting("mqpassthrough")
    helper.log_debug("mqpassthrough={}".format(mqpassthrough))

    # Get kvstore_eviction
    kvstore_eviction = helper.get_global_setting("kvstore_eviction")
    helper.log_debug("kvstore_eviction={}".format(kvstore_eviction))    

    # Get kvstore_retention
    kvstore_retention = helper.get_global_setting("kvstore_retention")
    helper.log_debug("kvstore_retention={}".format(kvstore_retention))

    # convert in seconds
    kvstore_retention_seconds = int(float(kvstore_retention) * 3600)
    helper.log_debug("kvstore_retention_seconds={}".format(kvstore_retention_seconds))

    # Loop within events and proceed

    events = helper.get_events()
    for event in events:
        helper.log_debug("event={}".format(event))

        account = helper.get_param("account")
        helper.log_debug("account={}".format(account))

        # get account details
        account_cfm = solnlib.conf_manager.ConfManager(
            session_key,
            app,
            realm="__REST_CREDENTIAL__#{}#configs/conf-ta_dhl_mq_account".format(app))
        splunk_ta_account_conf = account_cfm.get_conf("ta_dhl_mq_account").get_all()
        helper.log_debug("account={}".format(splunk_ta_account_conf))

        # account details
        account_details = splunk_ta_account_conf[account]

        # Get authentication type
        auth_type = account_details.get("auth_type", 0)
        helper.log_debug("auth_type={}".format(auth_type))

        # Get username
        username = account_details.get("username", 0)
        helper.log_debug("username={}".format(username))

        # Get password
        password = account_details.get("password", 0)
        helper.log_debug("password={}".format(password))

        # get mqmanager
        mqmanager = str(account)
        helper.log_debug("mqmanager={}".format(mqmanager))

        # Get mqhost
        mqhost = account_details.get("mqhost", 0)
        helper.log_debug("mqhost={}".format(mqhost))

        # Get mqport
        mqport = account_details.get("mqport", 0)
        helper.log_debug("mqport={}".format(mqport))

        # Get mqchannel
        mqchannel = account_details.get("mqchannel", 0)
        helper.log_debug("mqchannel={}".format(mqchannel))

        #
        # Alert params
        #

        # Get key
        key = helper.get_param("key")
        helper.log_debug("key={}".format(key))

        # Get app
        appname = helper.get_param("appname")
        helper.log_debug("appname={}".format(appname))

        # Get region
        region = helper.get_param("region")
        helper.log_debug("region={}".format(region))

        # Get mqqueuedest
        mqqueuedest = helper.get_param("mqqueuedest")
        helper.log_debug("mqqueuedest={}".format(mqqueuedest))

        # Get message
        message = helper.get_param("message")
        helper.log_debug("message={}".format(message))

        # Get no_max_retry
        no_max_retry = int(helper.get_param("no_max_retry"))
        helper.log_debug("no_max_retry={}".format(no_max_retry))

        # Get no_attempts
        no_attempts = int(helper.get_param("no_attempts"))
        helper.log_debug("no_attempts={}".format(no_attempts))

        # Get ctime
        ctime = helper.get_param("ctime")
        helper.log_debug("ctime={}".format(ctime))

        # Get mtime
        mtime = helper.get_param("mtime")
        helper.log_debug("mtime={}".format(mtime))

        # Get status
        status = helper.get_param("status")
        helper.log_debug("status={}".format(status))

        # Get user
        user = helper.get_param("user")
        helper.log_debug("user={}".format(user))

        # Set record_url
        record_url = str(kv_url) + str(key)

        #
        # START LOGIC 
        #

        # if passthrough mode is enabled, this instance will only handle messages that were successfully published

        if str(mqpassthrough) == "enabled":

            # get the record age in seconds
            record_age = int(round(float(time.time()) - float(ctime), 0))
            helper.log_debug("record_age={}".format(record_age))

            # On the master instance, we handle the lifecyle of messages that were successfully published, and their deletion upon retention reached
            if str(status) in ("success") and str(kvstore_eviction) == "delete":
                logmsg = 'record has been successfully published and kvstore_eviction is delete.'
                helper.log_debug(logmsg)

                delete_record(helper, key, record_url, headers)

            elif str(status) in ("permanent_failure") and str(kvstore_eviction) == "preserve":
                logmsg = 'record is in permanent failure status and kvstore_eviction is preserve.'
                helper.log_debug(logmsg)

                if record_age >= kvstore_retention_seconds:
                    delete_record(helper, key, record_url, headers)
                else:
                    logmsg = 'record with key=' + str(key) + ' with age_seconds=' + str(record_age) \
                        + ' has not yet reached the max retention of ' + str(kvstore_retention_seconds)
                    helper.log_info(logmsg)

            return 0

        elif str(mqpassthrough) == "disabled":

            # get the record age in seconds
            record_age = int(round(float(time.time()) - float(ctime), 0))
            helper.log_debug("record_age={}".format(record_age))

            # If the record submission is canceled
            if str(status) in ("permanent_failure") and str(kvstore_eviction) == "delete":
                logmsg = 'record is in permanent failure status and kvstore_eviction is delete.'
                helper.log_debug(logmsg)

                delete_record(helper, key, record_url, headers)
                return 0

            elif str(status) in ("permanent_failure") and str(kvstore_eviction) == "preserve":
                logmsg = 'record is in permanent failure status and kvstore_eviction is preserve.'
                helper.log_debug(logmsg)

                if record_age >= kvstore_retention_seconds:
                    delete_record(helper, key, record_url, headers)
                else:
                    logmsg = 'record with key=' + str(key) + ' with age_seconds=' + str(record_age) \
                        + ' has not yet reached the max retention of ' + str(kvstore_retention_seconds)
                    helper.log_info(logmsg)
                return 0

            # If the record is to be processed 
            elif str(status) in ("pending", "temporary_failure"):

                # set SPLUNK_HOME
                SPLUNK_HOME = os.environ["SPLUNK_HOME"]

                # first, let's create a folder to temporary store our batch files
                batchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/batch"
                if not os.path.isdir(batchfolder):
                    try:
                        os.makedirs(batchfolder)
                    except Exception as e:
                        helper.log_error("batch folder coult not be created!={}".format(e))

                # second, create a folder to temporary store our mass batch files
                massbatchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/massbatch"
                if not os.path.isdir(massbatchfolder):
                    try:
                        os.makedirs(massbatchfolder)
                    except Exception as e:
                        helper.log_error("batch folder coult not be created!={}".format(e))

                # if the max number of attemps has not been reached
                if no_attempts < no_max_retry:

                    # increment
                    no_attempts +=1 

                    logmsg = 'MQ message publication relay, attempting publishing message from collection key=' + str(key) \
                        + ' (attempt ' + str(no_attempts) + '/' + str(no_max_retry) + ')'
                    helper.log_info(logmsg)

                    # define if multiline
                    ismultiline = False
                    if message.count('\n') > 2:
                        ismultiline = True
                        helper.log_debug("message is multiline")
                    else:
                        helper.log_debug("message is singleline")

                    # define a uuid conditionally to name the batches
                    if ismultiline:
                        uuid = uuid.uuid4()
                    else:
                        uuidstr = str(appname) + ":" + str(region) + ":" + str(mqmanager) + ":" + str(mqqueuedest)
                        uuid = hashlib.md5(uuidstr.encode('utf-8')).hexdigest()

                    # calculate the length of the message to be published
                    msgpayload_len = len(str(message))

                    # Generate Shell and batch files
                    if ismultiline:
                        shellbatchname = str(batchfolder) + "/" + str(uuid) + "-publish-mq.sh"
                        batchfile = str(batchfolder) + "/" + str(uuid) + "-filebatch.raw"
                    else:
                        shellbatchname = str(massbatchfolder) + "/" + str(uuid) + "-publish-mq.sh"
                        batchfile = str(massbatchfolder) + "/" + str(uuid) + "-filebatch.raw"

                    # Define the shell wrapper
                    if ismultiline:
                        shellcontent = '#!/bin/bash\n' +\
                        '. ' + str(mqclient_bin_path) + '/bin/setmqenv -s\n' +\
                        'export MQSERVER=\"' + str(mqchannel) + '/TCP/' + str(mqhost) + '(' + str(mqport) + ')\"\n' +\
                        str(q_bin_path) + '/q -m ' + str(mqmanager) + ' -l mqic -o ' + str(mqqueuedest) + ' -F ' + str(batchfile) + '\n' +\
                        'RETCODE=$?\n' +\
                        'if [ $RETCODE -ne 0 ]; then\n' +\
                        'echo "Failure with exit code $RETCODE"\n' +\
                        'else\n' +\
                        'echo "Success"\n' +\
                        'fi\n' +\
                        'exit $RETCODE'
                    else:
                        shellcontent = '#!/bin/bash\n' +\
                        '. ' + str(mqclient_bin_path) + '/bin/setmqenv -s\n' +\
                        'export MQSERVER=\"' + str(mqchannel) + '/TCP/' + str(mqhost) + '(' + str(mqport) + ')\"\n' +\
                        str(q_bin_path) + '/q -m ' + str(mqmanager) + ' -l mqic -o ' + str(mqqueuedest) + ' -f ' + str(batchfile) + '\n' +\
                        'RETCODE=$?\n' +\
                        'if [ $RETCODE -ne 0 ]; then\n' +\
                        'echo "Failure with exit code $RETCODE"\n' +\
                        'else\n' +\
                        'echo "Success"\n' +\
                        'fi\n' +\
                        'exit $RETCODE'

                    helper.log_debug("shellcontent:={}".format(shellcontent))

                    # Create the shell wrapper if required
                    if not os.path.isfile(shellbatchname):
                        with open(str(shellbatchname), 'w') as f:
                            f.write(shellcontent)
                        os.chmod(str(shellbatchname), 0o740)

                    # if multiline, execute and report, otherwise execute the batch conditionally

                    if ismultiline:

                        with open(str(batchfile), 'w') as f:
                            f.write(str(message))

                        # Execute the Shell batch now
                        output = subprocess.check_output([str(shellbatchname)],universal_newlines=True)
                        helper.log_debug("output={}".format(output))

                        # purge both baches
                        os.remove(str(shellbatchname))
                        os.remove(str(batchfile))

                        # From the output of the subprocess, determine the publication status
                        # If an exception was raised, it will be added to the error message
                        if "Success" in str(output):
                            logmsg = "message publication success, queue_manager=" + str(mqmanager) \
                            + ", channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest) \
                            + ", appname=" + str(appname) + ", region=" + str(region) \
                            + ", message_length=" + str(msgpayload_len) + ", key=" + str(key)
                            helper.log_info(logmsg)

                            # Update the KVstore record
                            record = '{"ctime": "' + str(ctime) + '", "mtime": "' + str(time.time()) \
                                    + '", "status": "success", "manager": "' + str(mqmanager) \
                                    + '", "queue": "' + str(mqqueuedest) \
                                    + '", "appname": "' + str(appname) \
                                    + '", "region": "' + str(region) \
                                    + '", "no_attempts": "' + str(no_attempts) \
                                    + '", "no_max_retry": "' + str(no_max_retry) \
                                    + '", "user": "' + str(user) \
                                    + '", "message": "' + str(checkstrforjson(message)) + '"}'

                            # update the record
                            update_record(helper, record, record_url, headers)
                            return 0

                        else:
                            logmsg = "failure in message publication for record key=" + str(key) + "with exception: " + str(output)
                            helper.log_error(logmsg)

                            # Update the KVstore record
                            record = '{"ctime": "' + str(ctime) + '", "mtime": "' + str(time.time()) \
                                    + '", "status": "temporary_failure", "manager": "' + str(mqmanager) \
                                    + '", "queue": "' + str(mqqueuedest) \
                                    + '", "appname": "' + str(appname) \
                                    + '", "region": "' + str(region) \
                                    + '", "no_attempts": "' + str(no_attempts) \
                                    + '", "no_max_retry": "' + str(no_max_retry) \
                                    + '", "user": "' + str(user) \
                                    + '", "message": "' + str(checkstrforjson(message)) + '"}'
                            response = requests.post(record_url, headers=headers, data=record,
                                                    verify=False)

                            # update the record
                            update_record(helper, record, record_url, headers)
                            return 0

                    else:

                        # get the line count if not multiline
                        line_count = 0
                        if os.path.isfile(str(batchfile)):
                            file = open(str(batchfile), "r")
                            line_count = 0
                            for line in file:
                                if line != "\n":
                                    line_count += 1
                            file.close()

                        if line_count < 500:

                            # Add to the batch
                            if os.path.isfile(str(batchfile)):
                                with open(str(batchfile), 'a') as f:
                                    f.write(str(message))
                            else:
                                with open(str(batchfile), 'w') as f:
                                    f.write(str(message))

                            logmsg = "message added to batch pending, queue_manager=" + str(mqmanager) \
                            + ", channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest) \
                            + ", appname=" + str(appname) + ", region=" + str(region) \
                            + ", message_length=" + str(msgpayload_len) + ", key=" + str(key)
                            helper.log_info(logmsg)

                            # Update the KVstore record
                            record = '{"ctime": "' + str(ctime) + '", "mtime": "' + str(time.time()) \
                                    + '", "status": "pending_batch", "manager": "' + str(mqmanager) \
                                    + '", "queue": "' + str(mqqueuedest) \
                                    + '", "appname": "' + str(appname) \
                                    + '", "region": "' + str(region) \
                                    + '", "no_attempts": "' + str(no_attempts) \
                                    + '", "no_max_retry": "' + str(no_max_retry) \
                                    + '", "user": "' + str(user) \
                                    + '", "message": "' + str(checkstrforjson(message)) + '"}'

                            # update the record
                            update_record(helper, record, record_url, headers)
                            return 0

                        elif line_count >= 500:

                            # Add to the batch
                            if os.path.isfile(str(batchfile)):
                                with open(str(batchfile), 'a') as f:
                                    f.write(str(message))
                            else:
                                with open(str(batchfile), 'w') as f:
                                    f.write(str(message))

                            # Execute the Shell batch now
                            output = subprocess.check_output([str(shellbatchname)],universal_newlines=True)
                            helper.log_debug("output={}".format(output))

                            # purge both baches
                            os.remove(str(shellbatchname))
                            os.remove(str(batchfile))

                            # From the output of the subprocess, determine the publication status
                            # If an exception was raised, it will be added to the error message

                            # batch: all messages in pending_batch for this UUID need to be updated to a successful status

                            if "Success" in str(output):
                                logmsg = "batch publication success, queue_manager=" + str(mqmanager) \
                                + ", channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest) \
                                + ", appname=" + str(appname) + ", region=" + str(region) \
                                + ", message_length=" + str(msgpayload_len) + ", key=" + str(key)
                                helper.log_info(logmsg)

                                # Update the KVstore record
                                record = '{"ctime": "' + str(ctime) + '", "mtime": "' + str(time.time()) \
                                        + '", "status": "success", "manager": "' + str(mqmanager) \
                                        + '", "queue": "' + str(mqqueuedest) \
                                        + '", "appname": "' + str(appname) \
                                        + '", "region": "' + str(region) \
                                        + '", "no_attempts": "' + str(no_attempts) \
                                        + '", "no_max_retry": "' + str(no_max_retry) \
                                        + '", "user": "' + str(user) \
                                        + '", "message": "' + str(checkstrforjson(message)) + '"}'

                                # update the record
                                update_record(helper, record, record_url, headers)

                                # Now, update all pending_batch records matching our criterias

                                # Define the url
                                url = "https://" + str(kvstore_instance) + "/services/search/jobs/export"

                                # form a search
                                search_filter = "where (status=\"pending_batch\" AND manager=\"" + str(mqmanager) +\
                                    "\" AND queue=\"" + str(mqqueuedest) + "\")"
                                search_action = "| eval key=_key, status=\"success\", mtime=now() | outputlookup append=t key_field=key mq_publish_backlog"
                                search = "| inputlookup mq_publish_backlog " + str(search_filter) + str(search_action)

                                output_mode = "csv"
                                exec_mode = "oneshot"
                                response = requests.post(url, headers={'Authorization': headers}, verify=False, data={'search': search, 'output_mode': output_mode, 'exec_mode': exec_mode}) 

                                if response.status_code not in (200, 201, 204):
                                    helper.log_error(
                                        'KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
                                        'content={}'.format(record_url, response.status_code, response.text))
                                else:
                                    helper.log_debug("Kvstore saving is successful")

                                return 0

                else:

                    logmsg = 'MQ message publish permanent failure for record key=' + str(key) \
                        + ' has reached ' + str(no_attempts) + ' attempts over ' + str(no_max_retry) + ' allowed, its publication is now canceled'
                    helper.log_error(logmsg)

                    if str(kvstore_eviction) == "delete":
                        helper.log_info("kvstore_eviction: permanently deleting the record with key=" + str(key))

                        # delete the record
                        delete_record(helper, key, record_url, headers)

                    elif str(kvstore_eviction) == "preserve":
                        helper.log_info("kvstore_eviction: tagging as permanent_failure and preserving the record with key=" + str(key))

                        # Update the KVstore record
                        record = '{"ctime": "' + str(ctime) + '", "mtime": "' + str(time.time()) \
                                + '", "status": "permanent_failure", "manager": "' + str(mqmanager) \
                                + '", "queue": "' + str(mqqueuedest) \
                                + '", "appname": "' + str(appname) \
                                + '", "region": "' + str(region) \
                                + '", "no_attempts": "' + str(no_attempts) \
                                + '", "no_max_retry": "' + str(no_max_retry) \
                                + '", "user": "' + str(user) \
                                + '", "message": "' + str(checkstrforjson(message)) + '"}'

                        # update the record
                        update_record(helper, record, record_url, headers)
                        return 0
