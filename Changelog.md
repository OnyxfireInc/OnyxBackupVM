# Changelog for OnyxBackup-XS
### VM Backup for XenServer/XCP-NG

### v1.1.0 - 18 June 2018
  #### New Features
  - Added config option to enable/disable starttls for smtp
  #### Config Changes
  - For compatibility reasons, starttls is now disabled by default. If you wish to encrypt your emails outbound simply override the default in your config file.

### v1.0.1 - 18 June 2018
  #### New Features
  - Added built-in SMTP support for email reports
  #### Config Changes
  - No longer relies on cron to email reports. Cron entries should now redirect stdout and stderr to /dev/null and enable smtp functionality through config files

### v1.0.0 - 2 March 2018
	Inital Release
