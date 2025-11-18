# Sign In App Home Assistant Integration

Home Assistant custom integration for Sign In App companion devices. Each config entry represents one companion device linked to a Home Assistant `device_tracker`, supports site-aware automatic sign in/out, and exposes an optional status sensor. Multiple devices are supported by adding multiple config entries.

## Installation via HACS
1. Install [HACS](https://hacs.xyz/) in your Home Assistant instance.
2. In HACS, add this repository as a custom integration repository using `https://github.com/youruser/hass-signinapp` as the repository URL.
3. Install **Sign In App** from HACS, then restart Home Assistant.
4. Go to **Settings → Devices & Services**, add **Sign In App**, enter your companion code, choose office/remote sites and a `device_tracker`, and finish the flow. Repeat to add more devices.

## Features
- Pair Sign In App companion codes to obtain and store long-lived tokens securely per config entry.
- Uses a selected `device_tracker` entity to supply GPS coordinates for sign in/out, matching the device zone to pick office or remote sites by default.
- Services to sign in, sign out, or auto sign in using the configured sites.
- Optional status sensor per companion device reflecting current Sign In App state.
- Supports multiple companion devices in a single Home Assistant instance.
