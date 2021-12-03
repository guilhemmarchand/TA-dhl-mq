Requirements
------------

MQ Client librairies
####################

The MQ client librairies are required on the Splunk instances acting as the consumers of the messages, these are the Splunk Heavy Forwarders.

.. hint:: The MQ client librairies are not required on the Splunk Search Head layer

See the installation procedure.

q command
#########

The "Q" command (called mqgem) is the interface we use to interract with IBM MQ series.

This binary is provided by DHL and allows especially to mass submit messages to IBM MQ in a simple and effiscient manner.

The Q command in its latest verions requires a license, to be provided by DHL, an older free version can as well be used.

The "Q" command has to be made available on the Splunk instances consuming the messages (Splunk Heavy Forwarders).

.. hint:: The Q command access path is configurable in the Add-on, it can be installed in the same directory than mqm (MQ librairies), but it doesn't have to be

Splunk API communication between the Heavy Forwarders and the SHC members
#########################################################################

**To retrieve and handle the KVstore records, the Heavy Forwarders require to use a bearer token to be configured on the SHC.**

*For more information about bearer tokens:*
- https://docs.splunk.com/Documentation/Splunk/latest/Security/UseAuthTokens

Note: technically each forwarder can use a different bearer token which is configurable in the Add-on configuration UI of the HF, you may as well use the same bearer token on all Heavy Forwarder for that particular context.

**A bearer token must be created on the SHC which is going to be used by the Heavy Forwarders to perform their various operations on different KVstore collections part of the TA.**

The bearer token must match a service account user that is a member of the builtin role:

- ``mqsubmission_superadmin``
