#########################################################################################
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.                    #
# SPDX-License-Identifier: MIT-0                                                        #
#                                                                                       #
# Permission is hereby granted, free of charge, to any person obtaining a copy of this  #
# software and associated documentation files (the "Software"), to deal in the Software #
# without restriction, including without limitation the rights to use, copy, modify,    #
# merge, publish, distribute, sublicense, and/or sell copies of the Software, and to    #
# permit persons to whom the Software is furnished to do so.                            #
#                                                                                       #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,   #
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A         #
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT    #
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION     #
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE        #
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                                #
#########################################################################################

import boto3
import argparse
import sys
import json
import logging

# Defining global variables that capture info on parameters passed to script
TARGET = None

# defines what type of target specified
# Is it target server(s) id(s), key=value pair or all
TARGET_TYPE = None

SOURCE = None

# Defines what type of source specified. Is it a source server or launch template
SOURCE_TYPE = None

# Whether or not the launch settings are to be copied
# default is False
COPY_LAUNCH_SETTINGS = False

# Whether or not the launch settings are to be copied
# default is False
COPY_POST_LAUNCH_SETTINGS = False

# This variable gives us the name of the launch settings/configuration file name if it was passed as an argument
# If no value was passed, it is set to None
LAUNCH_SETTINGS_FILE = None

# This variable gives us the list of properties to copy from the EC2 launch template
PARAMETERS = ['SubnetId','AssociatePublicIpAddress','DeleteOnTermination','Groups','Tenancy','IamInstanceProfile','InstanceType']

# Logger for logging messages
LOGGER = logging.getLogger()

# ---------------------------------------
#
# Function to display usage options
#
# ---------------------------------------
def usage_message():
    msg = f'''
        Script to copy launch template and launch configuration across multiple replicating servers in AWS Application Migration Service (MGN)
        python {sys.argv[0]} --target target [--template-id  template-id | --source-server source-server] --copy-launch-settings --launch-settings-file launch-settings-file --parameters [SubnetId,InstanceType,AssociatePublicIpAddress,DeleteOnTermination,Groups,Tenancy,IamInstanceProfile] --debug
        examples:
        Copy launch template ONLY from source server s-11111 to s-22222 and s-33333
        python {sys.argv[0]} --target s-22222,s-33333 --source-server s-11111

        Copy launch settings and launch template from source server s-11111 to servers with tag key=env and value=dev
        python {sys.argv[0]} --target env=dev --source-server s-11111 --copy-launch-settings

        Copy launch settings and launch template from source server s-11111 to all replicating servers
        python {sys.argv[0]} --target all --source-server s-11111 --copy-launch-settings

        Copy launch template from lt-12345 to all replicating servers but only copy the parameters SubnetId,InstanceType,AssociatePublicIpAddress from the launch template.
        python {sys.argv[0]} --target all --template-id lt-12345 --parameters SubnetId,InstanceType,AssociatePublicIpAddress

        Copy launch template from lt-12345 to all replicating servers and launch configuration from file lf.json
        python {sys.argv[0]} --target all --template-id lt-12345 --copy-launch-settings --launch-settings-file.json

    '''
    LOGGER.info(msg)
    return msg
# ---------------------------------------
#
# Function to set logging
#
# ---------------------------------------
def set_logging(debug):

    # Clear any previous loggers
    for h in LOGGER.handlers:
        LOGGER.removeHandler(h)

    # Set the format of the log messages
    FORMAT = '%(levelname)s - %(message)s'

    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter(FORMAT))
    LOGGER.addHandler(h)

    # Set the log level
    if debug == True:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.INFO)

    # Suppressing messages below ERROR for boto3 and other loggers
    logging.getLogger('boto3').setLevel(logging.ERROR)
    logging.getLogger('botocore').setLevel(logging.ERROR)
    logging.getLogger('urllib3').setLevel(logging.ERROR)

# ---------------------------------------
#
# Function to validate if correct arguments have been specified
#
# ---------------------------------------
def validate_arguments(args):

    global TARGET
    global TARGET_TYPE
    global SOURCE
    global SOURCE_TYPE
    global COPY_LAUNCH_SETTINGS
    global COPY_POST_LAUNCH_SETTINGS
    global LAUNCH_SETTINGS_FILE
    global PARAMETERS
    
    # This function checks if the right combination of arguments have been passed

    if args.get('target') != None and (args.get('template_id') != None or args.get('source_server') != None):

        # Check what type of target has been passed
        if args.get('target').startswith('s-'):
            TARGET = args.get('target')
            TARGET_TYPE = 'servers'
        elif args.get('target') == 'all':
            TARGET = args.get('target')
            TARGET_TYPE = 'all'
        elif '=' in args.get('target'):
            TARGET = args.get('target')
            TARGET_TYPE = 'key/value'
        else:
            LOGGER.error('Incorrect value for target specified.')
            LOGGER.error('Target can be a comma seprated list of serverids, all or key/value pair specified using the format key=value.')
            usage_message()
            exit(1)

        # Check if both source server and launch template passed
        if args.get('source_server') != None and args.get('template_id') != None:
            LOGGER.error('Both source launch template and server specified.')
            LOGGER.error('Either a launch template or a source server id should be passed and not both.')
            usage_message()
            exit(1)
        else:
            # Check what source has been passed
            if args.get('source_server') != None:
                SOURCE_TYPE = 'server'
                SOURCE = args.get('source_server')
            else:
                SOURCE_TYPE = 'launch_template'
                SOURCE = args.get('template_id')

        # Check to see if --copy-lauch-settings specified along with --launch-settings file or source server
        # If not, show an error and exit as either a source server or a launch settings file needs to be specified with this option
        if args.get('copy_launch_settings') == True and args.get('source_server') == None and args.get('launch_settings_file') == None:
            LOGGER.error('Option to copy launch settings used without providing either a source server or launch settings json file.')
            usage_message()
            exit(1)

        # Check to see if --copy-post-lauch-settings specified along with source server
        # If not, show an error and exit as either a source server or a launch settings file needs to be specified with this option
        if args.get('copy_post_launch_settings') == True and args.get('source_server') == None:
            LOGGER.error('Option to copy post launch settings used without providing a source server.')
            usage_message()
            exit(1)

        COPY_LAUNCH_SETTINGS = args.get('copy_launch_settings')
        COPY_POST_LAUNCH_SETTINGS = args.get('copy_post_launch_settings')
        LAUNCH_SETTINGS_FILE = args.get('launch_settings_file')

        # Check to see if customer parameters need to be copied or all
        if args.get('parameters') != None:
            # check to see if valid options passed for parameters argument
            PARAMETERS = args.get('parameters').split(',')
            test_parameters = PARAMETERS.copy()

            for p in ['SubnetId','AssociatePublicIpAddress','DeleteOnTermination','Groups','Tenancy','IamInstanceProfile','InstanceType']:
                try:
                    test_parameters.remove(p)
                except:
                    continue

            if len(test_parameters) > 0:
                LOGGER.error(f'Incorrect parameter(s) specified with the --parameters argument. {test_parameters}')
                LOGGER.error(f'Available parameters to copy: SubnetId,AssociatePublicIpAddress,DeleteOnTermination,Groups,Tenancy,IamInstanceProfile,InstanceType')
                exit(1)


        return True
    else:
        return False

# ---------------------------------------
#
# This function takes a source server id or a launch template id and returns the EC2 default Launch Template associated with it
#
# ---------------------------------------

def get_template_data(source_server_or_template_id):

    # global TARGET
    # global TARGET_TYPE
    # global SOURCE
    # global SOURCE_TYPE
    # global COPY_LAUNCH_SETTINGS

    mgn = boto3.client('mgn')
    ec2 = boto3.client('ec2')

    # Check if a server id was passed in source_server_or_template_id
    if SOURCE_TYPE == 'server':
        LOGGER.debug('Source type is server')
        response = mgn.get_launch_configuration(
            sourceServerID=source_server_or_template_id
        )

        versions = ec2.describe_launch_template_versions(
            LaunchTemplateId=response['ec2LaunchTemplateID'],
        )

    else:
        LOGGER.debug('Source type is template id')
        # Launch template ID was passed to this function
        versions = ec2.describe_launch_template_versions(
            LaunchTemplateId=source_server_or_template_id,
        )

    # Get the default version template data
    version_to_return = {}
    for version in versions['LaunchTemplateVersions']:
        if version['DefaultVersion'] == True:
            version_to_return = version.copy()
    
    return version_to_return

# ---------------------------------------
#
# This function takes a source server id and returns the launch configuration
#
# ---------------------------------------

def get_source_launch_configuration(source_server):
    # global SOURCE_TYPE
    # global LAUNCH_SETTINGS_FILE

    mgn = boto3.client('mgn')
    if LAUNCH_SETTINGS_FILE != None:
        # Launch settings file was passed as an argument. Read the file and load launch configuration
        LOGGER.debug('Launch settings json file specified. Reading data.')
        with open(LAUNCH_SETTINGS_FILE) as f:
            data = json.load(f)
            return_source_launch_configuration = {
                'copyPrivateIp': data['copyPrivateIp'],
                'copyTags': data['copyTags'],
                'launchDisposition': data['launchDisposition'],
                'targetInstanceTypeRightSizingMethod': data['targetInstanceTypeRightSizingMethod']
            }
    elif SOURCE_TYPE == 'server':
        LOGGER.debug('Source server used for launch settings data. Reading data from source server.')
        return_source_launch_configuration = mgn.get_launch_configuration(
            sourceServerID=source_server
        )

    else:
        return_source_launch_configuration = None

    LOGGER.debug('Printing launch settings json:\n')
    LOGGER.debug(return_source_launch_configuration)

    return return_source_launch_configuration

# ---------------------------------------
#
# This function returns the list of 'launch configuration' for each server ids matching the tag key/value pair passed. 
# It could either receive a value of 'all' or a value in the format 'tag_key=tag_value'
# If 'all' is passed, this function returns all source servers replicating in MGN
# If tag_key=tag_value is passed (notice there is no space in between), it returns servers having this key/value pair
# The user may also pass a comma delimited list of replicating server ids. eg: s-111111,s-2222222
#
# ---------------------------------------
def get_target_servers_configuration_list(target):

    # Setting this variable to false. This indicates we are not searching by tags
    filter_by_tags = False
    tag_key = False
    tag_value = False

    # Check if the value is all
    if target == 'all':
        filters = {
            'isArchived': False,
        }

    # Check if the value is in the format of tag_key=tag_value
    elif '='  in target:
        filters = {
            'isArchived': False,
        }
        
        # set this variable to True
        # Later, this variable will be used to further filter the results based on tag key/value
        filter_by_tags = True
        tag_key = target.split('=')[0]
        tag_value = target.split('=')[1]

    # Look for the presence of 's-'. This indicates presence of server id(s)
    elif 's-' in target:
        filters = {
            'isArchived': False,
            'sourceServerIDs': target.split(',')
        }
    
    else:
        # Exit the program since the right value was not passed for this argument
        LOGGER.error('Incorrect value for target specified.')
        LOGGER.error('Target can be a comma seprated list of serverids, all or key/value pair specified using the format key=value.')
        exit(1)

    # Calling a function which will extract all replicating servers in MGN based on the filters set above
    target_servers = search_replicating_servers(filters, filter_by_tags, tag_key, tag_value)

    # Call get_launch_configuration for each server
    # The output will be in this format.
    '''
    [
        {
            'bootMode': 'LEGACY_BIOS'|'UEFI',
            'copyPrivateIp': True|False,
            'copyTags': True|False,
            'ec2LaunchTemplateID': 'string',
            'launchDisposition': 'STOPPED'|'STARTED',
            'licensing': {
                'osByol': True|False
            },
            'name': 'string',
            'sourceServerID': 'string',
            'targetInstanceTypeRightSizingMethod': 'NONE'|'BASIC'

        },
    ]
    '''
    configuration_list = []

    mgn = boto3.client('mgn')
    # For each server, call get_launch_configuration
    for server in target_servers:
        configuration = mgn.get_launch_configuration(
            sourceServerID=server['sourceServerID']
        )
        configuration_list.append(configuration)
    return configuration_list

# ---------------------------------------
#
# This function is called by get_target_servers_configuration_list
# It invokes the MGN api describe_source_servers and returns the list of servers matching critera
#
# ---------------------------------------
def search_replicating_servers(filters, filter_by_tags, tag_key, tag_value):

    mgn = boto3.client('mgn')

    return_list = []
    response = mgn.describe_source_servers(
        filters=filters,
        maxResults=100
    )

    return_list = response['items']

    while 'nextToken' in response:
        response = mgn.describe_source_servers(
        filters=filters,
        maxResults=100,
        nextToken = response['nextToken']
        )
        return_list.extend(response['items'])

    # Now that all the servers have been extracted, check if they need to be further filtered by tag key/value
    if filter_by_tags == True:
        # New list created which would have filtered results
        new_list = []

        # Evaluate each server in the list return_list and check its tags
        # A user may pass just the tag key and * for the value. In which case the tag value is not evaluated
        for server in return_list:
            if 'tags' in server:
                for tag in server['tags']:
                    if tag == tag_key and (server['tags'][tag] == tag_value or tag_value == '*'):
                        # Found a server matching the tag key/value
                        # Add it to the new list
                        new_list.append(server)
                        break

        return_list=new_list

    # Remove source server from the target servers list
    # The source server may show up in target list when tag key/value pair is specified or all is specified
    # this is needed only when a source server is specified in command line arguments and not launch template
    if SOURCE_TYPE == 'server':
        iterate_list = return_list.copy()
        return_list = []
        for server in iterate_list:
            if server['sourceServerID'] != SOURCE:
                return_list.append(server)

    # Remove servers that are in ["DISCONNECTED", "CUTOVER", "DISCOVERED"] state
    iterate_list = return_list.copy()
    return_list = []
    for server in iterate_list:
        if server['lifeCycle']['state'] not in ["DISCONNECTED", "CUTOVER", "DISCOVERED"]:
            return_list.append(server)
        else:
            LOGGER.info(f'Unable to update target server {server["sourceServerID"]} due to it being in {server["lifeCycle"]["state"]} state')

    return return_list
# ---------------------------------------
#
# This function takes a list of target servers launch configurations (includes template id) and updates them using the template data passed 
#
# ----------------------------------------
def update_template_ids(target_servers_configuration, template_data, launch_configuration=None, post_launch_configuration=None):

    # Go through each target configuration
    # The data in this list is in this format:
    '''
    [
        {
            'bootMode': 'LEGACY_BIOS'|'UEFI',
            'copyPrivateIp': True|False,
            'copyTags': True|False,
            'ec2LaunchTemplateID': 'string',
            'launchDisposition': 'STOPPED'|'STARTED',
            'licensing': {
                'osByol': True|False
            },
            'name': 'string',
            'sourceServerID': 'string',
            'targetInstanceTypeRightSizingMethod': 'NONE'|'BASIC',
            'enableMapAutoTagging': True|False,
            'mapAutoTaggingMpeID': 'string'
        },
    ]

    '''

    ec2 = boto3.client('ec2')
    mgn = boto3.client('mgn')
    for target_configuration in target_servers_configuration:

        LOGGER.info(f'Updating target server {target_configuration["sourceServerID"]}')
        # Check if launch_configuration specified. Update launch configuration if set to True
        if launch_configuration != None:
            LOGGER.debug(f'Updating launch configuration for target server {target_configuration["sourceServerID"]}')
            mgn.update_launch_configuration(
                sourceServerID=target_configuration['sourceServerID'],
                copyPrivateIp=launch_configuration['copyPrivateIp'],
                copyTags=launch_configuration['copyTags'],
                launchDisposition=launch_configuration['launchDisposition'],
                targetInstanceTypeRightSizingMethod=launch_configuration['targetInstanceTypeRightSizingMethod'],
                enableMapAutoTagging=launch_configuration['enableMapAutoTagging'],
                mapAutoTaggingMpeID=launch_configuration['mapAutoTaggingMpeID']
            )

        if post_launch_configuration != None:
            LOGGER.debug(f'Updating post launch configuration for target server {target_configuration["sourceServerID"]}')
            if 'postLaunchActions' in post_launch_configuration:
                mgn.update_launch_configuration(
                    sourceServerID=target_configuration['sourceServerID'],
                    postLaunchActions=post_launch_configuration['postLaunchActions']
                )
            else:
                mgn.update_launch_configuration(
                    sourceServerID=target_configuration['sourceServerID'],
                    postLaunchActions={}
                )

        versions = ec2.describe_launch_template_versions(
            LaunchTemplateId=target_configuration['ec2LaunchTemplateID'],
        )

        # Find the default version of each server by going through all versions
        for version in versions['LaunchTemplateVersions']:
            if version['DefaultVersion'] == True:
                # print('DEBUG: ##############VERSION')
                # print(version)
                # print('DEBUG: ###########VERSION')

                # Extract the network information from the source version
                # The values we are interested in are:
                # AssociatePublicIpAddress, DeleteOnTermination, Groups(list) and SubnetId
                NetworkInterfaces = get_network_interfaces_info(template_data['LaunchTemplateData']['NetworkInterfaces'])

                # Get existing NetworkInterfaces dictionary from the target template with DeviceIndex of 0
                Existing_NetworkInterface = get_network_interfaces_info(version['LaunchTemplateData'].get('NetworkInterfaces',[{'DeviceIndex': 0}]))

                # The value returned by the above function call looks something like this:
                '''
                 {
                    "AssociatePublicIpAddress": false,
                    "DeleteOnTermination": true,
                    "DeviceIndex": 0,
                    "Groups": [
                        "sg-045df1ac3711111"
                    ],
                    "SubnetId": "subnet-79a5ce11"
                }
                '''

                LOGGER.debug('PARAMETERS = ' + str(PARAMETERS))
                LOGGER.debug(f'NetworkInterfaces = {NetworkInterfaces}')

                # Create the LaunchTemplateData parameter based on what user wants to copy
                LaunchTemplateData_parameter = {
                }

                if 'AssociatePublicIpAddress' in PARAMETERS:
                    LOGGER.debug('Parameters: AssociatePublicIpAddress to be copied')
                    try:
                        Existing_NetworkInterface['AssociatePublicIpAddress'] = NetworkInterfaces['AssociatePublicIpAddress']
                    except:
                        Existing_NetworkInterface['AssociatePublicIpAddress'] = False

                if 'DeleteOnTermination' in PARAMETERS:
                    LOGGER.debug('Parameters: DeleteOnTermination to be copied')
                    try:
                        Existing_NetworkInterface['DeleteOnTermination'] = NetworkInterfaces['DeleteOnTermination']
                    except:
                        Existing_NetworkInterface['DeleteOnTermination'] = True

                if 'SubnetId' in PARAMETERS:
                    LOGGER.debug('Parameters: SubnetId to be copied')
                    try:
                        Existing_NetworkInterface['SubnetId'] = NetworkInterfaces['SubnetId']
                    except:
                        Existing_NetworkInterface.pop('SubnetId', None)

                if 'Groups' in PARAMETERS:
                    LOGGER.debug('Parameters: Groups to be copied')
                    try:
                        Existing_NetworkInterface['Groups'] = NetworkInterfaces['Groups']
                    except:
                        Existing_NetworkInterface.pop('Groups', None)

                LOGGER.debug(f'Creating new launch template version for launch template {target_configuration["ec2LaunchTemplateID"]}')
                
                if 'InstanceType' in PARAMETERS and template_data['LaunchTemplateData'].get('InstanceType') !=None:
                    LOGGER.debug('Parameters: InstanceType to be copied')
                    LaunchTemplateData_parameter['InstanceType'] = template_data['LaunchTemplateData']['InstanceType']
                else:
                    LOGGER.debug('Parameters: EXCLUDING InstanceType')

                if 'Tenancy' in PARAMETERS and template_data['LaunchTemplateData'].get('Placement', {}).get('Tenancy') !=None:
                    LOGGER.debug('Parameters: Tenancy to be copied')
                    LaunchTemplateData_parameter['Placement'] = {}
                    LaunchTemplateData_parameter['Placement']['Tenancy'] = template_data['LaunchTemplateData'].get('Placement', {}).get('Tenancy')
                else:
                    LOGGER.debug('Parameters: EXCLUDING Tenancy')

                if 'IamInstanceProfile' in PARAMETERS and template_data['LaunchTemplateData'].get('IamInstanceProfile') !=None:
                    LOGGER.debug('Parameters: IamInstanceProfile to be copied')
                    LOGGER.debug(template_data['LaunchTemplateData'].get('IamInstanceProfile'))
                    LaunchTemplateData_parameter['IamInstanceProfile'] = {}
                    LaunchTemplateData_parameter['IamInstanceProfile'] = template_data['LaunchTemplateData'].get('IamInstanceProfile')
                    LOGGER.debug(LaunchTemplateData_parameter['IamInstanceProfile'])
                else:
                    LOGGER.debug('Parameters: EXCLUDING IamInstanceProfile')

                LaunchTemplateData_parameter['NetworkInterfaces'] = [Existing_NetworkInterface]
                response = ec2.create_launch_template_version(
                    DryRun=False,
                    LaunchTemplateId = target_configuration['ec2LaunchTemplateID'],
                    SourceVersion = str(version['VersionNumber']),
                    LaunchTemplateData=LaunchTemplateData_parameter
                )

                LOGGER.debug(f'Setting the latest version as the default version for launch template {target_configuration["ec2LaunchTemplateID"]}')
                ec2.modify_launch_template(
                    DryRun=False,
                    LaunchTemplateId=target_configuration["ec2LaunchTemplateID"],
                    DefaultVersion=str(response['LaunchTemplateVersion']['VersionNumber'])
                )

                LOGGER.info(f'Finished updating target server {target_configuration["sourceServerID"]}')
                break

# ---------------------------------------
#
# Reads network interfaces list from the source launch template
# identifies the one with DeviceIndex = 0
# Extract the following info from it and returns a dictionary back 
# AssociatePublicIpAddress, DeleteOnTermination, Groups(list) and SubnetId
#
# ---------------------------------------
def get_network_interfaces_info(network_interfaces):

    return_network_interface = {}
    return_network_interface['DeviceIndex'] = 0

    for ni in network_interfaces:
        if ni['DeviceIndex'] == 0:
            # the Device Indes 0 is found. Extract info from here
            try:
                return_network_interface['AssociatePublicIpAddress'] = ni['AssociatePublicIpAddress']
            except:
                return_network_interface['AssociatePublicIpAddress'] = False

            try:
                return_network_interface['DeleteOnTermination'] = ni['DeleteOnTermination']
            except:
                return_network_interface['DeleteOnTermination'] = True

            try:
                return_network_interface['Groups'] = ni['Groups']
            except:
                pass

            try:
                return_network_interface['SubnetId'] = ni['SubnetId']
            except:
                pass

    
    return return_network_interface

# ---------------------------------------
#
# Entry point
#
# ---------------------------------------
def main():

    # Setup argparse
    parser = argparse.ArgumentParser(description='Script to copy launch template and launch configuration across multiple replicating servers in AWS Application Migration Service (MGN)', usage=usage_message())
    parser.add_argument('--target', help='Specify the servers to update', required=False)
    parser.add_argument('--source-server', help='Specify the server id whose launch template would be used to update the launch template in target server', required=False)
    parser.add_argument('--template-id', help='Specify the launch template id to use', required=False)
    parser.add_argument('--launch-settings-file', help='Specify the launch settings/configuration json file to use', required=False)
    parser.add_argument('--copy-launch-settings', help='Specify whether the launch configruation should be copied or not if source server or json file specified', required=False, action='store_true')
    parser.add_argument('--copy-post-launch-settings', help='Specify whether the launch configruation should be copied or not if source server or json file specified', required=False, action='store_true')
    parser.add_argument('--parameters', help='Specify which parameters to copy from the EC2 Launch Template', required=False)
    parser.add_argument('--debug', help='Set logging to DEBUG', required=False, action='store_true')
    
    args = vars(parser.parse_args())

    # set logging level
    set_logging(args.get('debug'))

    # Check to see if the parameters passed to the script are valid
    arguments_ok = validate_arguments(args)

    if arguments_ok == False:
        LOGGER.error('Incorrect combination of arguments. Usage:')
        usage_message()
        exit(1)

    # Get the template data and target servers configuration
    template_data = get_template_data(SOURCE)

    # Check if --copy-launch-settings set
    if args.get('copy_launch_settings') == True:
        # extract launch configuration from source server
        source_launch_configuration = get_source_launch_configuration(SOURCE)
    else:
        # set source_launch_configuration to None since the user did not specify the argument to copy launch configuration
        source_launch_configuration = None

    if args.get('copy_post_launch_settings') == True:
        # extract post launch configuration from source server
        source_post_launch_configuration = get_source_launch_configuration(SOURCE)
    else:
        # set post_launch_configuration to None since the user did not specify the argument to copy post launch configuration
        source_post_launch_configuration = None
    
    target_servers_configuration = get_target_servers_configuration_list(TARGET)

    # Exit if the return list is of size 0
    if len(target_servers_configuration) == 0:
        print('No target servers found matching the criteria. Exiting.')
        exit(0)
    LOGGER.info(f'Found {len(target_servers_configuration)} target server(s) matching the criteria.')

    LOGGER.debug('\nPrinting launch template data:\n')
    LOGGER.debug(template_data)

    LOGGER.debug('\nPrinting target servers configuration:\n')
    LOGGER.debug(target_servers_configuration)

    LOGGER.debug('Updating template ids and launch configuration (if the required argument is passed)')

    # Call function to update the target launch templates
    update_template_ids(target_servers_configuration, template_data, source_launch_configuration, source_post_launch_configuration)

    LOGGER.info('Finished updating all targets.')

if __name__ == '__main__':
    main()
