Administrative Reference matrix
===============================

Alerts and reports
------------------

Scheduled alerts reference
^^^^^^^^^^^^^^^^^^^^^^^^^^

DHL MQ messages publishing - relay publishing
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

**This is the main modular alert which handles submission to MQ for:**

- Batches of multi-line messages (the field ``multiline`` in the KVstore contains the boolean with value ``1``)
- Re-attempt for submission failures for both single-line and multi-line messages

**SHC versus HF:**

- SHC: This alert when running on the SHC will maintain the KVstore records, especially it will purge old records when their expiration is reached
- HFs: This alert performs the submission to IBM MQ

DHL MQ messages publishing - batch failing detected
;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;;

**This is an out of the box alert to detect when a batch is failing, either temporary or permanently.**

**SHC versus HF:**

- SHC: This alert is to be running on the search head layer
- HFS: This alert will not do anything on the HFs

