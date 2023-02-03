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
import json
import csv
import logging

logging.basicConfig(filename='mgn_launch_automate.log', format='%(asctime)s%(levelname)s:%(message)s', level=logging.DEBUG)
log = logging.getLogger(__name__)

mgn_client = boto3.client('mgn')
ec2_client = boto3.client('ec2')



def get_launch_config(sourceServerID,hostname):
	'''Get the general launch settings from MGN and Ec2 Launch settings for a source server'''
	general_launch_settings = mgn_client.get_launch_configuration(
		sourceServerID=sourceServerID
	)

	del general_launch_settings['ResponseMetadata']
	log.info ("=================================== Old Launch configuration====================================")
	log.info ("Old Launch Configuration for host {} with SourceServerID {}".format(hostname,sourceServerID))
	log.info ("================================================================================================")
	log.info ("================================================================================================")
	log.info ("Old - General Launch Settings:")
	log.info (general_launch_settings)

	lt = ec2_client.describe_launch_template_versions(LaunchTemplateId=general_launch_settings['ec2LaunchTemplateID'])
	launchTemplateVersions = lt['LaunchTemplateVersions']
	for launchTemplateVersion in launchTemplateVersions:
		if launchTemplateVersion['DefaultVersion'] == True:
			log.info ("================================================================================================")
			log.info ("================================================================================================")
			log.info ("Old - EC2 Launch Settings:")
			log.info (launchTemplateVersion)
			break
	return general_launch_settings,launchTemplateVersion


def query_lifecycle_state(sourceServerID):
	'''Query lifecycle state of source server'''
	res = mgn_client.describe_source_servers(filters={'sourceServerIDs': [sourceServerID]})
	del res['ResponseMetadata']
	lifecycle_state = res['items'][0]['lifeCycle']['state']
	return (lifecycle_state)


def get_all_source_servers():
	'''Get all source servers from MGN console'''
	sourceServers = mgn_client.describe_source_servers(filters={'isArchived': False})
	return sourceServers['items']


def get_source_serverID(hostname, sourceServers):
	'''Get the source server ID'''
	for sourceServer in sourceServers:
		if 'hostname' in sourceServer['sourceProperties']['identificationHints'] and sourceServer['sourceProperties']['identificationHints']['hostname'] == hostname:
			log.info (sourceServer['sourceServerID'])
			return sourceServer['sourceServerID']
	return None

def update_launch_config(general_launch_settings, launchTemplateVersion, sourceServerID, row):
	'''Update the Ec2 launch template and general launch settings json before publishing'''
	newEc2Launchtemplate = launchTemplateVersion
	newGeneralLaunchSettings = general_launch_settings
	if row['Instance_type_right_sizing'] != '' and general_launch_settings['targetInstanceTypeRightSizingMethod'] != row['Instance_type_right_sizing']:
		newGeneralLaunchSettings['targetInstanceTypeRightSizingMethod'] = row['Instance_type_right_sizing']
	if newGeneralLaunchSettings['targetInstanceTypeRightSizingMethod'] != 'BASIC' and row['EC2_Instance_type'] != '':
		newEc2Launchtemplate['LaunchTemplateData']['InstanceType'] = row['EC2_Instance_type']
	if row['Copy_private_ip'] != '' and row['Copy_private_ip'].capitalize() != str(general_launch_settings['copyPrivateIp']):
		newGeneralLaunchSettings['copyPrivateIp'] = True if row['Copy_private_ip'].capitalize() == "True" else False
	if row['Start_Instance_upon_launch'] != '' and general_launch_settings['launchDisposition'] != row['Start_Instance_upon_launch']:
		newGeneralLaunchSettings['launchDisposition'] = row['Start_Instance_upon_launch']
	if row['Transfer_Server_tags'] != '' and str(general_launch_settings['copyTags']) != row['Transfer_Server_tags'].capitalize():
		newGeneralLaunchSettings['copyTags'] = True if row['Transfer_Server_tags'].capitalize() == "True" else False
	if 'windows' in row['OS'].lower() and row['OS_licensing_byol'] != '':
		newGeneralLaunchSettings['licensing']['osByol'] = True if row['OS_licensing_byol'].capitalize() == "True" else False
	if 'windows' in row['OS'].lower() and row['Boot_mode'] != '':
		newGeneralLaunchSettings['bootMode'] = row['Boot_mode']
	if row['placement_group_name'] != '':
		if 'Placement' not in newEc2Launchtemplate['LaunchTemplateData']:
			newEc2Launchtemplate['LaunchTemplateData']['Placement'] = {}
		newEc2Launchtemplate['LaunchTemplateData']['Placement']['GroupName'] = row['placement_group_name']
	if 'windows' in row['OS'].lower() and row['Tenancy'] != '':                      # MGN specific 'windows' check as dedicated and host tenancy only supported by windows
		if 'Placement' not in newEc2Launchtemplate['LaunchTemplateData']:
			newEc2Launchtemplate['LaunchTemplateData']['Placement'] = {}
		newEc2Launchtemplate['LaunchTemplateData']['Placement']['Tenancy'] = row['Tenancy']
		if newEc2Launchtemplate['LaunchTemplateData']['Placement']['Tenancy'] == 'default' or newEc2Launchtemplate['LaunchTemplateData']['Placement']['Tenancy'] == 'dedicated':
			newEc2Launchtemplate['LaunchTemplateData']['Placement'].pop('HostId', None)
			newEc2Launchtemplate['LaunchTemplateData']['Placement'].pop('HostResourceGroupArn', None)
		elif row['HostresourceGroupArn'] != '':
			newEc2Launchtemplate['LaunchTemplateData']['Placement']['HostResourceGroupArn'] = row['HostresourceGroupArn']
			newEc2Launchtemplate['LaunchTemplateData']['Placement'].pop('HostId', None)
		elif row['HostId'] != '':
			newEc2Launchtemplate['LaunchTemplateData']['Placement']['HostId'] = row['HostId']
			newEc2Launchtemplate['LaunchTemplateData']['Placement'].pop('HostResourceGroupArn', None)
				
	
	network_interfaces = newEc2Launchtemplate['LaunchTemplateData']['NetworkInterfaces']
	device_indexes_from_lt = [i['DeviceIndex'] for i in network_interfaces]
	
	#Remove all white space characters from csv and split using a comma 
	all_id_enis = "".join(row['ENI'].split()).split(',')
	all_id_subs = "".join(row['Subnet_ID'].split()).split(',')
	all_id_sgs = "".join(row['Security_Groups'].split()).split(',')
	all_id_pis = "".join(row['Primary_private_ip'].split()).split(',')
	

	if row['Subnet_ID'] != '':  
		for idsub in all_id_subs:                    #If no ENI-Id is present for a network device index, then subnet-id for network device index can be present
			idx = idsub.split(':')[0]
			sub = idsub.split(':')[1]
			if int(idx) not in device_indexes_from_lt:
				network_interfaces.append({'DeviceIndex': int(idx)})
				device_indexes_from_lt = [i['DeviceIndex'] for i in network_interfaces]
			for ni in network_interfaces:
				if ni['DeviceIndex'] == int(idx):
					if not sub:
						ni.pop('SubnetId', None)
						continue
					ni['SubnetId'] = sub
					ni.pop('NetworkInterfaceId', None)
					
	if row['Security_Groups'] != '':                  #If no ENI-Id is present for a network device index, then security group for network device index can be present
		device_indexes = [i['DeviceIndex'] for i in network_interfaces]
		for idsg in all_id_sgs:
			idx = idsg.split(':')[0]
			sg = idsg.split(':')[1].split(';')
			if int(idx) not in device_indexes_from_lt:
				network_interfaces.append({'DeviceIndex': int(idx)})
				device_indexes_from_lt = [i['DeviceIndex'] for i in network_interfaces]	
			for ni in network_interfaces:
				if ni['DeviceIndex'] == int(idx):
					if not sg:
						ni.pop('Groups', None)
						continue
					ni['Groups'] = sg
					ni.pop('NetworkInterfaceId', None)


	if row['Primary_private_ip'] != '':               #If no ENI-Id is present for a network device index, then primary private ip for network device index can be present
		for idpi in all_id_pis:
			idx = idpi.split(':')[0]
			pi = idpi.split(':')[1]
			if int(idx) not in device_indexes_from_lt:
				network_interfaces.append({'DeviceIndex': int(idx)})
				device_indexes_from_lt = [i['DeviceIndex'] for i in network_interfaces]
			if int(idx) == 0 and row['Copy_private_ip'].capitalize() == "True":
				continue
			for ni in network_interfaces:
				if ni['DeviceIndex'] == int(idx):
					if not pi:
						ni.pop('PrivateIpAddresses', None)
						continue
					ni['PrivateIpAddresses'] = [{'Primary': True, 'PrivateIpAddress': pi}]
	else:
		for ni in network_interfaces:
			ni.pop('PrivateIpAddresses', None)
			
					
	if row['ENI'] != '':                               #For Network interface index that has an ENI, no need to specify subnetID or Security groups or primary private ip
		for ideni in all_id_enis:            
			idx = ideni.split(':')[0]
			eni = ideni.split(':')[1]
			if int(idx) not in device_indexes_from_lt:
				network_interfaces.append({'DeviceIndex': int(idx)})
				device_indexes_from_lt = [i['DeviceIndex'] for i in network_interfaces]
			for ni in network_interfaces:
				if ni['DeviceIndex'] == int(idx):
					if not eni:
						ni.pop('NetworkInterfaceId', None)
						continue
					ni['NetworkInterfaceId'] = eni
					ni.pop('SubnetId', None)
					ni.pop('Groups', None)
					ni.pop('PrivateIpAddresses', None)
	
	blk_device_mappings = newEc2Launchtemplate['LaunchTemplateData']['BlockDeviceMappings']
	if row['volume_type'] != '':
		all_dn_vtyps = row['volume_type'].split(',')
		for dnvtyp in all_dn_vtyps:
			if 'windows' in row['OS'].lower():
				device_name = ":".join(dnvtyp.split(':')[:2])
				volume_type = dnvtyp.split(':')[2]
			else:
				device_name = dnvtyp.split(':')[0]
				volume_type = dnvtyp.split(':')[1]
			for blk_device_mapping in blk_device_mappings:
				if blk_device_mapping['DeviceName'] == device_name:
					blk_device_mapping['Ebs']['VolumeType'] = volume_type
	
	if row['volume_throughput'] != '':
		all_dn_vthrps = row['volume_throughput'].split(',')
		for dnvthrp in all_dn_vthrps:
			if 'windows' in row['OS'].lower():
				device_name = ":".join(dnvthrp.split(':')[:2])
				volume_throughput = dnvthrp.split(':')[2]
			else:
				device_name = dnvthrp.split(':')[0]
				volume_throughput = dnvthrp.split(':')[1]
			for blk_device_mapping in blk_device_mappings:
				if blk_device_mapping['DeviceName'] == device_name: 
					if blk_device_mapping['Ebs']['VolumeType'] == 'gp3':
						blk_device_mapping['Ebs']['Throughput'] = int(volume_throughput)
					else:
						blk_device_mapping['Ebs'].pop('Throughput', None)

	if row['volume_iops'] != '':
		all_dn_viops = row['volume_iops'].split(',')
		for dnviops in all_dn_viops:
			if 'windows' in row['OS'].lower():
				device_name = ":".join(dnviops.split(':')[:2])
				volume_iops = dnviops.split(':')[2]
			else:
				device_name = dnviops.split(':')[0]
				volume_iops = dnviops.split(':')[1]
			for blk_device_mapping in blk_device_mappings:
				if blk_device_mapping['DeviceName'] == device_name: 
					if blk_device_mapping['Ebs']['VolumeType'] == 'gp3' or blk_device_mapping['Ebs']['VolumeType'] == 'io1' \
					or blk_device_mapping['Ebs']['VolumeType'] == 'io2':
						blk_device_mapping['Ebs']['Iops'] = int(volume_iops)
					else:
						blk_device_mapping['Ebs'].pop('Iops', None)
						
					
	if row['Resource_tags'] != '':
		all_resource_tags = row['Resource_tags'].split(',')
		for resource_tag in all_resource_tags:
			key = resource_tag.split(':')[0]
			value = resource_tag.split(':')[1]
			rt = {'Key':key, 'Value':value}
			tag_specifications = newEc2Launchtemplate['LaunchTemplateData']['TagSpecifications']
			if rt not in tag_specifications[0]['Tags']:
				for tag_specification in tag_specifications:
					tag_specification['Tags'].append(rt)


	device_indexes_from_lt = [i['DeviceIndex'] for i in network_interfaces]				
	device_indexes_from_eni_row = [ideni.split(':')[0] for ideni in all_id_enis]
	device_indexes_from_subnet_row = [idsub.split(':')[0] for idsub in all_id_subs]
	device_indexes_from_sg_row = [idsg.split(':')[0] for idsg in all_id_sgs]
	device_indexes_from_pi_row = [idpi.split(':')[0] for idpi in all_id_pis]
	for ind,ni in enumerate(network_interfaces):
		di = str(ni['DeviceIndex'])
		if  di not in device_indexes_from_eni_row and di not in device_indexes_from_subnet_row and di not in device_indexes_from_sg_row \
		and di not in device_indexes_from_pi_row:
			del network_interfaces[ind]
	

	update_ec2_launch_template(newEc2Launchtemplate, sourceServerID)
	update_mgn_launch_config(newGeneralLaunchSettings, sourceServerID)
	log.info ("================================================================================================")
	log.info ("================================================================================================")
	log.info ("New - General Launch Settings:")
	log.info (newGeneralLaunchSettings)
	log.info ("================================================================================================")
	log.info ("================================================================================================")
	log.info ("New - EC2 Launch Settings:")
	log.info (newEc2Launchtemplate)
	
def update_ec2_launch_template(newEc2Launchtemplate, sourceServerID):
	'''Create a new Ec2 Launch template version with new launch setting and make it default version'''
	try:
		print ("Creating a new EC2 Launch template version for Launch Template ID - {}".format(newEc2Launchtemplate['LaunchTemplateId']))
		output = ec2_client.create_launch_template_version(LaunchTemplateId = newEc2Launchtemplate['LaunchTemplateId'], 
		LaunchTemplateData = newEc2Launchtemplate['LaunchTemplateData'])
		print ("Modifying the launch template for Source Server ID - {}".format(sourceServerID))
		ec2_client.modify_launch_template(LaunchTemplateId = newEc2Launchtemplate['LaunchTemplateId'], 
		DefaultVersion=str(output['LaunchTemplateVersion']['VersionNumber']))
		print ("================================================================================")
		print ("================================================================================")
	except Exception as e:
		log.error("EC2 Launch template update failed for source server {}. Please see the error below:".format(sourceServerID))
		log.error(e)
		print (e)
		
				
			
def update_mgn_launch_config(newGeneralLaunchSettings, sourceServerID):
	'''Update MGN General Launch Settings'''
	try:
		mgn_client.update_launch_configuration(bootMode=newGeneralLaunchSettings['bootMode'],
    copyPrivateIp=newGeneralLaunchSettings['copyPrivateIp'],
    copyTags=newGeneralLaunchSettings['copyTags'],
    launchDisposition=newGeneralLaunchSettings['launchDisposition'],
    licensing=newGeneralLaunchSettings['licensing'],
    sourceServerID=sourceServerID,
    targetInstanceTypeRightSizingMethod=newGeneralLaunchSettings['targetInstanceTypeRightSizingMethod']
)
	except Exception as e:
		log.error("MGN Launch template update failed for source server {}. Please see the error below:".format(sourceServerID))
		log.error(e)
		print (e)
		
 

def main():
	sourceServers = get_all_source_servers()
	with open('sample_template.csv', mode='r', encoding='utf-8-sig') as scriptfile:
		scriptfile_reader = csv.DictReader(scriptfile)
		for row in scriptfile_reader:
			hostname = row['Server_Name']
			sourceServerID = get_source_serverID(hostname, sourceServers)
			if sourceServerID == None:
				continue
			lifecycle_state = query_lifecycle_state(sourceServerID)
			if lifecycle_state == 'DISCONNECTED' or lifecycle_state == 'CUTOVER':
				log.info ("Source Server {} skipped as it is in disconnected or cutover state".format(sourceServerID))
				continue
			general_launch_settings,launchTemplateVersion = get_launch_config(sourceServerID, hostname)
			update_launch_config(general_launch_settings, launchTemplateVersion, sourceServerID, row)
	scriptfile.close()
			
			
	
	
	
	
	
if __name__ == '__main__':
	main()
