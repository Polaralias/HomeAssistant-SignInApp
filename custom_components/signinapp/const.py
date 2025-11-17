"""Constants for the SignInApp integration."""

from datetime import timedelta

DOMAIN = "signinapp"
PLATFORMS = ["sensor"]

CONF_BASE_URL = "base_url"
CONF_CODE = "code"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCOUNT_ID = "account_id"
CONF_DEVICE_TRACKER = "device_tracker"
CONF_SITE_ID = "site_id"
CONF_AUTO_SITE = "auto_site"

UPDATE_INTERVAL = timedelta(seconds=30)

SERVICE_SIGN_IN = "sign_in"
SERVICE_SIGN_OUT = "sign_out"

DATA_COORDINATOR = "coordinator"
DATA_CLIENT = "client"
DATA_LISTENER = "listener"
DATA_ENTITY_MAP = "entity_map"
