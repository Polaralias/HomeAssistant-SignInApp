from datetime import timedelta

DOMAIN = "signinapp"
PLATFORMS = ["sensor"]

DEFAULT_BASE_URL = "https://backend.signinapp.com/api/mobile"

CONF_COMPANION_CODE = "companion_code"
CONF_TOKEN = "token"
CONF_DEVICE_TRACKER = "device_tracker"
CONF_OFFICE_SITE = "office_site_id"
CONF_REMOTE_SITE = "remote_site_id"
CONF_VISITOR_NAME = "visitor_name"
CONF_VISITOR_ID = "visitor_id"

SERVICE_SIGN_IN = "sign_in"
SERVICE_SIGN_OUT = "sign_out"
SERVICE_SIGN_IN_AUTO = "sign_in_auto"

DATA_CLIENT = "client"
DATA_COORDINATOR = "coordinator"
DATA_LISTENER = "listener"
DATA_ENTITY_MAP = "entity_map"

UPDATE_INTERVAL = timedelta(minutes=5)

ATTR_STATE = "state"
ATTR_CURRENT_SITE = "current_site"
ATTR_STATUS_NAME = "status_name"
ATTR_STATUS_COLOR = "status_color"
