
# Orca-SecureChange

[![CircleCI](https://circleci.com/gh/Tufin/orca-securechange.svg?style=svg)](https://circleci.com/gh/Tufin/orca-securechange)

## Overview
A SecureChange add-on to automate Kubernetes egress connectivity on firewalls


## Getting Started

These instructions will get you a copy of the project up and running on SecureChange machine. 
See the Installation section for notes on how to deploy the project.


### Prerequisites

* To start the Ora-SecureChange integration, you must download the package from the [release](
https://github.com/Tufin/orca-securechange/releases) tab on Github or build the package by copying the 
repository into the Linux machine and running the make command.

* You should get Orca token for the Bearer authentication

* You must create a GroupChange workflow in SecureChange. The first step of the workflow should include the 
following field types and names (the names can be changed but the JSON files and ticket template files must 
be updated accordingly). 
    
    | Field Type         | Field Name                   |
    | ----------         | ----------                   |
    | multi_group_change | Modify network object group  |
    | text_field         | Orca Task ID                 |
    | text_field         | Group Name                   |


### Installation

Once you upload the package to your machine you can start the installation:

* Start the installation by executing package: sh setup_orca_ps_scripts-1.0.0.run 
* Enter a valid username and password for either SecureChange and SecureTrack
* For Orca authentication enter username as orca and password as "Bearer <Orca-Token>"
* Login to SecureChange WEB UI and open the SecureChange API under the Settings tab
    * Click on the Add script button
    * Give a name to the new script
    * In the Full path field enter the following path: /usr/local/orca/bin/rest_integration.py
    * Enter the Trigger Group Name
    * Select the Orca workflow
    * Select all the triggers in the Triggers section
    * Save settings


## License

This project is licensed under the Apache License Version 2.0 - see the [LICENSE](LICENSE) file for details