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
import csv
import logging

import boto3

logging.basicConfig(
    filename="mgn_launch_automate.log",
    format="%(asctime)s%(levelname)s:%(message)s",
    level=logging.DEBUG,
)
log = logging.getLogger(__name__)

mgn_client = boto3.client("mgn")
ec2_client = boto3.client("ec2")


def list_all(client, method, type, **kwargs):
    """
    Retrieve all items from a paginated AWS API call.

    Args:
        client (botocore.client.BaseClient): The AWS client object to use for the API call.
        method (str): The name of the method to call on the client object.
        type (str): The key in the response dictionary that contains the items to retrieve.
        **kwargs: Additional keyword arguments to pass to the API call.

    Returns:
        list: A list containing all items retrieved from the API call.
    """
    results = []
    paginator = client.get_paginator(method)
    page_iterator = paginator.paginate(**kwargs)
    for page in page_iterator:
        results += page[type]
    return results


def get_launch_config(source_server_id, hostname):
    """
    Retrieve the general launch settings from MGN and EC2 launch settings for a
    specific source server.

    This function fetches the launch configuration from AWS Application Migration Service (MGN) and
    the corresponding EC2 launch template for a given source server. It logs detailed information
    about both the MGN and EC2 launch settings.

    Args:
        source_server_id (str): The unique identifier of the source server in MGN.
        hostname (str): The hostname of the source server, used for logging purposes.

    Returns:
        tuple: A tuple containing two elements:
            - general_launch_settings (dict): The MGN launch configuration settings
              for the source server.
            - general_launch_settings (dict): The MGN launch configuration settings
              for the source server.

    Notes:
        - The function assumes the existence of global 'mgn_client', 'ec2_client',
          and 'log' objects.
        - The 'ResponseMetadata' key is removed from the MGN launch configuration.
        - Extensive logging is performed, including the old launch configuration
          and EC2 launch settings.
        - Only the default version of the EC2 launch template is returned and logged.

    Raises:
        Any exceptions raised by the AWS SDK calls are not caught in this function
        and will propagate.

    Example:
        mgn_settings, ec2_template = get_launch_config('s-1234567890abcdef0',
                                                       'myserver.example.com')
    """
    general_launch_settings = mgn_client.get_launch_configuration(
        sourceServerID=source_server_id
    )

    del general_launch_settings["ResponseMetadata"]
    log.info("=" * 35 + " Old Launch configuration " + "=" * 35)

    log.info(
        "Old Launch Configuration for host %s with SourceServerID %s",
        hostname,
        source_server_id,
    )
    log.info("=" * 80)
    log.info("=" * 80)
    log.info("Old - General Launch Settings:")
    log.info(general_launch_settings)

    launch_template = ec2_client.describe_launch_template_versions(
        LaunchTemplateId=general_launch_settings["ec2LaunchTemplateID"]
    )
    launch_template_versions = launch_template["LaunchTemplateVersions"]
    for launch_template_version in launch_template_versions:
        if launch_template_version["DefaultVersion"]:
            log.info("=" * 80)
            log.info("=" * 80)
            log.info("Old - EC2 Launch Settings:")
            log.info(launch_template_version)
            break

    return general_launch_settings, launch_template_version


def query_lifecycle_state(source_server_id):
    """
    Query the lifecycle state of a specified source server using AWS Application
    Migration Service (MGN).

    This function retrieves the current lifecycle state of a source server identified by its ID.
    It uses the MGN client to describe the source server and extract the lifecycle
    state information.

    Parameters:
    -----------
    source_server_id : str
        The unique identifier of the source server whose lifecycle state is to be queried.

    Returns:
    --------
    str
        The current lifecycle state of the specified source server.

    Raises:
    -------
    IndexError
        If the response from MGN does not contain the expected data structure.
    KeyError
        If the required keys are not present in the response dictionary.

    Note:
    -----
    This function assumes that the MGN client (mgn_client) has been properly initialized
    and has the necessary permissions to describe source servers.

    Example:
    --------
    >>> state = query_lifecycle_state("s-1234567890abcdef0")
    >>> print(state)
    'READY_FOR_TEST'
    """
    res = mgn_client.describe_source_servers(
        filters={"sourceServerIDs": [source_server_id]}
    )
    del res["ResponseMetadata"]
    lifecycle_state = res["items"][0]["lifeCycle"]["state"]

    return lifecycle_state


def get_all_source_servers():
    """
    Retrieve all non-archived source servers from the AWS Application Migration
    Service (MGN) console.

    This function uses the MGN client to describe all source servers that are not archived.
    It filters out archived servers and returns only the active ones.

    Returns:
    --------
    list
        A list of dictionaries, where each dictionary contains information about a source server.
        The structure of each dictionary depends on the MGN API response format.

    Raises:
    -------
    botocore.exceptions.ClientError
        If there's an error in making the API call to MGN.

    Note:
    -----
    This function assumes that the MGN client (mgn_client) has been properly initialized
    and has the necessary permissions to describe source servers.

    Example:
    --------
    >>> servers = get_all_source_servers()
    >>> print(len(servers))
    5
    >>> print(servers[0]['sourceServerID'])
    's-1234567890abcdef0'
    """
    source_servers = list_all(mgn_client, "describe_source_servers", "items", filters={"isArchived": False})

    return source_servers


def get_source_server_id(hostname, source_servers):
    """
    Retrieve the source server ID for a given hostname from a list of source servers.

    This function iterates through a list of source servers and attempts to find a match
    for the provided hostname. It checks the 'identificationHints' property of each source
    server for a matching hostname.

    Args:
        hostname (str): The hostname to search for.
        source_servers (list): A list of dictionaries, each representing a source server.
            Each dictionary is expected to have a structure that includes:
            {
                'sourceServerID': str,
                'sourceProperties': {
                    'identificationHints': {
                        'hostname': str
                    }
                }
            }

    Returns:
        str or None: The source server ID if a match is found, or None if no match is found.

    Notes:
        - The function logs the source server ID when a match is found.
        - The function assumes the existence of a global 'log' object for logging.
        - If multiple servers have the same hostname, only the first match is returned.

    Example:
        source_servers = [
            {
                'sourceServerID': 's-1234',
                'sourceProperties': {
                    'identificationHints': {'hostname': 'server1'}
                }
            },
            {
                'sourceServerID': 's-5678',
                'sourceProperties': {
                    'identificationHints': {'hostname': 'server2'}
                }
            }
        ]
        server_id = get_source_server_id('server2', source_servers)
        # server_id will be 's-5678'
    """
    for source_server in source_servers:
        if (
            "hostname" in source_server["sourceProperties"]["identificationHints"]
            and source_server["sourceProperties"]["identificationHints"]["hostname"]
            == hostname
        ):
            log.info(source_server["sourceServerID"])
            return source_server["sourceServerID"]

    return None


def update_launch_config(
    general_launch_settings, launch_template_version, source_server_id, row
):
    """
    Update the EC2 launch template and general launch settings for a specific source server.

    This function modifies various launch configuration settings based on the provided row data,
    including instance type, network interfaces, storage configurations, and resource tags.

    Args:
        general_launch_settings (dict): The current general launch settings for the source server.
        launch_template_version (dict): The current EC2 launch template version for the
            source server.
        source_server_id (str): The unique identifier of the source server.
        row (dict): A dictionary containing the new configuration values, typically from a CSV row.

    Notes:
        - This function performs extensive modifications to the launch template and
          general settings.
        - It handles various aspects such as instance sizing, network interfaces,
          storage configurations, and tagging.
        - The function assumes the existence of global 'log' object for logging.
        - After updating configurations, it calls external functions to apply changes
          to EC2 and MGN.
        - Extensive logging is performed to record both old and new configurations.

    Important fields in 'row':
        - Instance_type_right_sizing: Method for right-sizing the instance type.
        - EC2_Instance_type: The target EC2 instance type.
        - Copy_private_ip: Whether to copy the private IP.
        - Start_Instance_upon_launch: Launch disposition of the instance.
        - Transfer_Server_tags: Whether to transfer server tags.
        - OS: Operating system of the server (used for Windows-specific configurations).
        - OS_licensing_byol: BYOL licensing option for Windows.
        - Boot_mode: Boot mode for Windows instances.
        - placement_group_name: Name of the placement group.
        - Tenancy: EC2 tenancy option.
        - ENI, Subnet_ID, Security_Groups, Primary_private_ip: Network interface configurations.
        - volume_type, volume_throughput, volume_iops: EBS volume configurations.
        - Resource_tags: Additional resource tags to be added.

    Raises:
        Any exceptions raised during the process are not caught in this function and will propagate.

    Example:
        update_launch_config(general_settings, launch_template, 's-1234567890abcdef0', csv_row)
    """
    new_ec2_launch_template = launch_template_version
    new_general_launch_settings = general_launch_settings
    if (
        row["Instance_type_right_sizing"] != ""
        and general_launch_settings["targetInstanceTypeRightSizingMethod"]
        != row["Instance_type_right_sizing"]
    ):
        new_general_launch_settings["targetInstanceTypeRightSizingMethod"] = row[
            "Instance_type_right_sizing"
        ]
    if (
        new_general_launch_settings["targetInstanceTypeRightSizingMethod"] != "BASIC"
        and row["EC2_Instance_type"] != ""
    ):
        new_ec2_launch_template["LaunchTemplateData"]["InstanceType"] = row[
            "EC2_Instance_type"
        ]
    if row["Copy_private_ip"] != "" and row["Copy_private_ip"].capitalize() != str(
        general_launch_settings["copyPrivateIp"]
    ):
        new_general_launch_settings["copyPrivateIp"] = (
            True if row["Copy_private_ip"].capitalize() == "True" else False
        )
    if row["Enable_Map_Auto_Tagging"] != "" and row[
        "Enable_Map_Auto_Tagging"
    ].capitalize() != str(general_launch_settings["enableMapAutoTagging"]):
        new_general_launch_settings["enableMapAutoTagging"] = (
            True if row["Enable_Map_Auto_Tagging"].capitalize() == "True" else False
        )
    if row["Map_Auto_Tagging_Mpe_ID"] != "" and row["Map_Auto_Tagging_Mpe_ID"] != str(
        general_launch_settings["mapAutoTaggingMpeID"]
    ):
        new_general_launch_settings["mapAutoTaggingMpeID"] = row[
            "Map_Auto_Tagging_Mpe_ID"
        ]
    if (
        row["Start_Instance_upon_launch"] != ""
        and general_launch_settings["launchDisposition"]
        != row["Start_Instance_upon_launch"]
    ):
        new_general_launch_settings["launchDisposition"] = row[
            "Start_Instance_upon_launch"
        ]
    if (
        row["Transfer_Server_tags"] != ""
        and str(general_launch_settings["copyTags"])
        != row["Transfer_Server_tags"].capitalize()
    ):
        new_general_launch_settings["copyTags"] = (
            True if row["Transfer_Server_tags"].capitalize() == "True" else False
        )
    if "windows" in row["OS"].lower() and row["OS_licensing_byol"] != "":
        new_general_launch_settings["licensing"]["osByol"] = (
            True if row["OS_licensing_byol"].capitalize() == "True" else False
        )
    if "windows" in row["OS"].lower() and row["Boot_mode"] != "":
        new_general_launch_settings["bootMode"] = row["Boot_mode"]
    if row["placement_group_name"] != "":
        if "Placement" not in new_ec2_launch_template["LaunchTemplateData"]:
            new_ec2_launch_template["LaunchTemplateData"]["Placement"] = {}
        new_ec2_launch_template["LaunchTemplateData"]["Placement"]["GroupName"] = row[
            "placement_group_name"
        ]
    if (
        "windows" in row["OS"].lower() and row["Tenancy"] != ""
    ):  # MGN specific 'windows' check as dedicated and host tenancy only supported by windows
        if "Placement" not in new_ec2_launch_template["LaunchTemplateData"]:
            new_ec2_launch_template["LaunchTemplateData"]["Placement"] = {}
        new_ec2_launch_template["LaunchTemplateData"]["Placement"]["Tenancy"] = row[
            "Tenancy"
        ]
        if (
            new_ec2_launch_template["LaunchTemplateData"]["Placement"]["Tenancy"]
            == "default"
            or new_ec2_launch_template["LaunchTemplateData"]["Placement"]["Tenancy"]
            == "dedicated"
        ):
            new_ec2_launch_template["LaunchTemplateData"]["Placement"].pop(
                "HostId", None
            )
            new_ec2_launch_template["LaunchTemplateData"]["Placement"].pop(
                "HostResourceGroupArn", None
            )
        elif row["HostresourceGroupArn"] != "":
            new_ec2_launch_template["LaunchTemplateData"]["Placement"][
                "HostResourceGroupArn"
            ] = row["HostresourceGroupArn"]
            new_ec2_launch_template["LaunchTemplateData"]["Placement"].pop(
                "HostId", None
            )
        elif row["HostId"] != "":
            new_ec2_launch_template["LaunchTemplateData"]["Placement"]["HostId"] = row[
                "HostId"
            ]
            new_ec2_launch_template["LaunchTemplateData"]["Placement"].pop(
                "HostResourceGroupArn", None
            )

    network_interfaces = new_ec2_launch_template["LaunchTemplateData"][
        "NetworkInterfaces"
    ]
    device_indexes_from_lt = [i["DeviceIndex"] for i in network_interfaces]

    # Remove all white space characters from csv and split using a comma
    all_id_enis = "".join(row["ENI"].split()).split(",")
    all_id_subs = "".join(row["Subnet_ID"].split()).split(",")
    all_id_sgs = "".join(row["Security_Groups"].split()).split(",")
    all_id_pis = "".join(row["Primary_private_ip"].split()).split(",")

    if row["Subnet_ID"] != "":
        for idsub in all_id_subs:
            # If no ENI-Id is present for a network device index,
            # then subnet-id for network device index can be present
            idx = idsub.split(":")[0]
            sub = idsub.split(":")[1]
            if int(idx) not in device_indexes_from_lt:
                network_interfaces.append({"DeviceIndex": int(idx)})
                device_indexes_from_lt = [i["DeviceIndex"] for i in network_interfaces]
            for network_interface in network_interfaces:
                if network_interface["DeviceIndex"] == int(idx):
                    if not sub:
                        network_interface.pop("SubnetId", None)
                        continue
                    network_interface["SubnetId"] = sub
                    network_interface.pop("NetworkInterfaceId", None)

    if row["Security_Groups"] != "":
        # If no ENI-Id is present for a network device index,
        # then security group for network device index can be present
        for idsg in all_id_sgs:
            idx = idsg.split(":")[0]
            security_group = idsg.split(":")[1].split(";")
            if int(idx) not in device_indexes_from_lt:
                network_interfaces.append({"DeviceIndex": int(idx)})
                device_indexes_from_lt = [i["DeviceIndex"] for i in network_interfaces]
            for network_interface in network_interfaces:
                if network_interface["DeviceIndex"] == int(idx):
                    if not security_group:
                        network_interface.pop("Groups", None)
                        continue
                    network_interface["Groups"] = security_group
                    network_interface.pop("NetworkInterfaceId", None)

    if row["Primary_private_ip"] != "":
        # If no ENI-Id is present for a network device index,
        # then primary private ip for network device index can be present
        for idpi in all_id_pis:
            idx = idpi.split(":")[0]
            private_ip = idpi.split(":")[1]
            if int(idx) not in device_indexes_from_lt:
                network_interfaces.append({"DeviceIndex": int(idx)})
                device_indexes_from_lt = [i["DeviceIndex"] for i in network_interfaces]
            if int(idx) == 0 and row["Copy_private_ip"].capitalize() == "True":
                continue
            for network_interface in network_interfaces:
                if network_interface["DeviceIndex"] == int(idx):
                    if not private_ip:
                        network_interface.pop("PrivateIpAddresses", None)
                        continue
                    network_interface["PrivateIpAddresses"] = [
                        {"Primary": True, "PrivateIpAddress": private_ip}
                    ]
    else:
        for network_interface in network_interfaces:
            network_interface.pop("PrivateIpAddresses", None)

    if row["ENI"] != "":
        # For Network interface index that has an ENI,
        # no need to specify subnetID or Security groups or primary private ip
        for ideni in all_id_enis:
            idx = ideni.split(":")[0]
            eni = ideni.split(":")[1]
            if int(idx) not in device_indexes_from_lt:
                network_interfaces.append({"DeviceIndex": int(idx)})
                device_indexes_from_lt = [i["DeviceIndex"] for i in network_interfaces]
            for network_interface in network_interfaces:
                if network_interface["DeviceIndex"] == int(idx):
                    if not eni:
                        network_interface.pop("NetworkInterfaceId", None)
                        continue
                    network_interface["NetworkInterfaceId"] = eni
                    network_interface.pop("SubnetId", None)
                    network_interface.pop("Groups", None)
                    network_interface.pop("PrivateIpAddresses", None)

    blk_device_mappings = new_ec2_launch_template["LaunchTemplateData"][
        "BlockDeviceMappings"
    ]
    if row["volume_type"] != "":
        all_dn_vtyps = row["volume_type"].split(",")
        for dnvtyp in all_dn_vtyps:
            if "windows" in row["OS"].lower():
                device_name = ":".join(dnvtyp.split(":")[:2])
                volume_type = dnvtyp.split(":")[2]
            else:
                device_name = dnvtyp.split(":")[0]
                volume_type = dnvtyp.split(":")[1]
            for blk_device_mapping in blk_device_mappings:
                if blk_device_mapping["DeviceName"] == device_name:
                    blk_device_mapping["Ebs"]["VolumeType"] = volume_type

    if row["volume_throughput"] != "":
        all_dn_vthrps = row["volume_throughput"].split(",")
        for dnvthrp in all_dn_vthrps:
            if "windows" in row["OS"].lower():
                device_name = ":".join(dnvthrp.split(":")[:2])
                volume_throughput = dnvthrp.split(":")[2]
            else:
                device_name = dnvthrp.split(":")[0]
                volume_throughput = dnvthrp.split(":")[1]
            for blk_device_mapping in blk_device_mappings:
                if blk_device_mapping["DeviceName"] == device_name:
                    if blk_device_mapping["Ebs"]["VolumeType"] == "gp3":
                        blk_device_mapping["Ebs"]["Throughput"] = int(volume_throughput)
                    else:
                        blk_device_mapping["Ebs"].pop("Throughput", None)

    if row["volume_iops"] != "":
        all_dn_viops = row["volume_iops"].split(",")
        for dnviops in all_dn_viops:
            if "windows" in row["OS"].lower():
                device_name = ":".join(dnviops.split(":")[:2])
                volume_iops = dnviops.split(":")[2]
            else:
                device_name = dnviops.split(":")[0]
                volume_iops = dnviops.split(":")[1]
            for blk_device_mapping in blk_device_mappings:
                if blk_device_mapping["DeviceName"] == device_name:
                    if (
                        blk_device_mapping["Ebs"]["VolumeType"] == "gp3"
                        or blk_device_mapping["Ebs"]["VolumeType"] == "io1"
                        or blk_device_mapping["Ebs"]["VolumeType"] == "io2"
                    ):
                        blk_device_mapping["Ebs"]["Iops"] = int(volume_iops)
                    else:
                        blk_device_mapping["Ebs"].pop("Iops", None)

    if row["Resource_tags"] != "":
        all_resource_tags = row["Resource_tags"].split(",")
        for resource_tag in all_resource_tags:
            key = resource_tag.split(":")[0]
            value = resource_tag.split(":")[1]
            rt = {"Key": key, "Value": value}
            tag_specifications = new_ec2_launch_template["LaunchTemplateData"][
                "TagSpecifications"
            ]
            if rt not in tag_specifications[0]["Tags"]:
                for tag_specification in tag_specifications:
                    tag_specification["Tags"].append(rt)

    device_indexes_from_lt = [i["DeviceIndex"] for i in network_interfaces]
    device_indexes_from_eni_row = [ideni.split(":")[0] for ideni in all_id_enis]
    device_indexes_from_subnet_row = [idsub.split(":")[0] for idsub in all_id_subs]
    device_indexes_from_sg_row = [idsg.split(":")[0] for idsg in all_id_sgs]
    device_indexes_from_pi_row = [idpi.split(":")[0] for idpi in all_id_pis]
    for ind, network_interface in enumerate(network_interfaces):
        device_interface = str(network_interface["DeviceIndex"])
        if (
            device_interface not in device_indexes_from_eni_row
            and device_interface not in device_indexes_from_subnet_row
            and device_interface not in device_indexes_from_sg_row
            and device_interface not in device_indexes_from_pi_row
        ):
            del network_interfaces[ind]

    update_ec2_launch_template(new_ec2_launch_template, source_server_id)
    update_mgn_launch_config(new_general_launch_settings, source_server_id)
    log.info("=" * 80)
    log.info("=" * 80)
    log.info("New - General Launch Settings:")
    log.info(new_general_launch_settings)
    log.info("=" * 80)
    log.info("=" * 80)
    log.info("New - EC2 Launch Settings:")
    log.info(new_ec2_launch_template)


def update_ec2_launch_template(new_ec2_launch_template, source_server_id):
    """
    Create a new EC2 Launch Template version with updated launch settings and set it
    as the default version.

    This function creates a new version of an existing EC2 Launch Template using the provided
    launch template data, and then sets this new version as the default for the template.

    Parameters:
    -----------
    new_ec2_launch_template : dict
        A dictionary containing the launch template details. It should have the following structure:
        {
            "LaunchTemplateId": str,
            "LaunchTemplateData": dict
        }
        Where "LaunchTemplateData" contains the new configuration for the launch template.

    source_server_id : str
        The ID of the source server associated with this launch template update.

    Returns:
    --------
    None

    Raises:
    -------
    Exception
        If there's an error in creating the new launch template version or setting it as default.
        The error details are logged and printed.

    Side Effects:
    -------------
    - Creates a new version of the specified EC2 Launch Template.
    - Sets the newly created version as the default for the Launch Template.
    - Prints status messages to the console.
    - Logs error messages if exceptions occur.

    Note:
    -----
    This function assumes that the EC2 client (ec2_client) and a logging object (log)
    have been properly initialized with necessary permissions.

    Example:
    --------
    >>> new_template = {
    ...     "LaunchTemplateId": "lt-0123456789abcdef0",
    ...     "LaunchTemplateData": {
    ...         "InstanceType": "t2.micro",
    ...         "KeyName": "my-key-pair"
    ...     }
    ... }
    >>> update_ec2_launch_template(new_template, "s-1234567890abcdef0")
    Creating a new EC2 Launch template version for Launch Template ID - lt-0123456789abcdef0
    Modifying the launch template for Source Server ID - s-1234567890abcdef0
    ================================================================================
    ================================================================================
    """
    try:
        print(
            f"Creating a new EC2 Launch template version for Launch Template ID - "
            f"{new_ec2_launch_template['LaunchTemplateId']}"
        )
        output = ec2_client.create_launch_template_version(
            LaunchTemplateId=new_ec2_launch_template["LaunchTemplateId"],
            LaunchTemplateData=new_ec2_launch_template["LaunchTemplateData"],
        )
        print(
            f"Modifying the launch template for Source Server ID - {source_server_id}"
        )
        ec2_client.modify_launch_template(
            LaunchTemplateId=new_ec2_launch_template["LaunchTemplateId"],
            DefaultVersion=str(output["LaunchTemplateVersion"]["VersionNumber"]),
        )
        print(
            "================================================================================"
        )
        print(
            "================================================================================"
        )
    except Exception as exception:
        log.error(
            "EC2 Launch template update failed for source server %s. Please see the error below:",
            source_server_id,
        )
        log.error(exception)
        print(exception)


def update_mgn_launch_config(new_general_launch_settings, source_server_id):
    """
    Update the MGN (AWS Application Migration Service) launch configuration for a
    specific source server.

    This function attempts to update various launch settings for a given source server
    in MGN using the provided new general launch settings.

    Args:
        new_general_launch_settings (dict): A dictionary containing the new launch
            configuration settings.
            Expected keys include:
            - bootMode
            - copyPrivateIp
            - copyTags
            - launchDisposition
            - licensing
            - targetInstanceTypeRightSizingMethod
        source_server_id (str): The unique identifier of the source server in MGN.

    Raises:
        Exception: Any exception that occurs during the update process is caught,
            logged, and printed.

    Notes:
        - This function uses a global 'mgn_client' object to interact with the MGN service.
        - If an exception occurs, an error message is logged with the source server ID
          and the full exception details.
        - The function does not return any value; it only performs the update operation
          or logs errors.

    Example:
        new_settings = {
            "bootMode": "LEGACY_BIOS",
            "copyPrivateIp": True,
            "copyTags": True,
            "launchDisposition": "STOPPED",
            "licensing": "AWS",
            "targetInstanceTypeRightSizingMethod": "NONE"
        }
        update_mgn_launch_config(new_settings, "s-1234567890abcdef0")
    """
    try:
        mgn_client.update_launch_configuration(
            bootMode=new_general_launch_settings["bootMode"],
            copyPrivateIp=new_general_launch_settings["copyPrivateIp"],
            copyTags=new_general_launch_settings["copyTags"],
            launchDisposition=new_general_launch_settings["launchDisposition"],
            licensing=new_general_launch_settings["licensing"],
            sourceServerID=source_server_id,
            targetInstanceTypeRightSizingMethod=new_general_launch_settings[
                "targetInstanceTypeRightSizingMethod"
            ],
            enableMapAutoTagging=new_general_launch_settings["enableMapAutoTagging"],
            mapAutoTaggingMpeID=new_general_launch_settings["mapAutoTaggingMpeID"],
        )
    except Exception as exception:
        log.error(
            "MGN Launch template update failed for source server %s. Please see the error below:",
            source_server_id,
        )
        log.error(exception)
        print(exception)


def main():
    """
    Main function to process source servers and update their launch configurations.

    This function performs the following steps:
    1. Retrieves all source servers.
    2. Reads a CSV file named "sample_template.csv" containing server information.
    3. For each row in the CSV:
        a. Retrieves the source server ID based on the hostname.
        b. Checks the lifecycle state of the server.
        c. If the server is not disconnected or in cutover state:
            - Retrieves the current launch configuration and template version.
            - Updates the launch configuration with new settings from the CSV row.

    The function skips servers that are disconnected or in cutover state, logging an
    info message for each skipped server.

    Note:
    - The CSV file should have a column named "Server_Name" for the hostname.
    - The function relies on several helper functions (not shown) to retrieve and
      update server information.
    - The CSV file is automatically closed after processing.

    Raises:
        Any exceptions raised by the helper functions or file operations are not caught
        in this function.
    """
    parser = argparse.ArgumentParser(
        description="Update MGN launch configurations based on a CSV file.",
    )
    parser.add_argument(
        "--template-file",
        help="Specify the path to the CSV file containing server information",
        type=str,
        default="sample_template.csv",
    )
    args = parser.parse_args()

    source_servers = get_all_source_servers()
    with open(args.template_file, mode="r", encoding="utf-8-sig") as scriptfile:
        scriptfile_reader = csv.DictReader(scriptfile)
        for row in scriptfile_reader:
            hostname = row["Server_Name"]
            source_server_id = get_source_server_id(hostname, source_servers)
            if source_server_id is None:
                continue
            lifecycle_state = query_lifecycle_state(source_server_id)
            if lifecycle_state in ("DISCONNECTED", "CUTOVER"):
                log.info(
                    "Source Server %s skipped as it is in disconnected or cutover state",
                    source_server_id,
                )
                continue
            general_launch_settings, launch_template_version = get_launch_config(
                source_server_id, hostname
            )
            update_launch_config(
                general_launch_settings, launch_template_version, source_server_id, row
            )
    scriptfile.close()


if __name__ == "__main__":
    main()
