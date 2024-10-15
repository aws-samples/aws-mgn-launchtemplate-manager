# AWS MGN Launch Template Update

Project to create a set of scripts / simplifications to manage (copy, clone, mass-apply) EC2 Launch Template(s) across serves migrated by AWS Application Migration Service (MGN)


---

# Use Cases

1. Apply one EC2 Launch Template to all other actively migrating servers in the migration wave
2. Tag servers in MGN Console to group by application / layer (like DB / apps / etc) and apply EC2 LTs only to these 
3. apply/clone EC2 LTs to another server by individual ServerID (MGN-ID)

# Script arguments: 

1. `--target <target>`

    Options:
    1. all - target all servers replicating in MGN.
    2. key=value - target all servers with the key tag key/value pair
    3. s-1111111 - target server s-1111111
    4. s-1111111,s-2222222,s-3333333 - target the list of comma separated servers

2. `--template-id <id>`

    use template id as the blueprint to update the launch template associated with target servers

3. `--source-server <id>`

    Use the launch template associated with the source server to update launch template

4. `--copy-launch-settings`

    Copy launch configuration/settings from the source server or launch configuration json file to update launch configuration of target servers. Without this option, only launch template is updated

5. `--copy-post-launch-settings`

    Copy post launch configuration/settings from the source server to update post launch configuration of target servers.

5. `--launch-settings-file launch_configuration.json`

    Copy launch configuration/settings from the file

6. `--parameters`

    Specify the parameters that should be copied from source launch template. Comma separated list of:

    SubnetId,AssociatePublicIpAddress,DeleteOnTermination,Groups,Tenancy,IamInstanceProfile,InstanceType

7. `--debug`

    Enable debugging messages

---

# Example script commands: 

1. `python mgn-update-template --target all --template-id lt-0259a7eb0bfbd77c8`

    Update existing templates for all replicating servers based on template lt-0259a7eb0bfbd77c8

2. `python mgn-update-template --target s-111111111,s-2222222,s-333333333 --template-id lt-0259a7eb0bfbd77c8`

    Update existing templates for the servers based on template lt-0259a7eb0bfbd77c8

3. `python mgn-update-template --target s-111111111,s-2222222,s-333333333 --template-id lt-0259a7eb0bfbd77c8 --parameters SubnetId,IamInstanceProfile`

    Update existing templates for the servers based on template lt-0259a7eb0bfbd77c8 but only copy the SubnetId and IamInstanceProfile
    
4. `python mgn-update-template --target s-111111111,s-2222222,s-333333333 --template-id lt-0259a7eb0bfbd77c8 --copy-launch-settings --launch-settings-file launch_configuration.json`
    
    Update existing templates for the servers based on template lt-0259a7eb0bfbd77c8 and launch configuration based on information from file launch_configuration.json

5. `python mgn-update-template --target s-111111111,s-2222222,s-333333333 --source-server s-3fae7af2d2d13fa9f --copy-launch-settings`
    
    Update existing templates for the servers based on source server launch template and launch configuration 

6. `python mgn-update-template --target s-111111111,s-2222222,s-333333333 --source-server s-3fae7af2d2d13fa9f --copy-post-launch-settings`

    Update existing templates for the servers based on source server post launch configuration 

7. `python mgn-update-template --target s-111111111,s-2222222,s-333333333 --source-server s-3fae7af2d2d13fa9f --copy-launch-settings --copy-post-launch-settings`

    Update existing templates for the servers based on source server launch and post-launch configuration 

8. `python mgn-update-template --target key=value --template-id lt-0259a7eb0bfbd77c8`
    
    Updates existing template for all servers with matching tag key/value pair based on template with id lt-0259a7eb0bfbd77c8

