# Instructions
- Copy buttplug folder into /custom_components/ folder of home-assistant config
- Restart home assistant
- add buttplug integration via home-assistant UI
- provide host/ip and port of a buttplug server (such as intiface-desktop)
  - (name provided during configuration is just for logging)
- Devices should show up when connected to the buttplug server; and be controllable via their attached entities

# Known Issues
- Lots more work to be done handling error cases like if the buttplug server stops running; currently you need to reset the integration to recover from that; though resetting takes like 1 second to complete.
- device-ping/activation when devices are added can be disruptive if connection is dropping in and out (so made worse by the bullet above)
- doesn't yet handle multiple devices with the same name (as determined by buttplug server)
- linear motors don't have a configurable time-per-command; always 1 second. Will want to figure out a good UI component that lets you submit multiple values simultaneously.

