Release notes
-------------

Version 1.0.28
==============

- Delegate the MQ backlog KVstore collection old records purge to a seperate scheduled reports relying on a new custom command for better performances and less CPU cycles required on the SHC (custom command: purgebacklog, report: DHL MQ Logs - MQ backlog purge logs)
- Manage batch: allow to cancel a batch which remains in pending from processing but might have been partially submitted already, better handle canceling a batch in temporary failure (custom command: managebatch)
- set the schedule_window to auto by default for scheduled reports and alerts on the SHC that can accomodate with the setting with no consequences 

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
