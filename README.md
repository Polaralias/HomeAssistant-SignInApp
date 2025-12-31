# Home Assistant Sign In App Integration

This is a custom integration for [Home Assistant](https://www.home-assistant.io/) that connects to [Sign In App](https://signinapp.com/). It allows you to manage sign-ins and sign-outs, track your status, and automate actions based on your Sign In App status.

## Features

-   **Sign In / Sign Out**: Services to sign in or out of your configured sites directly from Home Assistant.
-   **Site Types**: Supports both 'Office' and 'Remote' site types.
-   **Status Tracking**: Sensor entity that reflects your current status (e.g., Signed In (Office), Signed In (Remote), Signed Out).
-   **Authentication**: Uses a secure companion code for initial authentication.
-   **Location Integration**: Uses a configurable `person` entity for location data during Office sign-ins.

## Installation

### HACS (Recommended)

1.  Ensure you have [HACS](https://hacs.xyz/) installed.
2.  Add this repository as a custom repository in HACS:
    *   Go to **HACS** -> **Integrations**.
    *   Click the 3 dots in the top right corner and select **Custom repositories**.
    *   Enter the URL of this repository.
    *   Select **Integration** as the category.
    *   Click **Add**.
3.  Search for "Sign In App" in HACS and install it.
4.  Restart Home Assistant.

### Manual Installation

1.  Download the `custom_components/signinapp` directory from this repository.
2.  Copy the `signinapp` directory to your Home Assistant `custom_components` directory.
3.  Restart Home Assistant.

## Configuration

1.  Navigate to **Settings** -> **Devices & Services**.
2.  Click **Add Integration** and search for "Sign In App".
3.  **Authentication**:
    *   Enter your **Companion Code**. You can generate this from the Sign In App portal or mobile app (check the email invitation or your profile settings).
4.  **Site Configuration**:
    *   The integration will fetch available sites associated with your account.
    *   **Remote Site ID**: Enter the ID for your Remote site (displayed in the setup dialog).
    *   **Office Site ID**: Enter the ID for your Office site (displayed in the setup dialog).
    *   **Person Tracker**: Select the `person` entity that represents you. This is used to determine your location when signing in to the Office.
    *   **Office Distance**: Set the radius (in meters) for considering you "at the office". Default is 50m.

## Usage

### Entities

The integration creates a sensor entity for the configured user:
*   `sensor.signinapp_<name>`: Shows the current state (e.g., `Signed In (Office)`, `Signed In (Remote)`, `Signed Out`).

### Services

You can use the following services in your automations and scripts:

#### `signinapp.sign_in`
Signs the user in.

| Field | Description | Required | Options |
| :--- | :--- | :--- | :--- |
| **Site Type** | The type of site to sign in to. | Yes | `Office`, `Remote` |

**Note**:
*   **Office**: Uses the latitude/longitude from your configured `person` entity.
*   **Remote**: Uses 0 for latitude/longitude.

#### `signinapp.sign_out`
Signs the user out.

| Field | Description | Required | Options |
| :--- | :--- | :--- | :--- |
| **Site Type** | The type of site to sign out from. If omitted, the integration attempts to auto-detect the context. | No | `Office`, `Remote` |
