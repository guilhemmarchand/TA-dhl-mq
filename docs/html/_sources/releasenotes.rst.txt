Release notes
-------------

Version 1.0.27
==============

- To improve the performance of the mutliline and re-attempt modular alert process, the successfully proceeded records are notified to the remote KVstore by batching via a third party report invovling a separate custom command
- fix issue in log generation from the managebatch custom command which generates twice double quotes

Version 1.0.26
==============

- MQ Manage Batch UI: sort by last modified batch
- Remove alert suppression for the consumption modular alert for performance improvements purposes

Version 1.0.25
==============

- Prevents duplication from the modular alert when the Splunk remote environment is under heavy load
- Fix the MQ Manage batch dashboard issue where a single batch appears more than once depending on the status of the messages
