
# encoding = utf-8

def process_event(helper, *args, **kwargs):
    """
    # IMPORTANT
    # Do not remove the anchor macro:start and macro:end lines.
    # These lines are used to generate sample code. If they are
    # removed, the sample code will not be updated when configurations
    # are updated.

    [sample_code_macro:start]

    # The following example gets the alert action parameters and prints them to the log
    account = helper.get_param("account")
    helper.log_info("account={}".format(account))

    mqchannel = helper.get_param("mqchannel")
    helper.log_info("mqchannel={}".format(mqchannel))

    mqqueuedest = helper.get_param("mqqueuedest")
    helper.log_info("mqqueuedest={}".format(mqqueuedest))


    # The following example adds two sample events ("hello", "world")
    # and writes them to Splunk
    # NOTE: Call helper.writeevents() only once after all events
    # have been added
    helper.addevent("hello", sourcetype="mq:alert_action:publish_message")
    helper.addevent("world", sourcetype="mq:alert_action:publish_message")
    helper.writeevents(index="summary", host="localhost", source="localhost")

    # The following example gets the events that trigger the alert
    events = helper.get_events()
    for event in events:
        helper.log_info("event={}".format(event))

    # helper.settings is a dict that includes environment configuration
    # Example usage: helper.settings["server_uri"]
    helper.log_info("server_uri={}".format(helper.settings["server_uri"]))
    [sample_code_macro:end]
    """

    helper.log_info("Alert action mq_publish_message started.")

    # TODO: Implement your alert action logic here

    # imports
    import solnlib
    import os
    import uuid
    import subprocess

    account = helper.get_param("account")
    helper.log_info("account={}".format(account))

    # Retrieve the session_key
    helper.log_debug("Get session_key.")
    session_key = helper.session_key

    # conf manager
    app = 'TA-dhl-mq'
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
    mqmanager = account_details.get("mqmanager", 0)
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
                msgpayload = value
        helper.log_debug("msgpayload:={}".format(msgpayload))

        # publish
        if msgpayload:
            logmsg = "Publishing the message=" + str(msgpayload) + " to the queue manager=" + str(mqhost) \
                + " with channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest) \
                + " to the queue manager account=" + str(account)
            helper.log_debug("logmsg:={}".format(logmsg))

            # generate a random uuid to name the batch
            uuid = uuid.uuid4()

            # calculate the lenght of the message to be published
            msgpayload_len = len(str(msgpayload))

            # Generate Shell and Python batch files
            shellbatchname = str(batchfolder) + "/" + str(uuid) + "-publish-mq.sh"
            pybatchname = str(batchfolder) + "/" + str(uuid) + "-publish-mq.py"

            shellcontent = '#!/bin/bash\n' +\
            'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/mqm/lib64\n' +\
            'unset PYTHONPATH\n' +\
            '/usr/bin/python3 ' + str(pybatchname) + '\n'

            with open(str(shellbatchname), 'w') as f:
                f.write(shellcontent)
            os.chmod(str(shellbatchname), 0o740)

            # Generate the Py wrapper
            pyatchcontent = 'import os\n' +\
            'import sys\n' +\
                'import pymqi\n' +\
                'queue_manager = \'' + str(mqmanager) + '\'\n' +\
                'channel = \'' + str(mqchannel) + '\'\n' +\
                'host = \'' + str(mqhost) + '\'\n' +\
                'port = \'' + str(mqport) + '\'\n' +\
                'queue_name = \'' + str(mqqueuedest) + '\'\n' +\
                'message = \'' + str(msgpayload) + '\'\n' +\
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

            with open(str(pybatchname), 'w') as f:
                f.write(pyatchcontent)

            # Execute the Shell batch now
            output = subprocess.check_output([str(shellbatchname), str(pybatchname)],universal_newlines=True)
            helper.log_debug("output={}".format(output))

            # purge both baches
            os.remove(str(shellbatchname))
            os.remove(str(pybatchname))

            # From the output of the subprocess, determine the publication status
            # If an exception was raised, it will be added to the error message
            if "Success" in str(output):
                logmsg = "message publication success, queue_manager=" + str(mqmanager) \
                + ", channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest) \
                + ", message_lenght=" + str(msgpayload_len)
                helper.log_info(logmsg)
            else:
                logmsg = "failure in message publication with exception: " + str(output)
                helper.log_error(logmsg)

        # message is empty!
        else:
            helper.log_error("failure in message publication: Cannot publish an empty message!")

        return 0
