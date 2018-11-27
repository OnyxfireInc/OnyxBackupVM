# Changelog for OnyxBackupVM
### VM Backup for XenServer/XCP-NG

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
