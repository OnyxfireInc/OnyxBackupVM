# Changelog for OnyxBackupVM
### VM Backup for Citrix Hypervisor/XCP-NG

### Future Release
  #### Features and Enhancements
  - Convert remaining functions to XAPI calls only
  - Automatically use remote authentication if not running on CH/xcp-ng host

### v1.3.1 - 10 Apr 2020
  #### Features and Enhancements
  - Changed logging of date and time to ISO 8601 format #18

### v1.3.0 - 18 March 2019
  #### Features and Enhancements
  - VDI exports and VM Exports of the same VM #15
  #### Bugs
  - VM can be processed twice if the VM is matched twice within the same list under certain circumstances #16

### v1.2.3 - 26 November 2018
  #### Bugs
  - Fixed blank elapsed time for operations less than 1 second

### v1.2.2 - 8 August 2018
  #### Features and Enhancements
  - Time elapsed in minutes/hours instead of decimal #12

### v1.2.1 - 24 July 2018
  #### Features and Enhancements
  - VSS snapshots should have fallback #10

### v1.2.0 - 26 June 2018
  #### Bugs
  - Snapshot checking too eager #6

  #### Features and Enhancements
  - More accurate elapsed time reporting #8
  - More accurate file size reporting for backups #7
  - Quiesced snapshots by default if available #5

  #### Other Changes
  - Duplicated code in service layer #4 (complete refactoring of service layer)

### v1.1.1 - 18 June 2018
  - Initial release
