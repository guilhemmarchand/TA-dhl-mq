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

To perform various actions related to the life-cycle of the application, every Splunk Heavy Forwarder needs to be able to reach the Splunk API on the SHC members.

The authentification is achieved using a bearer token approach, which is defined on the SHC side, configured in the Add-on configuration UI on the Heavy Forwarders and stored encrypted in the Splunk secure store.
