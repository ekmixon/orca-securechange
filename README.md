
# Orca-SecureChange

[![CircleCI](https://circleci.com/gh/Tufin/orca-securechange.svg?style=svg)](https://circleci.com/gh/Tufin/orca-securechange)

## Overview
A SecureChange add-on to automate Kubernetes egress connectivity on firewalls


## Getting Started

These instructions will get you a copy of the project up and running on the SecureChange machine. 
See the Installation section below for notes on how to deploy the project.

### Define an API token in Orca

* Login to Orca, go to Settings and create an API token for the bearer authentication. Select 'agent' for the token scope and give it the label 'secure-change'.

### Instal the integration package on SecureChange server

* Download the installation package from the [release](https://github.com/Tufin/orca-securechange/releases) tab on Github.
* Upload the package setup_orca_ps_scripts-x.y.z.run to the SecureChange machine.
* Start the installation: sh setup_orca_ps_scripts-x.y.z.run. 
    * Enter a valid username and password for both SecureChange and SecureTrack.
    * For Orca authentication enter username="orca" and password="Bearer <Orca_API_Token>".
* Open the file **/usr/local/orca/conf/custom.conf** and define the following parameters:
    * hostname=orca.tufin.io
    * For every instance of /bridge/X/Y/Z - replace X with your ORCA DOMAIN ands Y with ORCA PROJECT.
    * securechange host = <your securechange address>
    * securetrack host = <your securetrack addr:q!:ess>

### Configure SecureChange for the integration

**Add a new script to SecureChange**

* Login to SecureChange through the web UI and open Settings -> SecureChange API.
    * Click on the Add script button.
    * Give a name to the new script.
    * In the "Full path" field enter the following path: /usr/local/orca/bin/rest_integration.py.
    * Enter the Trigger Group Name.
    * Select the Orca workflow.
    * Select all the triggers in the Triggers section.
    * Save settings.
**Add a new workflow in SecureChange**   

* Create a Modify Group workflow in SecureChange. The first step of the workflow should include the following 
field types and names. The package comes with default names which can be changed after installation.

    * Workflow name: Orca Group Change
    * First step name: Submit network object group request

    | Field Type         | Field Name                   |
    | ----------         | ----------                   |
    | multi_group_change | Modify network object group  |
    | text_field         | Orca Task ID                 |
    | text_field         | Group Name                   |
    
### Preparing the Firewall Policies

* The SecureChange workflow triggered from Orca is based on "Modify Group"
* It will look for certain group names accross the monitored firewalls and update them according to the egress end-points (destination) in Orca.
* You need to create these groups manually on the relevant firewalls using the following naming convention for group names: &lt;domain&gt;.&lt;project&gt;.&lt;namespace&gt; 
* You also need to create rules on the firewalls that use these groups as destinations (the source should be the Kubernetes cluster IPs or subnet).
In case the firewall does not allow a rule withoput any destination, you may add a "fake destination".
* Orca does not yet discover protocols and ports. Due to this, there are two options to define the rule "service" field:
    * Use "Any" service and optionally apply Tufin's Automatic Policy Generator (APG) to replace them by specific service later
    * Use https which is the most common protocol for reaching end-points


## License

This project is licensed under the Apache License Version 2.0 - see the [LICENSE](LICENSE) file for details
