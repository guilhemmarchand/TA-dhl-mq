User guide
----------

Submitting messages to IBM MQ Series from Splunk
================================================

**Using the Technical Add-on for IBM MQ-Series developed for DHL allows you submit any message to IBM MQ-Series resulting from a Splunk query, using the following summarised cycle:**

- You run a Splunk search, which generates any number of results containing the message payloads to be sent as well as their identifiers (message ID)

- Additional information are defined at search time, such as the destination Queue manager and the Queue

- A custom command is called to interract and submit these messages to IBM MQ as part of a ``batch``

- The batch is submitted as pending from approval

- An approver receives a notification and approves your demand eventually, the approver can as well decide to refuse the batch and cancel its submission

- After a couple of minutes, the batch is taken into account and messages start to be publishing by the Splunk Heavy Forwarders

- Depending on the message nature (single line versus multiline) and the volume, the batch sent can take a few minutes to be full processed, or more

Sending messages to IBM MQSeries with the putmqrelay command
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**To send messages effectively, you will use a custom command named ``putmqrelay`` which requires the following arguments:**

- ``field_message_id``: the name of the Splunk field containing the message identifiers
- ``field_message``: the name of the Splunk field containing the message payloads
- ``field_appname``: the name of the Splunk field containing the application value, this is a string value which identifies the application
- ``field_region``: the name of the Splunk field containing the region value, this is a string value which idenfities the region for these messages
- ``field_manager``: the name of the Splunk field IBM MQ Queue manager, which needs to be defined on the Splunk Search Heads and the consumers for this application/region 
- ``field_queue``: the name of the Splunk field containing the IBM MQ Queue destination for the messages
- ``dedup``: (true/false) optional dedup at the command level which ensures messages being sent are unique, this can be handled on the upstream search level too
- ``comment``:  optional comment for the submission, this comment will be logged at different levels and made available for the approver to review
- ``max_batchsize``: optional maximal amount of messages per batch, defaults to 10000 messages, when the limit is reached, one or more additional batches are created to accomodate with the query

When the command is called, it will render a summary of the request with the following information:

- ``action``: (success/failure) the result of the operation submit request
- ``result``: a human reable message describing the result of the operation
- ``results_count``: how many messages were requested to be sent by the upstream search
- ``processed_count``: how many messages the command handled
- ``kvstore_count``: how many messages where generated in the Splunk remote KVstore

A simple example of sending a message to MQ:

::

   | makeresults
   | eval message="This is a test demo payload", appname="DMG", region="LAB", manager="QM1", queue="DEV.QUEUE.1", MsgId=md5(message)
   | putmqrelay field_message_id="MsgId" field_message="message" field_appname="appname" field_manager="manager" field_queue="queue" field_region="region" dedup="False" comment="Demo message"

Which results in:

.. image:: img/putmqrelay1.png
   :alt: putmqrelay1.png
   :align: center
   :width: 1200px

Sending a real batch of messages would look like:

.. image:: img/putmqrelay2.png
   :alt: putmqrelay2.png
   :align: center
   :width: 1200px

At this stage, a batch has been generated and is pending from approval. (see the next section)

Managing MQ submission batches
==============================

**The user interface MQ Manage Batches is designed to allow users to interract with the life cycle of the batches:**

.. image:: img/manage_batches1.png
   :alt: manage_batches1.png
   :align: center
   :width: 1200px

Batches statuses
^^^^^^^^^^^^^^^^

**A single batch can appear in different states:**

- ``pending_validation``: the batch was sumitted and is pending from approval by an approver member of the application role
- ``pending_processing``: the batch was approved already, and is pending from being processed by the application
- ``temporary_failure``: the batch was approved and attempted once or more times, but has currently failed to be processed successfully
- ``permanent_failure``: the batch has reached the maximal amount of attempts, and is now permanently failed, it will not be processed again
- ``succesful``: the batch was processed successfully

Validating a batch pending from approval
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**A batch that is pending from approval can be approved by relevant users depending on their Splunk role membership:**

.. image:: img/manage_batches2.png
   :alt: manage_batches2.png
   :align: center
   :width: 1200px

.. image:: img/manage_batches3.png
   :alt: manage_batches3.png
   :align: center
   :width: 1200px

**A note can be added by the approver, this information is added to:**

- The different log files technically invovled in the process, and indexed in Splunk automatically
- An history KVstore collection that retains the validation history for easy auditing purposes

*Log files:*

- See the report: "DHL MQ Logs - managebatch logs (batch validation by approvers)"

::

    (`idx_mq`) sourcetype="mq:actions:mq_publish_message:managebatch"

.. image:: img/manage_batches4.png
   :alt: manage_batches4.png
   :align: center
   :width: 1200px

*History approval KVstore collection:*

::

    | inputlookup mq_publish_batch_history | sort - limit=0 ctime | eval ctime=strftime(ctime/1000, "%c")

Shortcut access:

.. image:: img/manage_batches5.png
   :alt: manage_batches5.png
   :align: center
   :width: 1200px

Managing a batch pending from processing
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**When a batch is pending from processing, this means it is approved but has not been handled by the application, this can happen for various reasons:**

- Right after the initial validation, it can take a few minutes before the messages will start to be processed
- Due to technical issues, if the Heavy Forwarders responsible the consumption of these messages are not currently available, or cannot access the Splunk infrastructure properly

**A user with the relevant permissions can decide to cancel the job via the UI, as it is already approved this function is disabled automatically:**

.. image:: img/manage_batches7.png
   :alt: manage_batches7.png
   :align: center
   :width: 1200px

Managing a batch pending in temporary failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**When a batch is in temporary failure, this means that we already attempted at least once to send the messages to MQ, but the operation has failed at least once:**

- A policy defined on the SHC says how many attempts will be processed for the same messages (default to 10 attempts)
- When the maximal number of attempts for a given message has been reached, the status moves automatically to permanent failure
- The manage batch UI show up with the latest error encountered while trying to send to MQ

.. image:: img/manage_batches8.png
   :alt: manage_batches8.png
   :align: center
   :width: 1200px

**The Overview user interface will show as well the activity of the failing messages:**

.. image:: img/manage_batches9.png
   :alt: manage_batches9.png
   :align: center
   :width: 1200px

**When a batch is in temporary failure, the manage batch UI allows the submitter to cancel the batch is necessary: (only users with the application submitter roles, or the super admin, can cancel a running job)**

.. image:: img/manage_batches10.png
   :alt: manage_batches10.png
   :align: center
   :width: 1200px

Managing a batch pending in permanent failure
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**When a batch of messages has reached the maximal number of attempts defined by the application policy, the status moves from temporary_failure to permanent_failure:**

.. image:: img/manage_batches11.png
   :alt: manage_batches11.png
   :align: center
   :width: 1200px

**At this stage, the batch can no longer be canceled as it was already by the system, and the manage batch UI would show the following message if user with approval roles tries to manage it:**

.. image:: img/manage_batches12.png
   :alt: manage_batches12.png
   :align: center
   :width: 1200px

.. hint:: The records will remain in the KVstore for a certain of time which is defined by the retention policy, when this period is over, records are permanently purged

Managing a successful batch
^^^^^^^^^^^^^^^^^^^^^^^^^^^

**When a batch of messages was successfully sent to MQ, the batch appears as successful in the manage batch UI:**

.. image:: img/manage_batches13.png
   :alt: manage_batches13.png
   :align: center
   :width: 1200px

**At this stage, the manage cannot be managed any longer as it has been processed already, the UI would show an informational message when accessing to it:**

.. image:: img/manage_batches14.png
   :alt: manage_batches14.png
   :align: center
   :width: 1200px

Verifying the status of the MQ submission
=========================================

MQ Overview dashboard
^^^^^^^^^^^^^^^^^^^^^

**Splunk administrators, MQ submitters and approvers can rely on the MQ Overview dashboard to verify the activity of the MQ resubmission solution:**

.. image:: img/verify_status1.png
   :alt: verify_status1.png
   :align: center
   :width: 1200px

**Depending on the user status, you will:**

- See all applications and all messages if you are an administrator, or a member of the MQ super admin role
- See all applications and messages for the list of applications you are a member of

**The dashboard show all revelant information, activity and shortcut to all pieces of needed information, such as:**

- The total number of messages stored in the KVstore collection
- The number of successfully submitted messages
- The number of messages in pending status
- The number of batches pending for approval
- The number of messages currently in temporary_failure
