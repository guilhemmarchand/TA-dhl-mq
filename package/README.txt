# DHL Addon for MQ

## Installation

The Add-on installation is very straight forward, it can be installed in a standalone instance (Search Head or Heavy Forwarder) or in a Search Head Cluster (SHC).

In short, the application works in two specific modes:

- A server mode where the passthrough mode is enabled
- A client mode where the passthrough mode is disabled, and the access to the central KVstore configured

### Deployment on the search head layer

On the search head layer, the app does not have any external requirements, proceed either as:

- Standalone: installation via CLI or via Splunk Web
- SHC: installation via the SHC deployer

For Search Head Clusters, do not perform the configuration on the SHC deployer but instead perform the configuration via the UI on any member of the SHC.
Every part of the configuration (from the accounts to the advanced configuration) will be automatically repliacted to all the SHC members.