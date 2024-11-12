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

import argparse
import json
import logging
import sys

import boto3

# Defining global variables that capture info on parameters passed to script
TARGET = None

# defines what type of target specified
# Is it target server(s) id(s), key=value pair or all
TARGET_TYPE = None

SOURCE = None

# Defines what type of source specified. Is it a source server or launch template
SOURCE_TYPE = None

# Whether or not the replication settings are to be copied
# default is False
COPY_REPLICATION_SETTINGS = False

# Whether or not the launch settings are to be copied
# default is False
COPY_LAUNCH_SETTINGS = False

# Whether or not the launch settings are to be copied
# default is False
COPY_POST_LAUNCH_SETTINGS = False

# Gives us the name of the launch settings/configuration file name if it was passed as an argument
# If no value was passed, it is set to None
LAUNCH_SETTINGS_FILE = None

# This variable gives us the list of properties to copy from the EC2 launch template
PARAMETERS = [
    "SubnetId",
    "AssociatePublicIpAddress",
    "DeleteOnTermination",
    "Groups",
    "Tenancy",
    "IamInstanceProfile",
    "InstanceType",
]

# Logger for logging messages
LOGGER = logging.getLogger()

mgn = boto3.client("mgn")
ec2 = boto3.client("ec2")


def usage_message():
    """
    Generates and logs a usage message for the script.

    This function creates a formatted string containing information about how to use the script,
    including command-line options and examples. It then logs this message using the global LOGGER
    and returns it.

    Returns:
        str: A multi-line string containing the usage message and examples.

    The usage message includes:
    - A brief description of the script's purpose
    - The general command structure
    - Several specific examples demonstrating different use cases

    Examples in the message cover:
    1. Copying a launch template from one server to others
    2. Copying launch settings and template based on server tags
    3. Copying to all replicating servers
    4. Selective parameter copying from a launch template
    5. Combining template copying with launch configuration from a file

    Note:
        This function uses sys.argv[0] to dynamically include the script's filename in the examples.
        It also uses a global LOGGER object to log the message at the INFO level.

    Usage:
        This function is typically called when displaying help information or when
        incorrect arguments are provided to the script.
    """

    msg = f"""
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

    """

    LOGGER.info(msg)

    return msg


def set_logging(debug):
    """
    Configures the logging settings for the script.

    This function sets up the logging system, including the log format, log level,
    and handling of third-party library logs. It clears any existing log handlers
    before setting up new ones.

    Args:
        debug (bool): If True, sets the log level to DEBUG. Otherwise, sets it to INFO.

    Global Variables:
        LOGGER: The global logger object that this function configures.

    The function performs the following actions:
    1. Clears any existing handlers from the LOGGER.
    2. Sets up a StreamHandler to output logs to sys.stderr.
    3. Configures the log format to "LEVEL - MESSAGE".
    4. Sets the log level based on the debug parameter.
    5. Suppresses logs below ERROR level for boto3, botocore, and urllib3.

    Note:
        This function assumes that a global LOGGER object has been defined elsewhere
        in the script.

    Example:
        >>> set_logging(True)  # Enables DEBUG logging
        >>> set_logging(False)  # Sets logging to INFO level
    """

    # Clear any previous loggers
    for handler in LOGGER.handlers:
        LOGGER.removeHandler(handler)

    # Set the format of the log messages
    log_format = "%(levelname)s - %(message)s"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(log_format))
    LOGGER.addHandler(handler)

    # Set the log level
    if debug:
        LOGGER.setLevel(logging.DEBUG)
    else:
        LOGGER.setLevel(logging.INFO)

    # Suppressing messages below ERROR for boto3 and other loggers
    logging.getLogger("boto3").setLevel(logging.ERROR)
    logging.getLogger("botocore").setLevel(logging.ERROR)
    logging.getLogger("urllib3").setLevel(logging.ERROR)


def validate_arguments(args):
    """
    Validates the command-line arguments passed to the script.

    This function checks if the correct combination of arguments has been provided
    and sets global variables based on these arguments.

    Args:
        args (dict): A dictionary containing the parsed command-line arguments.

    Returns:
        bool: True if arguments are valid, False otherwise.

    Global Variables Modified:
        TARGET, TARGET_TYPE, SOURCE, SOURCE_TYPE, COPY_LAUNCH_SETTINGS,
        COPY_POST_LAUNCH_SETTINGS, LAUNCH_SETTINGS_FILE, PARAMETERS

    The function performs the following validations:
    1. Checks if a target and either a template_id or source_server are specified.
    2. Determines the type of target (servers, all, or key/value pair).
    3. Ensures that only one of source_server or template_id is specified.
    4. Validates the use of copy_launch_settings and copy_post_launch_settings options.
    5. Checks the validity of specified parameters if any.

    Raises:
        SystemExit: If any validation fails, the function logs an error message,
                    calls usage_message(), and exits the script with status code 1.

    Note:
        This function relies on a global LOGGER object for error logging and
        a global usage_message() function for displaying usage information.

    Example:
        >>> args = {'target': 'all', 'source_server': 's-12345', 'copy_launch_settings': True}
        >>> is_valid = validate_arguments(args)
        >>> print(is_valid)
        True
    """

    global TARGET
    global TARGET_TYPE
    global SOURCE
    global SOURCE_TYPE
    global COPY_REPLICATION_SETTINGS
    global COPY_LAUNCH_SETTINGS
    global COPY_POST_LAUNCH_SETTINGS
    global LAUNCH_SETTINGS_FILE
    global PARAMETERS

    # This function checks if the right combination of arguments have been passed

    if args.get("target") is not None and (
        args.get("template_id") is not None or args.get("source_server") is not None
    ):
        # Check what type of target has been passed
        if args.get("target").startswith("s-"):
            TARGET = args.get("target")
            TARGET_TYPE = "servers"
        elif args.get("target") == "all":
            TARGET = args.get("target")
            TARGET_TYPE = "all"
        elif "=" in args.get("target"):
            TARGET = args.get("target")
            TARGET_TYPE = "key/value"
        else:
            LOGGER.error("Incorrect value for target specified.")
            LOGGER.error("target: comma-separated serverids, 'all', or key=value pair.")
            usage_message()
            sys.exit(1)

        # Check if both source server and launch template passed
        if (
            args.get("source_server") is not None
            and args.get("template_id") is not None
        ):
            LOGGER.error("Both source launch template and server specified.")
            LOGGER.error(
                "Either a launch template or a source server id should be passed and not both."
            )
            usage_message()
            sys.exit(1)
        else:
            # Check what source has been passed
            if args.get("source_server") is not None:
                SOURCE_TYPE = "server"
                SOURCE = args.get("source_server")
            else:
                SOURCE_TYPE = "launch_template"
                SOURCE = args.get("template_id")

        # Check if --copy-replication-settings used with source server
        # Error if source server is not specified
        if (
            args.get("copy_replication_settings")
            and args.get("source_server") is None
        ):
            LOGGER.error(
                "Option to copy replication settings used without providing a source server."
            )
            usage_message()
            sys.exit(1)

        # Check to see if --copy-lauch-settings specified along with --launch-settings file or source server
        # If not, show an error and exit as either a source server or a launch settings file needs to be specified with this option
        if (
            args.get("copy_launch_settings")
            and args.get("source_server") is None
            and args.get("launch_settings_file") is None
        ):
            LOGGER.error(
                "Copy launch settings option used without source server or settings file."
            )
            usage_message()
            sys.exit(1)

        # Check if --copy-post-launch-settings used with source server
        # Error if no source server specified for this option
        if args.get("copy_post_launch_settings") and args.get("source_server") is None:
            LOGGER.error(
                "Option to copy post launch settings used without providing a source server."
            )
            usage_message()
            sys.exit(1)

        COPY_REPLICATION_SETTINGS = args.get("copy_replication_settings")
        COPY_LAUNCH_SETTINGS = args.get("copy_launch_settings")
        COPY_POST_LAUNCH_SETTINGS = args.get("copy_post_launch_settings")
        LAUNCH_SETTINGS_FILE = args.get("launch_settings_file")

        # Check to see if customer parameters need to be copied or all
        if args.get("parameters") is not None:
            # check to see if valid options passed for parameters argument
            PARAMETERS = args.get("parameters").split(",")

            valid_parameters = {
                "SubnetId",
                "AssociatePublicIpAddress",
                "DeleteOnTermination",
                "Groups",
                "Tenancy",
                "IamInstanceProfile",
                "InstanceType",
            }
            provided_parameters = set(PARAMETERS)

            invalid_parameters = provided_parameters - valid_parameters

            if len(invalid_parameters) > 0:
                LOGGER.error(
                    "Invalid parameter(s) in --parameters: %s",
                    ", ".join(invalid_parameters),
                )
                LOGGER.error(
                    "Valid parameters: SubnetId, AssociatePublicIpAddress, DeleteOnTermination, "
                    "Groups, Tenancy, IamInstanceProfile, InstanceType"
                )
                sys.exit(1)

        return True

    return False


def get_template_data(source_server_or_template_id):
    """
    Retrieves the default EC2 Launch Template data associated with a source server or launch
    template ID.

    This function takes either a source server ID or a launch template ID and returns the
    default version of the associated EC2 Launch Template.

    Args:
        source_server_or_template_id (str): Either a source server ID or a launch template ID.

    Returns:
        dict: A dictionary containing the default version of the EC2 Launch Template data.
              Returns an empty dictionary if no default version is found.

    Global Variables:
        SOURCE_TYPE (str): Expected to be either "server" or "launch_template".
        LOGGER: A logging object for debug messages.

    Raises:
        boto3.exceptions.Boto3Error: May raise Boto3 related exceptions during API calls.

    Note:
        - If SOURCE_TYPE is "server", the function first retrieves the launch configuration
          from MGN and then uses the associated EC2 launch template ID.
        - If SOURCE_TYPE is not "server", it assumes the input is a launch template ID.
        - Only the default version of the launch template is returned.

    Example:
        >>> template_data = get_template_data('s-1234567890abcdef0')
        >>> print(template_data['LaunchTemplateData']['InstanceType'])
        't2.micro'
    """

    # Check if a server id was passed in source_server_or_template_id
    if SOURCE_TYPE == "server":
        LOGGER.debug("Source type is server")
        response = mgn.get_launch_configuration(
            sourceServerID=source_server_or_template_id
        )

        versions = ec2.describe_launch_template_versions(
            LaunchTemplateId=response["ec2LaunchTemplateID"],
        )

    else:
        LOGGER.debug("Source type is template id")
        # Launch template ID was passed to this function
        versions = ec2.describe_launch_template_versions(
            LaunchTemplateId=source_server_or_template_id,
        )

    # Get the default version template data
    version_to_return = {}
    for version in versions["LaunchTemplateVersions"]:
        if version["DefaultVersion"]:
            version_to_return = version.copy()

    return version_to_return


def get_source_launch_configuration(source_server):
    """
    Retrieves the launch configuration for a given source server.

    This function attempts to retrieve the launch configuration either from a specified
    JSON file (if LAUNCH_SETTINGS_FILE is set) or from AWS Migration Hub (if SOURCE_TYPE
    is set to "server"). If neither condition is met, it returns None.

    Args:
        source_server (str): The ID of the source server.

    Returns:
        dict or None: The launch configuration for the specified source server if found,
                      otherwise None.

    Raises:
        json.JSONDecodeError: If there's an error parsing the JSON file.
        boto3.exceptions.Boto3Error: If there's an error communicating with AWS.
        FileNotFoundError: If the specified LAUNCH_SETTINGS_FILE is not found.

    Note:
        This function relies on global variables LAUNCH_SETTINGS_FILE and SOURCE_TYPE.
        It also uses a global LOGGER object for debug logging.
    """

    if LAUNCH_SETTINGS_FILE is not None:
        # Launch settings file was passed as an argument.
        # Read the file and load launch configuration.
        LOGGER.debug("Launch settings json file specified. Reading data.")
        with open(LAUNCH_SETTINGS_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
            return_source_launch_configuration = {
                "copyPrivateIp": data["copyPrivateIp"],
                "copyTags": data["copyTags"],
                "launchDisposition": data["launchDisposition"],
                "targetInstanceTypeRightSizingMethod": data[
                    "targetInstanceTypeRightSizingMethod"
                ],
                "enableMapAutoTagging": data["enableMapAutoTagging"],
                "mapAutoTaggingMpeID": data["mapAutoTaggingMpeID"],
            }
    elif SOURCE_TYPE == "server":
        LOGGER.debug(
            "Source server used for launch settings data. Reading data from source server."
        )
        return_source_launch_configuration = mgn.get_launch_configuration(
            sourceServerID=source_server
        )

    else:
        return_source_launch_configuration = None

    LOGGER.debug("Printing launch settings json:\n")
    LOGGER.debug(return_source_launch_configuration)

    return return_source_launch_configuration


def get_target_servers_configuration_list(target):
    """
    Retrieves launch configurations for servers based on specified criteria.

    This function returns a list of 'launch configurations' for server IDs matching
    the provided target. The target can be 'all', a tag key-value pair, or a list of server IDs.

    Args:
        target (str): Specifies the servers to retrieve configurations for.
            - 'all': Returns configurations for all replicating servers in MGN.
            - 'tag_key=tag_value': Returns configurations for servers with the specified tag.
            - 's-111111,s-2222222,...': Returns configurations for the specified server IDs.

    Returns:
        list: A list of dictionaries containing launch configurations for the matching servers.
        Each dictionary includes details such as boot mode, IP settings, launch template ID,
        licensing information, and more.

    Raises:
        SystemExit: If an incorrect value is provided for the target argument.

    Example:
        >>> get_target_servers_configuration_list('all')
        [{'bootMode': 'LEGACY_BIOS', 'copyPrivateIp': True, ...}, ...]

        >>> get_target_servers_configuration_list('environment=production')
        [{'bootMode': 'UEFI', 'copyPrivateIp': False, ...}, ...]

        >>> get_target_servers_configuration_list('s-111111,s-222222')
        [{'bootMode': 'LEGACY_BIOS', 'copyPrivateIp': True, ...}, ...]
    """

    # Setting this variable to false. This indicates we are not searching by tags
    filter_by_tags = False
    tag_key = False
    tag_value = False

    # Check if the value is all
    if target == "all":
        filters = {
            "isArchived": False,
        }

    # Check if the value is in the format of tag_key=tag_value
    elif "=" in target:
        filters = {
            "isArchived": False,
        }

        # set this variable to True
        # Later, this variable will be used to further filter the results based on tag key/value
        filter_by_tags = True
        tag_key = target.split("=")[0]
        tag_value = target.split("=")[1]

    # Look for the presence of 's-'. This indicates presence of server id(s)
    elif "s-" in target:
        filters = {"isArchived": False, "sourceServerIDs": target.split(",")}

    else:
        # Exit the program since the right value was not passed for this argument
        LOGGER.error("Incorrect value for target specified.")
        LOGGER.error(
            "Target can be a comma separated list of serverids, all or key/value pair "
            "specified using the format key=value."
        )
        sys.exit(1)

    # Calling a function which will extract all replicating servers in MGN
    # based on the filters set above
    target_servers = search_replicating_servers(
        filters, filter_by_tags, tag_key, tag_value
    )

    configuration_list = []

    # For each server, call get_launch_configuration
    for server in target_servers:
        configuration = mgn.get_launch_configuration(
            sourceServerID=server["sourceServerID"]
        )
        configuration_list.append(configuration)

    return configuration_list


def search_replicating_servers(filters, filter_by_tags, tag_key, tag_value):
    """
    Searches for replicating servers in MGN based on specified filters and tags.

    This function is called by get_target_servers_configuration_list. It uses the MGN API
    to describe source servers and returns a list of servers matching the given criteria.

    Args:
        filters (dict): A dictionary of filters for the MGN describe_source_servers API call.
        filter_by_tags (bool): If True, additional filtering by tags will be performed.
        tag_key (str): The key of the tag to filter by (used if filter_by_tags is True).
        tag_value (str): The value of the tag to filter by, or '*' for any value
                         (used if filter_by_tags is True).

    Returns:
        list: A list of dictionaries, each representing a server matching the specified
              criteria. Servers in 'DISCONNECTED', 'CUTOVER', or 'DISCOVERED' states are
              excluded from the results.

    Notes:
        - The function paginates through all results from the MGN API.
        - If filter_by_tags is True, it performs additional filtering based on the provided
          tag key and value.
        - Servers matching the global SOURCE variable (if SOURCE_TYPE is 'server') are
          excluded from the results.
        - Servers in 'DISCONNECTED', 'CUTOVER', or 'DISCOVERED' states are logged and
          excluded from the results.

    Global Variables Used:
        SOURCE_TYPE (str): Expected to be defined globally, determines if filtering by
                           source server is needed.
        SOURCE (str): Expected to be defined globally, the ID of the source server to
                      exclude (if applicable).
        LOGGER: Expected to be a logging object for outputting information messages.
    """

    return_list = []
    response = mgn.describe_source_servers(filters=filters, maxResults=100)

    return_list = response["items"]

    while "nextToken" in response:
        response = mgn.describe_source_servers(
            filters=filters, maxResults=100, nextToken=response["nextToken"]
        )
        return_list.extend(response["items"])

    # Now that all the servers have been extracted, check if they need to be further
    # filtered by tag key/value
    if filter_by_tags:
        # New list created which would have filtered results
        new_list = []

        # Evaluate each server in the list return_list and check its tags.
        # A user may pass just the tag key and * for the value. In which case the tag
        # value is not evaluated.
        for server in return_list:
            if "tags" in server:
                for tag in server["tags"]:
                    if tag == tag_key and (
                        server["tags"][tag] == tag_value or tag_value == "*"
                    ):
                        # Found a server matching the tag key/value
                        # Add it to the new list
                        new_list.append(server)
                        break

        return_list = new_list

    # Remove source server from the target servers list
    # The source server may show up in target list when tag key/value pair is specified
    # or all is specified
    # This is needed only when a source server is specified in command line arguments
    # and not launch template
    if SOURCE_TYPE == "server":
        iterate_list = return_list.copy()
        return_list = []
        for server in iterate_list:
            if server["sourceServerID"] != SOURCE:
                return_list.append(server)

    # Remove servers that are in ["DISCONNECTED", "CUTOVER", "DISCOVERED"] state
    iterate_list = return_list.copy()
    return_list = []
    for server in iterate_list:
        if server["lifeCycle"]["state"] not in [
            "DISCONNECTED",
            "CUTOVER",
            "DISCOVERED",
        ]:
            return_list.append(server)
        else:
            LOGGER.info(
                "Unable to update target server %s due to it being in %s state",
                server["sourceServerID"],
                server["lifeCycle"]["state"],
            )

    return return_list

def get_replication_settings(source_server):
    """
    Retrieves the replication configuration settings for a specified source server.

    This function uses the AWS Application Migration Service (MGN) to fetch
    the replication configuration for a given source server.

    Args:
        source_server (str): The ID of the source server for which to retrieve
                             the replication configuration.

    Returns:
        dict: A dictionary containing the replication configuration settings
              for the specified source server. The structure of this dictionary
              depends on the AWS MGN API response.

    Raises:
        Exception: Any exception raised by the AWS MGN API call will be
                   propagated to the caller.

    Note:
        This function assumes that the AWS SDK for Python (Boto3) is properly
        configured with the necessary credentials and permissions to make
        API calls to AWS MGN.
    """
    replication_settings = mgn.get_replication_configuration(
        sourceServerID=source_server, 
    )
    return replication_settings


def update_replication_settings(target_servers, replication_settings):
    """
    Updates the replication configuration for multiple target servers.

    This function iterates through a list of target servers and updates their
    replication settings using the AWS Application Migration Service (MGN).

    Args:
        target_servers (list): A list of dictionaries, where each dictionary
                               represents a target server and contains at least
                               a 'sourceServerID' key.
        replication_settings (dict): A dictionary containing the replication
                                     configuration settings to be applied. It
                                     should include the following keys:
                                     - bandwidthThrottling
                                     - dataPlaneRouting
                                     - createPublicIP
                                     - useDedicatedReplicationServer
                                     - replicationServerInstanceType
                                     - stagingAreaSubnetId
                                     - defaultLargeStagingDiskType
                                     - replicationServersSecurityGroupsIDs

    Returns:
        None

    Raises:
        KeyError: If any required key is missing in the target_servers or
                  replication_settings dictionaries.
        Exception: Any exception raised by the AWS MGN API call will be
                   propagated to the caller.

    Note:
        This function assumes that the AWS SDK for Python (Boto3) is properly
        configured with the necessary credentials and permissions to make
        API calls to AWS MGN.
    """
    for target_server in target_servers:
        mgn.update_replication_configuration(
            sourceServerID=target_server["sourceServerID"],
            bandwidthThrottling=replication_settings["bandwidthThrottling"],
            dataPlaneRouting=replication_settings["dataPlaneRouting"],
            createPublicIP=replication_settings["createPublicIP"],
            useDedicatedReplicationServer=replication_settings["useDedicatedReplicationServer"],
            replicationServerInstanceType=replication_settings["replicationServerInstanceType"],
            stagingAreaSubnetId=replication_settings["stagingAreaSubnetId"],
            defaultLargeStagingDiskType=replication_settings["defaultLargeStagingDiskType"],
            replicationServersSecurityGroupsIDs=replication_settings["replicationServersSecurityGroupsIDs"]
        )


def update_template_ids(
    target_servers_configuration,
    template_data,
    launch_configuration=None,
    post_launch_configuration=None,
):
    """
    Updates launch templates and configurations for target servers.

    This function iterates through a list of target server configurations and updates
    their launch templates and configurations based on the provided template data
    and optional launch and post-launch configurations.

    Args:
        target_servers_configuration (list): A list of dictionaries, each containing
            the configuration for a target server.
        template_data (dict): The source template data to be used for updating.
        launch_configuration (dict, optional): Launch configuration to be applied.
        post_launch_configuration (dict, optional): Post-launch configuration to be applied.

    Global Variables Used:
        LOGGER: For logging information and debug messages.
        PARAMETERS: A list of parameters to be copied from the source template.

    The function performs the following steps for each target server:
    1. Updates the launch configuration if provided.
    2. Updates the post-launch configuration if provided.
    3. Retrieves the current launch template versions.
    4. For the default version:
       a. Extracts and updates network interface information.
       b. Copies specified parameters from the source template.
       c. Creates a new launch template version with the updated data.
       d. Sets the new version as the default.

    Note:
        This function makes API calls to AWS services (EC2 and MGN) and assumes
        the necessary permissions are in place.

    Raises:
        boto3.exceptions.Boto3Error: For any AWS API related errors.

    Example:
        >>> target_configs = [{'sourceServerID': 's-123', 'ec2LaunchTemplateID': 'lt-456'}]
        >>> template_data = {'LaunchTemplateData': {...}}
        >>> update_template_ids(target_configs, template_data)
    """

    for target_configuration in target_servers_configuration:
        LOGGER.info("Updating target server %s", target_configuration["sourceServerID"])

        # Check if launch_configuration specified. Update launch configuration if set to True
        if launch_configuration is not None:
            LOGGER.debug(
                "Updating launch configuration for target server %s",
                target_configuration["sourceServerID"],
            )
            mgn.update_launch_configuration(
                sourceServerID=target_configuration["sourceServerID"],
                copyPrivateIp=launch_configuration["copyPrivateIp"],
                copyTags=launch_configuration["copyTags"],
                launchDisposition=launch_configuration["launchDisposition"],
                targetInstanceTypeRightSizingMethod=launch_configuration[
                    "targetInstanceTypeRightSizingMethod"
                ],
                enableMapAutoTagging=launch_configuration["enableMapAutoTagging"],
                mapAutoTaggingMpeID=launch_configuration["mapAutoTaggingMpeID"],
            )

        if post_launch_configuration is not None:
            LOGGER.debug(
                "Updating post launch configuration for target server %s",
                target_configuration["sourceServerID"],
            )
            if "postLaunchActions" in post_launch_configuration:
                mgn.update_launch_configuration(
                    sourceServerID=target_configuration["sourceServerID"],
                    postLaunchActions=post_launch_configuration["postLaunchActions"],
                )
            else:
                mgn.update_launch_configuration(
                    sourceServerID=target_configuration["sourceServerID"],
                    postLaunchActions={},
                )

        versions = ec2.describe_launch_template_versions(
            LaunchTemplateId=target_configuration["ec2LaunchTemplateID"],
        )

        # Find the default version of each server by going through all versions
        for version in versions["LaunchTemplateVersions"]:
            if version["DefaultVersion"]:
                # Extract the network information from the source version
                # The values we are interested in are:
                # AssociatePublicIpAddress, DeleteOnTermination, Groups(list) and SubnetId
                network_interfaces = get_network_interfaces_info(
                    template_data["LaunchTemplateData"]["NetworkInterfaces"]
                )

                # Get existing NetworkInterfaces dictionary from the target template
                # with DeviceIndex of 0
                existing_network_interface = get_network_interfaces_info(
                    version["LaunchTemplateData"].get(
                        "NetworkInterfaces", [{"DeviceIndex": 0}]
                    )
                )

                LOGGER.debug("PARAMETERS = " + str(PARAMETERS))
                LOGGER.debug(f"NetworkInterfaces = {network_interfaces}")

                # Create the LaunchTemplateData parameter based on what user wants to copy
                launch_template_data_parameter = {}

                if "AssociatePublicIpAddress" in PARAMETERS:
                    LOGGER.debug("Parameters: AssociatePublicIpAddress to be copied")
                    try:
                        existing_network_interface["AssociatePublicIpAddress"] = (
                            network_interfaces["AssociatePublicIpAddress"]
                        )
                    except:
                        existing_network_interface["AssociatePublicIpAddress"] = False

                if "DeleteOnTermination" in PARAMETERS:
                    LOGGER.debug("Parameters: DeleteOnTermination to be copied")
                    try:
                        existing_network_interface["DeleteOnTermination"] = (
                            network_interfaces["DeleteOnTermination"]
                        )
                    except:
                        existing_network_interface["DeleteOnTermination"] = True

                if "SubnetId" in PARAMETERS:
                    LOGGER.debug("Parameters: SubnetId to be copied")
                    try:
                        existing_network_interface["SubnetId"] = network_interfaces[
                            "SubnetId"
                        ]
                    except:
                        existing_network_interface.pop("SubnetId", None)

                if "Groups" in PARAMETERS:
                    LOGGER.debug("Parameters: Groups to be copied")
                    try:
                        existing_network_interface["Groups"] = network_interfaces[
                            "Groups"
                        ]
                    except:
                        existing_network_interface.pop("Groups", None)

                LOGGER.debug(
                    "Creating new launch template version for launch template %s",
                    target_configuration["ec2LaunchTemplateID"],
                )

                if (
                    "InstanceType" in PARAMETERS
                    and template_data["LaunchTemplateData"].get("InstanceType")
                    is not None
                ):
                    LOGGER.debug("Parameters: InstanceType to be copied")
                    launch_template_data_parameter["InstanceType"] = template_data[
                        "LaunchTemplateData"
                    ]["InstanceType"]
                else:
                    LOGGER.debug("Parameters: EXCLUDING InstanceType")

                if (
                    "Tenancy" in PARAMETERS
                    and template_data["LaunchTemplateData"]
                    .get("Placement", {})
                    .get("Tenancy")
                    is not None
                ):
                    LOGGER.debug("Parameters: Tenancy to be copied")
                    launch_template_data_parameter["Placement"] = {}
                    launch_template_data_parameter["Placement"]["Tenancy"] = (
                        template_data["LaunchTemplateData"]
                        .get("Placement", {})
                        .get("Tenancy")
                    )
                else:
                    LOGGER.debug("Parameters: EXCLUDING Tenancy")

                if (
                    "IamInstanceProfile" in PARAMETERS
                    and template_data["LaunchTemplateData"].get("IamInstanceProfile")
                    is not None
                ):
                    LOGGER.debug("Parameters: IamInstanceProfile to be copied")
                    LOGGER.debug(
                        template_data["LaunchTemplateData"].get("IamInstanceProfile")
                    )
                    launch_template_data_parameter["IamInstanceProfile"] = (
                        template_data["LaunchTemplateData"].get(
                            "IamInstanceProfile", {}
                        )
                    )
                    LOGGER.debug(launch_template_data_parameter["IamInstanceProfile"])
                else:
                    LOGGER.debug("Parameters: EXCLUDING IamInstanceProfile")

                launch_template_data_parameter["NetworkInterfaces"] = [
                    existing_network_interface
                ]
                response = ec2.create_launch_template_version(
                    DryRun=False,
                    LaunchTemplateId=target_configuration["ec2LaunchTemplateID"],
                    SourceVersion=str(version["VersionNumber"]),
                    LaunchTemplateData=launch_template_data_parameter,
                )

                LOGGER.debug(
                    "Setting the latest version as the default version for launch template %s",
                    target_configuration["ec2LaunchTemplateID"],
                )
                ec2.modify_launch_template(
                    DryRun=False,
                    LaunchTemplateId=target_configuration["ec2LaunchTemplateID"],
                    DefaultVersion=str(
                        response["LaunchTemplateVersion"]["VersionNumber"]
                    ),
                )

                LOGGER.info(
                    "Finished updating target server %s",
                    target_configuration["sourceServerID"],
                )
                break


def get_network_interfaces_info(network_interfaces):
    """
        Extracts network interface information from a launch template.

        This function reads the network interfaces list from a source launch template,
        identifies the interface with DeviceIndex = 0, and extracts specific information
        from it.

        Args:
            network_interfaces (list): A list of dictionaries, each representing a network
                                       interface configuration from a launch template.

        Returns:
            dict: A dictionary containing the following keys:
                  - DeviceIndex: Always set to 0.
                  - AssociatePublicIpAddress: Boolean indicating if a public IP should be
                    associated.
                  - DeleteOnTermination: Boolean indicating if the interface should be deleted
                    on instance termination.
                  - Groups: A list of security group IDs (if available).
                  - SubnetId: The ID of the subnet (if available).

        Notes:
            - The function focuses on the network interface with DeviceIndex = 0.
            - If certain attributes are not found in the source data, default values or
              omissions are applied:
              - AssociatePublicIpAddress defaults to False if not found.
              - DeleteOnTermination defaults to True if not found.
              - Groups and SubnetId are omitted if not found.

    Example:
            >>> interfaces = [{'DeviceIndex': 0, 'AssociatePublicIpAddress': True,
            ...                'DeleteOnTermination': False, 'Groups': ['sg-1234'],
            ...                'SubnetId': 'subnet-5678'}]
            >>> get_network_interfaces_info(interfaces)
            {'DeviceIndex': 0, 'AssociatePublicIpAddress': True, 'DeleteOnTermination': False,
             'Groups': ['sg-1234'], 'SubnetId': 'subnet-5678'}
    """

    return_network_interface = {}
    return_network_interface["DeviceIndex"] = 0

    for network_interface in network_interfaces:
        if network_interface["DeviceIndex"] == 0:
            # the Device Indes 0 is found. Extract info from here
            try:
                return_network_interface["AssociatePublicIpAddress"] = (
                    network_interface["AssociatePublicIpAddress"]
                )
            except:
                return_network_interface["AssociatePublicIpAddress"] = False

            try:
                return_network_interface["DeleteOnTermination"] = network_interface[
                    "DeleteOnTermination"
                ]
            except:
                return_network_interface["DeleteOnTermination"] = True

            groups = network_interface.get("Groups")
            if groups is not None:
                return_network_interface["Groups"] = groups

            subnet_id = network_interface.get("SubnetId")
            if subnet_id is not None:
                return_network_interface["SubnetId"] = subnet_id

    return return_network_interface


def main():
    """
    Main entry point for the script to copy launch templates and configurations across MGN servers.

    This function orchestrates the entire process of updating launch templates and configurations
    for specified target servers in AWS Application Migration Service (MGN). It performs
    the following steps:

    1. Parses command-line arguments using argparse.
    2. Sets up logging based on the debug flag.
    3. Validates the provided arguments.
    4. Retrieves the source template data and target server configurations.
    5. Extracts launch and post-launch configurations if specified.
    6. Updates the target servers' launch templates and configurations.

    Command-line Arguments:
        --target: Specifies the servers to update.
        --source-server: The server ID whose launch template will be used for updates.
        --template-id: The launch template ID to use.
        --launch-settings-file: JSON file containing launch settings/configuration.
        --copy-launch-settings: Flag to copy launch configuration.
        --copy-post-launch-settings: Flag to copy post-launch configuration.
        --parameters: Specifies which parameters to copy from the EC2 Launch Template.
        --debug: Sets logging to DEBUG level.

    The function uses several helper functions to process the data and make the necessary updates.
    It handles errors and provides appropriate logging throughout the process.

    Exit codes:
        0: Successful execution
        1: Error in argument validation or no target servers found

    Note:
        This function relies on global variables and imported modules for AWS interactions
        and logging.
    """

    # Setup argparse
    parser = argparse.ArgumentParser(
        description="Script to copy launch template and launch configuration across "
        "multiple replicating servers in AWS Application Migration Service (MGN)",
        usage=usage_message(),
    )
    parser.add_argument(
        "--target", help="Specify the servers to update", required=False
    )
    parser.add_argument(
        "--source-server",
        help="Specify the server id whose launch template would be used to update the "
        "launch template in target server",
        required=False,
    )
    parser.add_argument(
        "--template-id", help="Specify the launch template id to use", required=False
    )
    parser.add_argument(
        "--launch-settings-file",
        help="Specify the launch settings/configuration json file to use",
        required=False,
    )
    parser.add_argument(
        "--copy-replication-settings",
        help="Specify whether the replication settings should be copied or not if source server specified",
        required=False,
        action="store_true",
    )
    parser.add_argument(
        "--copy-launch-settings",
        help="Specify whether the launch configuration should be copied or not if "
        "source server or json file specified",
        required=False,
        action="store_true",
    )
    parser.add_argument(
        "--copy-post-launch-settings",
        help="Specify whether the post-launch configuration should be copied or not if "
        "source server or json file specified",
        required=False,
        action="store_true",
    )
    parser.add_argument(
        "--parameters",
        help="Specify which parameters to copy from the EC2 Launch Template",
        required=False,
    )
    parser.add_argument(
        "--debug", help="Set logging to DEBUG", required=False, action="store_true"
    )

    args = vars(parser.parse_args())

    # set logging level
    set_logging(args.get("debug"))

    # Check to see if the parameters passed to the script are valid
    arguments_ok = validate_arguments(args)

    if not arguments_ok:
        LOGGER.error("Incorrect combination of arguments. Usage:")
        usage_message()
        sys.exit(1)

    # Get the template data and target servers configuration
    template_data = get_template_data(SOURCE)

    if args.get("copy_replication_settings"):
        replication_settings = get_replication_settings(SOURCE)

    # Check if --copy-launch-settings set
    if args.get("copy_launch_settings"):
        # extract launch configuration from source server
        source_launch_configuration = get_source_launch_configuration(SOURCE)
    else:
        # set source_launch_configuration to None since the user did not specify
        # the argument to copy launch configuration
        source_launch_configuration = None

    if args.get("copy_post_launch_settings"):
        # extract post launch configuration from source server
        source_post_launch_configuration = get_source_launch_configuration(SOURCE)
    else:
        # set post_launch_configuration to None since the user did not specify
        # the argument to copy post launch configuration
        source_post_launch_configuration = None

    target_servers_configuration = get_target_servers_configuration_list(TARGET)

    # Exit if the return list is of size 0
    if len(target_servers_configuration) == 0:
        print("No target servers found matching the criteria. Exiting.")
        sys.exit(0)

    LOGGER.info(
        "Found %d target server(s) matching the criteria.",
        len(target_servers_configuration),
    )

    LOGGER.debug("\nPrinting launch template data:\n")
    LOGGER.debug(template_data)

    LOGGER.debug("\nPrinting target servers configuration:\n")
    LOGGER.debug(target_servers_configuration)

    LOGGER.debug(
        "Updating template ids and launch configuration (if the required argument is passed)"
    )

    # Call function to update the target launch templates
    update_template_ids(
        target_servers_configuration,
        template_data,
        source_launch_configuration,
        source_post_launch_configuration,
    )

    if args.get("copy_replication_settings"):
        LOGGER.debug("Updating replication settings")
        update_replication_settings(target_servers_configuration, replication_settings)

    LOGGER.info("Finished updating all targets.")


if __name__ == "__main__":
    main()
