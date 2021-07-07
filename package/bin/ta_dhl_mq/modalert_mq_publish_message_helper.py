
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

    name = helper.get_param("name")
    helper.log_info("name={}".format(name))

    account = helper.get_param("account")
    helper.log_info("account={}".format(account))

    # Retrieve the session_key
    helper.log_debug("Get session_key.")
    session_key = helper.session_key

    import solnlib

    app = 'TA-dhl-mq'
    account_cfm = solnlib.conf_manager.ConfManager(
        session_key,
        app,
        realm="__REST_CREDENTIAL__#{}#configs/conf-ta_dhl_mq_account".format(app))
    splunk_ta_account_conf = account_cfm.get_conf("ta_dhl_mq_account").get_all()
    helper.log_info("account={}".format(splunk_ta_account_conf))

    # account details
    account_details = splunk_ta_account_conf[account]

    # Get authentication type
    auth_type = account_details.get("auth_type", 0)
    helper.log_info("auth_type={}".format(auth_type))

    # Get username
    username = account_details.get("username", 0)
    helper.log_info("username={}".format(username))

    # Get password
    password = account_details.get("password", 0)
    helper.log_info("password={}".format(password))

    # Get mqhost
    mqhost = account_details.get("mqhost", 0)
    helper.log_info("mqhost={}".format(mqhost))

    # Get mqport
    mqport = account_details.get("mqport", 0)
    helper.log_info("mqport={}".format(mqport))

    # Get mqssl
    mqssl = account_details.get("mqssl", 0)
    helper.log_info("mqssl={}".format(mqssl))

    # Get ssl_cipher_spec
    ssl_cipher_spec = account_details.get("ssl_cipher_spec", 0)
    helper.log_info("ssl_cipher_spec={}".format(ssl_cipher_spec))

    # Get key_repo_location
    key_repo_location = account_details.get("key_repo_location", 0)
    helper.log_info("key_repo_location={}".format(key_repo_location))

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
            logmsg = "Publishing the message=" + str(msgpayload) + " to the queue manager=" + str(mqhost) + " with channel=" + str(mqchannel) + ", queue=" + str(mqqueuedest)
            helper.log_debug("logmsg:={}".format(logmsg))
        else:
            helper.log_error("Cannot publish an empty message!")


    return 0
