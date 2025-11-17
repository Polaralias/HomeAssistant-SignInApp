# HomeAssistant Sign In App Integration

A Home Assistant custom component that connects to Sign In App to surface details about devices signed into your workplace locations. The integration supports multiple devices and shows their status directly inside Home Assistant.

## Features
- Discover and monitor all configured Sign In App devices within Home Assistant.
- Track live status for multiple devices across different locations.
- Configure via the Home Assistant UI with minimal setup.

## Installation
1. Ensure [HACS](https://hacs.xyz/) is installed in your Home Assistant instance.
2. In HACS, add this repository as a custom integration repository using the URL of this project.
3. After adding the repository, search for "Sign In App" under Integrations and install it.
4. Restart Home Assistant once installation completes.

## Setup in Home Assistant
1. Open **Settings > Devices & Services** and click **Add Integration**.
2. Search for **Sign In App** and select it.
3. Enter your Sign In App API credentials and confirm.
4. Select the devices and locations you want to monitor. Multiple devices can be added and managed after setup.
5. Finish the flow to create sensors reflecting your Sign In App device statuses.

## Updating
When updates are released, HACS will notify you. Apply updates from HACS and restart Home Assistant if prompted.
