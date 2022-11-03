# AWS MGN Launch Template Import
Any migration (medium or large sized) goes through 3 phases of the migration journey – Assess, Mobilize, Migrate & Modernize. To know more about the phases of a migration journey, please read the prescriptive guidance document [here](https://docs.aws.amazon.com/prescriptive-guidance/latest/strategy-migration/overview.html). In the assess phase, you build your business case for migration, and analyze portfolio and server inventory in scope of migration. Customers often use existing configuration management database (CMDB) or several discovery and assessment tools to build an inventory of the IT landscape that is in scope of the migration. These outputs from CMDB or Discovery & Assessment tools are often in CSV formats. 

This solution focuses on taking this inventory data from CSV file and using it in rehosting your servers through AWS MGN. The output from the CSV file will need to be imported into a standard flat file (sample_template.csv) which will be then used to automate MGN and EC2 Launch template for each of the source machines

# Flat file (sample_template.csv)
There are several columns in the sample_template.csv flat file. These columns are defined to align with MGN and EC2 Launch template for migrating through MGN. These are the possible values that you will specify for each of the columns:

```
Server_Name - (Hostname of source server)	
OS - Linux or windows
Instance_type_right_sizing - BASIC or NONE
EC2_Instance_type - EC2 Instance Type
Subnet_ID - 0:subnet-xxxxxxxx,1:subnet-yyyyyyyy
Security_Groups	- 0:sg-xxxxxxxx,1:sg-yyyyyyy;sg-zzzzzzzz
Copy_private_ip	- True or False
Start_Instance_upon_launch	- STOPPED or STARTED
Transfer_Server_tags - True or False
OS_licensing_byol - True or False
Boot_mode - LEGACY_BIOS or UEFI 
Primary_private_ip - 0:192.168.x.x,1:172.16.x.x,2:10.x.x.x
ENI	- 0:eni-xxxxxxxx,1:eni-yyyyyyyyy
volume_type	- 
/dev/xvda:gp3,/dev/xvdb:gp2	(For Linux)
c:0:gp3,d:0:gp2    (For windows)
volume_throughput -
/dev/xvda:125,/dev/xvdb:125	(For Linux)
c:0:125,d:0:125   (For windows)
volume_iops	-
/dev/xvda:3000,/dev/xvdb:3000	(For Linux)
c:0:3000,d:0:3000   (For windows)
Resource_tags - app:wordpress,env:dev
placement_group_name - Placement group name
Tenancy	- default or dedicated or host
HostresourceGroupArn - arn:aws:resource-groups:us-east-1:account-id:group/HostresourceGroupName
HostId - h-xxxxxxxxxxx
```

Fill in the sample_template.csv for all source servers or subset of source servers added on MGN console. This data is already available when you ran a discovery and assessment tool or you have a CMDB of your own, so copy the data from those files to populate some of the columns on sample_template.csv. 

# Rules to follow for updating the sample_template.csv file
There are some ground rules for updating the csv file. The rules are as below:

1.  You only add to the CSV columns what you want to change in the existing MGN and EC2 Launch templates.

2. For adding multiple network interfaces on target and selecting appropriate subnets, security groups, or primary private IP addresses for each, you need to specify network device index and corresponding subnet or security group or primary private IP address in csv as shown below:

```
Subnet_ID - 0:subnet-xxxxxxxx,1:subnet-yyyyyyyy
Security_Groups - 0:sg-xxxxxxxx,1:sg-yyyyyyy;sg-zzzzzzzz
Primary_private_ip - 0:192.168.x.x,1:172.16.x.x,2:10.x.x.xxxxxxxx
```



> Note - ‘0’, ‘1’, and '2' above indicates the network device index for the network interfaces. '0' being the network device index for primary interfaces. And each network device index is separated by a comma.


2. If you added a secondary network device index and pushed the change by running the script but now you want to remove the network interface with a specific network device index, then make sure you remove that specific network device index from all columns of the csv and push the change again.

3. If you added a specific network device index/network interface with subnet, SG, and Primary private Ip and pushed the change by running the script, but now you want to remove SG or primary private IP from that network device index and retain the network device index with only subnet value, then you need to make the change to csv as below:

eg. If you want to remove SG and Primary private IP from network device index '1' but keep subnet-Id:
```
Subnet_ID - 0:subnet-xxxxxxxx,1:subnet-yyyyyyyy
Security_Groups - 0:sg-xxxxxxxx,1:
Primary_private_ip - 0:192.168.x.x,1:

```



4. For changing EBS volume type, volume throughput or volume iops, you need to specify the AWS storage device name and the value. For eg.

```
volume_type - 
/dev/xvda:gp3,/dev/xvdb:gp2	(For Linux)
c:0:gp3,d:0:gp2    (For windows)

volume_throughput -
/dev/xvda:125,/dev/xvdb:125	(For Linux)
c:0:125,d:0:125   (For windows)

volume_iops -
/dev/xvda:3000,/dev/xvdb:3000	(For Linux)
c:0:3000,d:0:3000   (For windows)
```




5. If you specify an ENI column with an ENI-Id, it is assumed that this ENI is already configured with a subnet, SG, and primary private IP address, so ENI-Id will take precedence over what you specify in Subnet_ID, Security_Groups, Primary_private_ip.

6. Ensure that the mgn_launch_automate.py and sample_template.csv files are in the same location.



# Running the 'target_templates_import.py' script

Once you have updated the sample_template.csv file, you are ready to run the script – “target_templates_import.py”. This python script will ingest the csv file and update the MGN Launch general settings and EC2 Launch templates for each of the source machines as shown in its output below.


```
Creating a new EC2 Launch template version for Launch Template ID - lt-xxxxxxxxxx
Modifying the launch template for Source Server ID - s-xxxxxxxxxxx
================================================================================
================================================================================
Creating a new EC2 Launch template version for Launch Template ID - lt-yyyyyyyyyyy
Modifying the launch template for Source Server ID - s-yyyyyyyyyy
================================================================================
================================================================================
Creating a new EC2 Launch template version for Launch Template ID - lt-zzzzzzzzzzz
Modifying the launch template for Source Server ID - s-zzzzzzzzzzz
================================================================================
================================================================================
```






