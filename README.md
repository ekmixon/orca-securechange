
# Orca-SecureChange

[![CircleCI](https://circleci.com/gh/Tufin/orca-securechange.svg?style=svg)](https://circleci.com/gh/Tufin/orca-securechange)

## Overview
A SecureChange add-on to automate Kubernetes egress connectivity on firewalls


## Getting Started

These instructions will get you a copy of the project up and running on SecureChange machine. 
See the Installation section for notes on how to deploy the project.


### Prerequisites

* To start the Ora-SecureChange integration, you must download the package from the [release](
https://github.com/Tufin/orca-securechange/releases) tab on Github.

* You should get Orca token for the Bearer authentication

* You must create a Group-Change workflow in SecureChange. The first step of the workflow should include the following 
fields types and names. The package comes with default names which can be changed after installation.

    * Workflow name: Orca Group Change
    * First step name: Submit network object group request

    | Field Type         | Field Name                   |
    | ----------         | ----------                   |
    | multi_group_change | Modify network object group  |
    | text_field         | Orca Task ID                 |
    | text_field         | Group Name                   |


### Installation

* Upload the package setup_orca_ps_scripts-x.y.z.run to SecureChange machine
* Start the installation: sh setup_orca_ps_scripts-x.y.z.run 
    * Enter a valid username and password for both SecureChange and SecureTrack
    * For Orca authentication enter username as orca and password as "Bearer Orca-Token"
* Login to SecureChange WEB UI and open the SecureChange API under the Settings tab
    * Click on the Add script button
    * Give a name to the new script
    * In the "Full path" field enter the following path: /usr/local/orca/bin/rest_integration.py
    * Enter the Trigger Group Name
    * Select the Orca workflow
    * Select all the triggers in the Triggers section
    * Save settings
* Update local address of SecureChange in the custom.conf file under /usr/local/orca/conf


## License

This project is licensed under the Apache License Version 2.0 - see the [LICENSE](LICENSE) file for details