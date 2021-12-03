.. TA-dhl-mq documentation master file

Welcome to the DHL Splunk Add-on for MQ submission documentation
================================================================

**The DHL Splunk Add-on for MQ submission provides services for:**

- Publishing on demand messages to various IBM MQ managers in scalable, resilient and distributed manner using various Splunk components
- Handling the message life cycle at any point in time with RBAC capaibilities
- Hanlding temporary and permanent failures with automated retries based on a life cycle concept
- High availability with automated fail-over using multiple Splunk Heavy Fowarders working in a HA group concept

**High level application deployment topology diagram:**

.. image:: img/diagram.png
   :alt: diagram.png
   :align: center
   :width: 1000px

**Application workflow diagram and main components:**

.. image:: img/workflow.png
   :alt: workflow.png
   :align: center
   :width: 1000px

*In a nutshell:*

- The Add-on is deployed on the Search Head Cluster level (DHL uses a Search Head Cluster across multiple sites)

- Users interact with the application with a pre-defined workflow involving different components to create and maintain records in a Splunk distributed KVstore.

- The KVstore records contain the message payloads in addition with various Metadata such as the application name, the region, MQ related information (managers, queues. Etc), statuses, user requesting information.

- By nature, the KVstore is automatically replicated amongst the SHC members and is available on all DHL deployed sites.

- A number of Splunk Heavy Forwarders are deployed on a per site basis and leverage the Splunk API to retrieve and maintain the KVstore records with configurable filtering rules which allow dedicating a single Heavy Forwarder to consume the records it is responsible for.

- An MQ Series Queue manager definition is created on both the Search Head Cluster and the Heavy Forwarder(s) destinated to consume messages from this context (based on any Metadata available in the KVstore structure), a same Queue manager reference can exist in any number of sites and be targeting a different MQ broker by its definition.

- A concept of automatic retries and eviction policy is part of the application to handle the life cycle of the records, from their initial submission requests (pending state), to their publication (success), or temporary or definitive failures. (temporary_failure, permanent_failure)

- Messages are submitted to the MQ third party using a low level high performance third party (q command) which allow batching single line messages for the better performances (which single line messages represent around 70% of the total volume of messages), while multiline messages are handled with the same q command but a different workflow handling the records individually at a lower rate.

Overview:
=========

.. toctree::
   :maxdepth: 2

   compatibility
   requirements

Deployment and configuration:
=============================

.. toctree::
   :maxdepth: 2

   deployment
   configuration
   high_availability
   rbac

User guide:
===========

.. toctree::
   :maxdepth: 2

   userguide

Troubleshoot:
=============

.. toctree::
   :maxdepth: 1

   troubleshoot

Versions and build history:
===========================

.. toctree::
   :maxdepth: 1

   releasenotes
