MQ managers Configuration
-------------------------

**In a nutshell:**

- Queue managers need to be referenced with their logical definition (the MQ manager idenfitier) om both the SHC, and the Heavy Forwarders that will consume these messages
- On the SHC, only the definition needs to be added, the target (port, adress, etc) only matters on the Heavy Forwarders
- On the Heavy Forwarders consuming messages for the regions and the applications, the MQ manager account must contains the proper target definition effectively

**For the purpose of the documentation, we will assume that we configure two MQ managers:**

- **QM1** that can be reached via the address ``mq1-region1`` on the port ``1414`` and the channel to be used ``DEV.APP.SVRCONN``
- **QM2** that can be reached via the address ``mq2-region1`` on the port ``1414`` and the channel to be used ``DEV.APP.SVRCONN``

MQ managers definition on the SHC
#################################

On the SHC, open the TA-dhl-mq application and access to the configuration UI, then add a new account as follows:

.. image:: img/config_mq1.png
   :alt: config_mq1.png
   :align: center
   :width: 800px

- The address, port and channel are not important on the SHC, these information are only used on the consumers side
- All that we need is the definition of the MQ manager (Account)
- On the consumers side (HFs), a given logical Queue Manager reference, say MQ1, can totally address different targets on a per consumer basis, as the target is defined on the consumer itself

*repeat the operation for every MQ manager, all managers need to be referenced on the SHC*

MQ managers definition on the HFs
#################################

On the consumers side, aka Heavy Forwarders, we define whichever MQ manager the consumer needs to consume messages for, as well as the proper definition for the target, port and channel.

Two consumers can consume messages for a same named Queue Manager (say QM1) and put messages in different systems reachable at different addresses, the KVstore filters allow to have different configuration to address all use cases.

