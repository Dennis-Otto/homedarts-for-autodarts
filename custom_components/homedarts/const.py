"""Constants for the Autodarts integration."""

from typing import Final

DOMAIN: Final = "homedarts"

# The languages of the integration: its translations and the texts of the cards,
# the words of the calendar, of the highlight gallery and of the voice packs, and
# the names of the games that a voice assistant understands.
LANGUAGES: Final = ("en", "de", "es", "fr", "nl")

DEFAULT_PORT: Final = 3180


def event_signal(entry_id: str) -> str:
    """The signal that carries the events of a board to its event entity."""
    return f"{DOMAIN}_{entry_id}_event"


# Config entry keys
CONF_BOARD_ID: Final = "board_id"
CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
# Major Board Manager version the entities were built for (1 classic, 2 headless).
CONF_API_GENERATION: Final = "api_generation"
# Board Manager version found without /api/system; it runs as Board Manager 1.
CONF_NO_SYSTEM_API: Final = "no_system_api"
# A dartboard without Autodarts: every dart is entered in Home Assistant.
CONF_MANUAL_BOARD: Final = "manual_board"
# The own training plans of a board, in its options.
CONF_PLANS: Final = "plans"
# The Bluetooth address of the Granboard whose darts a dartboard without Autodarts
# receives, see granboard.py.
CONF_GRANBOARD: Final = "granboard"

# Detection states around a start or stop; the cameras open or close meanwhile.
LIFECYCLE_STATUSES: Final = ("starting", "stopping", "stopped", "calibrating", "error")

# Autodarts' guide to the headless Board Manager 2, which replaces the app.
BOARD_MANAGER_2_URL: Final = (
    "https://docs.autodarts.com/getting-started/detection/headless-installation/"
)

# Lists boards on the same public network, as the Board Manager app does.
DISCOVERY_URL: Final = "https://discover.autodarts.com"

PLATFORMS: Final = [
    "sensor",
    "binary_sensor",
    "button",
    "switch",
    "select",
    "number",
    "text",
    "camera",
    "event",
    "update",
    "calendar",
    "time",
]

# Sensor keys — board
SENSOR_BOARD_EVENT: Final = "board_event"

# Sensor keys — detection
SENSOR_LAST_THROW: Final = "last_throw"
SENSOR_NUM_THROWS: Final = "num_throws"

# Data of the cloud link, which entries of version 2.1 and those of the integration
# under its former name may still hold; the link is gone, see decision 0025 in
# docs/decisions/.
CLOUD_KEYS: Final = ("token", "client_id", "local_only")
# Its sensors of the match data in the cloud, whose keys no other entity uses.
CLOUD_SENSORS: Final = (
    "board_status",
    "game_mode",
    "match_state",
    "round",
    "visit_score",
    "darts_thrown",
)
