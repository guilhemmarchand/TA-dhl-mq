Development and build process
-----------------------------

**The Application is built on top of the Splunk Addon factory generator, which allows to build and maintain consistent and modular Splunk applications using the most up to date content:**

- https://github.com/splunk/addonfactory-ucc-generator

- https://splunk.github.io/addonfactory-ucc-generator/

For development purposes, different dependencies should be installed on the development platform, as follows.

Dependencies for developers
===========================

- Operating system: Linux or MacOS (seriously, what else?)

- Access to the machine in terminal (SSH if remote)

- Python 3.7 or later

- Sphinx librairies for the generation of the documentations

- Splunk ucc-gen

Sphinx librairies and documentation generation
##############################################

**The documentation of the TA is hosted as part of code being stored in the ```docs`` directory, this consists in rst files using the Sphinx language:**

- https://www.sphinx-doc.org/

The following librairies are required on the host generating the updated documentation:

- https://pypi.org/project/Sphinx/

- https://pypi.org/project/sphinx-rtd-theme/

How to update the documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**To update the documentation, you will update the rst files then run the following command:**

::

    cd docs
    make html

Any error in the syntax or missing files such as missing images, will be visible in the output of the make generation command.

Once the documentation has been updated, and the changes commited to the remote repository in GitHub, the GitHup pages Website will render the changes after a few minutes.

ucc-gen and updating the Technical Add-on
#########################################

**The development of the Technical Add-on relies on the Splunk UCC generator:**

- https://github.com/splunk/addonfactory-ucc-generator

- https://splunk.github.io/addonfactory-ucc-generator/

**When performing changes in the application, you will:**

- update the ``version.txt`` file to increment the version release number

- perform your changes effectively, by managing files in the ``TA-dhl-mq/package`` directory (such as modifying a view, etc)

- run the ucc-gen command via a shell wrapper:

::

    cd TA-dhl-mq/build
    ./buil.sh

- This produces automatically a new packaged application, located in the ``TA-dhl-mq/output/`` directory

- The tgz package is ignored in GitHub on purpose, you will take this new tarball archive, publish it as a new release in the repository releases, and finally deploy to your Splunk environment

*example:*

::

    TA-dhl-mq
    TA-dhl-mq_1023.tgz
    release-sha256.txt

- the content of the ``TA-dhl-mq`` directory is the uncompress content from the generated package (and is ignored in Git on purpose too)

- the tgz file is the package to be released in GitHub, and deployed to Splunk
