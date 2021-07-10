
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

def process_event(helper, *args, **kwargs):

    helper.log_info("Alert action mq_publish_message started.")

    # imports
    import solnlib
    import os
    import uuid
    import subprocess
    import splunk.entity
    import splunk.Intersplunk
    import splunklib.client as client
    import time
    import requests

    account = helper.get_param("account")
    helper.log_debug("account={}".format(account))

    # Retrieve the session_key
    helper.log_debug("Get session_key.")
    session_key = helper.session_key

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

    # Define the KVstore collection backend, we will use it to store and update statuses of our MQ messages submissions
    kv_url = record_url = 'https://localhost:' + str(splunkd_port) \
                     + '/servicesNS/nobody/' \
                       'TA-dhl-mq/storage/collections/data/kv_mq_publish_backlog/'
    headers = {
        'Authorization': 'Splunk %s' % session_key,
        'Content-Type': 'application/json'}

    # conf manager
    app = 'TA-dhl-mq'

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

    # Get mqssl
    mqssl = account_details.get("mqssl", 0)
    helper.log_debug("mqssl={}".format(mqssl))

    # Get ssl_cipher_spec
    ssl_cipher_spec = account_details.get("ssl_cipher_spec", 0)
    helper.log_debug("ssl_cipher_spec={}".format(ssl_cipher_spec))

    # Get key_repo_location
    key_repo_location = account_details.get("key_repo_location", 0)
    helper.log_debug("key_repo_location={}".format(key_repo_location))

    # Get python_bin_path
    python_bin_path = helper.get_global_setting("python_bin_path")
    helper.log_debug("python_bin_path={}".format(python_bin_path))

    # Get mqclient_bin_path
    mqclient_bin_path = helper.get_global_setting("mqclient_bin_path")
    helper.log_debug("mqclient_bin_path={}".format(mqclient_bin_path))

    # Get mqpassthrough
    mqpassthrough = helper.get_global_setting("mqpassthrough")
    helper.log_debug("mqpassthrough={}".format(mqpassthrough))

    # Get no_max_retry
    no_max_retry = int(helper.get_global_setting("no_max_retry"))
    helper.log_debug("no_max_retry={}".format(no_max_retry))

    #
    # Alert params
    #

    # Get mqchannel
    mqchannel = helper.get_param("mqchannel")
    helper.log_debug("mqchannel={}".format(mqchannel))

    # Get mqqueuedest
    mqqueuedest = helper.get_param("mqqueuedest")
    helper.log_debug("mqqueuedest={}".format(mqqueuedest))

    # Get mqmsgfield
    mqmsgfield = helper.get_param("mqmsgfield")
    helper.log_debug("mqmsgfield={}".format(mqmsgfield))

    # Get region
    region = helper.get_param("region")
    helper.log_debug("region={}".format(region))

    #
    # START LOGIC 
    #

    # Unfortunately loading the pymqi module natively from Splunk has not been successful
    # Therefore, we will rely on the system with a fairly simple logic:
    # For each message to be submitted, create a single Python batch file and a Shell wrapper
    # The reason why we need a shell wrapper is to encapsulate the Shell wrapper is the right environment variables we need

    # first, let's create a folder to temporary store our batch files
    SPLUNK_HOME = os.environ["SPLUNK_HOME"]
    batchfolder = SPLUNK_HOME + "/etc/apps/TA-dhl-mq/batch"
    if not os.path.isdir(batchfolder):
        try:
            os.makedirs(batchfolder)
        except Exception as e:
            helper.log_error("batch folder coult not be created!={}".format(e))

    # works in p2

    #cmd = "unset LIBPATH; export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/mqm/lib64; /usr/bin/python2 /tmp/test.py"
    #process = subprocess.Popen([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #output = process.communicate()[0]
    #helper.log_debug("output={}".format(output))

    # works in both?
    #output = subprocess.check_output(["/bin/bash", "/tmp/test.sh"],universal_newlines=True)
    #helper.log_debug("output={}".format(output))

    # Loop within events and proceed

    events = helper.get_events()
    for event in events:
        helper.log_debug("event={}".format(event))

        # Get the message payload from the instructed field
        msgpayload = "null"
        for key, value in event.items():
            if key in str(mqmsgfield):
                msgpayload = str(value)
                msgpayloadforjson = checkstrforjson(value)
        helper.log_debug("msgpayload:={}".format(msgpayload))

        # publish
        if msgpayload:

            # for debug only
            logmsg = "Publishing the message=" + str(msgpayload) + " to the queue manager=" + str(account) \
                + " with channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest)
            helper.log_debug(logmsg)

            # for normal logging - do not include the message itself
            logmsg = "Publishing a message to the queue manager=" + str(account) \
                + " with channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest)
            helper.log_info(logmsg)

            if str(mqpassthrough) == "disabled":

                # generate a random uuid to name the batch
                uuid = uuid.uuid4()

                # init the attempts counter
                no_attempts = 1

                # calculate the length of the message to be published
                msgpayload_len = len(str(msgpayload))

                # Generate Shell and Python batch files
                shellbatchname = str(batchfolder) + "/" + str(uuid) + "-publish-mq.sh"
                pybatchname = str(batchfolder) + "/" + str(uuid) + "-publish-mq.py"

                shellcontent = '#!/bin/bash\n' +\
                'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:' + str(mqclient_bin_path) + '/lib64\n' +\
                'unset PYTHONPATH\n' +\
                str(python_bin_path) + ' ' + str(pybatchname) + '\n'

                helper.log_debug("shellcontent:={}".format(shellcontent))

                with open(str(shellbatchname), 'w') as f:
                    f.write(shellcontent)
                os.chmod(str(shellbatchname), 0o740)

                # Generate the Py wrapper
                pybatchcontent = 'import os\n' +\
                'import sys\n' +\
                    'import pymqi\n' +\
                    'queue_manager = \'' + str(mqmanager) + '\'\n' +\
                    'channel = \'' + str(mqchannel) + '\'\n' +\
                    'host = \'' + str(mqhost) + '\'\n' +\
                    'port = \'' + str(mqport) + '\'\n' +\
                    'queue_name = \'' + str(mqqueuedest) + '\'\n' +\
                    'message = \"\"\"' + str(msgpayload) + '\"\"\"\n' +\
                    'conn_info = \'%s(%s)\' % (host, port)\n' +\
                    'try:\n' +\
                    '    qmgr = pymqi.connect(queue_manager, channel, conn_info)\n' +\
                    '    queue = pymqi.Queue(qmgr, queue_name)\n' +\
                    '    queue.put(message)\n' +\
                    '    queue.close()\n' +\
                    '    qmgr.disconnect()\n' +\
                    '    print("Success")\n' +\
                    '    sys.exit(0)\n' +\
                    'except Exception as e:\n' +\
                    '   print("Exception: " + str(e))\n' +\
                    '   sys.exit(0)\n'

                helper.log_debug("pybatchcontent:={}".format(pybatchcontent))

                with open(str(pybatchname), 'w') as f:
                    f.write(pybatchcontent)

                # Execute the Shell batch now
                output = subprocess.check_output([str(shellbatchname), str(pybatchname)],universal_newlines=True)
                helper.log_debug("output={}".format(output))

                # purge both baches
                #os.remove(str(shellbatchname))
                #os.remove(str(pybatchname))

                # From the output of the subprocess, determine the publication status
                # If an exception was raised, it will be added to the error message
                if "Success" in str(output):
                    logmsg = "message publication success, queue_manager=" + str(mqmanager) \
                    + ", channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest) \
                    + ", message_length=" + str(msgpayload_len)
                    helper.log_info(logmsg)

                    # Store a record in the KVstore
                    record = '{"ctime": "' + str(time.time()) + '", "mtime": "' + str(time.time()) \
                            + '", "status": "success", "manager": "' + str(mqmanager) \
                            + '", "channel": "' + str(mqchannel) + '", "queue": "' + str(mqqueuedest) \
                            + '", "region": "' + str(region) \
                            + '", "no_attempts": "' + str(no_attempts) \
                            + '", "no_max_retry": "' + str(no_max_retry) \
                            + '", "message": "' + str(msgpayloadforjson) + '"}'
                    response = requests.post(record_url, headers=headers, data=record,
                                            verify=False)
                    if response.status_code not in (200, 201, 204):
                        helper.log_error(
                            'KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
                            'content={}'.format(record_url, record, response.status_code, response.text))
                    else:
                        helper.log_debug("Kvstore saving is successful")

                else:
                    logmsg = "failure in message publication with exception: " + str(output)                    
                    helper.log_error(logmsg)
                    helper.log_info("Creating a new record in the replay KVstore with key=" + str(uuid))

                    # Store a record in the KVstore
                    record = '{"_key": "' + str(uuid) + '", "ctime": "' + str(time.time()) + '", "mtime": "' + str(time.time()) \
                            + '", "status": "temporary_failure", "manager": "' + str(mqmanager) \
                            + '", "channel": "' + str(mqchannel) + '", "queue": "' + str(mqqueuedest) \
                            + '", "region": "' + str(region) \
                            + '", "no_attempts": "' + str(no_attempts) \
                            + '", "no_max_retry": "' + str(no_max_retry) \
                            + '", "message": "' + str(msgpayloadforjson) + '"}'
                    response = requests.post(record_url, headers=headers, data=record,
                                            verify=False)
                    if response.status_code not in (200, 201, 204):
                        helper.log_error(
                            'KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
                            'content={}'.format(record_url, record, response.status_code, response.text))
                    else:
                        helper.log_debug("Kvstore saving is successful")

            # Stored in a KVstore to be processed
            else:

                helper.log_info("Creating a new record in the replay KVstore with key=" + str(uuid))

                # Store a record in the KVstore
                record = '{"ctime": "' + str(time.time()) + '", "mtime": "' + str(time.time()) \
                        + '", "status": "pending", "manager": "' + str(mqmanager) \
                        + '", "channel": "' + str(mqchannel) + '", "queue": "' + str(mqqueuedest) \
                        + '", "region": "' + str(region) \
                        + '", "no_attempts": "' + str(0) \
                        + '", "no_max_retry": "' + str(no_max_retry) \
                        + '", "message": "' + str(msgpayloadforjson) + '"}'
                response = requests.post(record_url, headers=headers, data=record,
                                        verify=False)
                if response.status_code not in (200, 201, 204):
                    helper.log_error(
                        'KVstore saving has failed!. url={}, data={}, HTTP Error={}, '
                        'content={}'.format(record_url, record, response.status_code, response.text))
                else:
                    helper.log_debug("Kvstore saving is successful")

        # message is empty!
        else:
            helper.log_error("failure in message publication: Cannot publish an empty message!")

        return 0
