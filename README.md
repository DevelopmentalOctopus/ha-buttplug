[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

# Instructions
- Use HACS to install, or copy the `custom_components/buttplug` folder into Home Assistant's `custom_components` folder.
- Restart Home Assistant.
- Add the Buttplug integration via Home Assistant's UI.
  - Provide host/ip and port of an existing buttplug server.
    - E.g. [intiface-desktop](https://github.com/intiface/intiface-desktop/)
  - The name provided during configuration is just for log messages.
- Devices should show up when connected to the buttplug server; and be controllable via their attached entities.

# Known Issues
- Configuration fields aren't fully/properly labeled.
- Lots more work to be done handling error cases like if the buttplug server stops running; currently you need to reset the integration to recover from that; though resetting takes like 1 second to complete.
- Device-ping/activation when devices are added can be disruptive if connection is dropping in and out (so made worse by the bullet above)
- Doesn't yet handle multiple devices with the same name (as determined by buttplug server)
- Linear motors don't have a configurable time-per-command; always 1 second. Will want to figure out a good UI component that lets you submit multiple values simultaneously.
- Rotational motors don't have very touch-friendly UX in some views.
  - Negative values are used to reverse rotation; but this makes setting to 0 more difficult.