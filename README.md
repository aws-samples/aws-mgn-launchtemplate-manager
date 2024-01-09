# AWS MGN LaunchTemplate Manager

This project was built to simplify management of target server's configurations for rehost migrations with AWS MGN.

Each target server has two sections to manage:

* **General Launch Settings** section, specific to AWS MGN service, and
* **EC2 Launch Template** section, related to an actual EC2 Launch Template object created per each target server

Two scripts below are created to help manage these configurations at scale:

1. `target-templates-import` to import configuration of multiple target servers (already added to MGN Console) from a single CSV file, usually the result of a previous assessment tool's output (ie: Migration Evaluator, Cloudamize, Cloudscape, etc)

2. `target-templates-update` to copy/clone/fine-tune specific target server configuration paramenters during PoCs or migration projects done w/o assessment tools


