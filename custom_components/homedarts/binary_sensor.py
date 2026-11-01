"""Connectivity to the local manager, distinct from its cloud connection, and
to the Granboard of a dartboard without Autodarts."""

from functools import partial

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LIFECYCLE_STATUSES
from .entity import AutodartsBoardEntity, AutodartsLocalEntity, async_track_cameras
from .local_coordinator import AutodartsLocalCoordinator
from .manual_coordinator import AutodartsManualCoordinator
from .runtime import AutodartsConfigEntry
from .topics import Topic

PARALLEL_UPDATES = 0

# Motion flags of the detection; they change with nearly every dart and takeout.
MOTION_SENSORS = {
    "hand_detected": "isHand",
    "image_stable": "isStable",
    "takeout_partial": "isTakeoutPartial",
    "takeout_full": "isTakeoutFull",
}
# The live card shows a hand at the board and a takeout; the others are for
# diagnosis only and would just fill the recorder.
MOTION_DISABLED = ("image_stable", "takeout_full")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.local
    # The connection, the motion and the cameras of a board; a dartboard
    # without Autodarts has none of them.
    if isinstance(coordinator, AutodartsLocalCoordinator):
        async_add_entities(
            [AutodartsLocalConnectivity(coordinator)]
            + [
                AutodartsLocalState(coordinator, key)
                for key in (
                    *MOTION_SENSORS,
                    "cameras_active",
                    "calibrating",
                    "realtime_connected",
                    "camera_problem",
                    *(("cloud_link",) if coordinator.board_manager_2 else ()),
                )
            ]
        )
        async_track_cameras(
            entry,
            coordinator,
            partial(AutodartsLocalState, coordinator, "camera_problem"),
            async_add_entities,
        )
    # The Bluetooth connection of a Granboard.
    elif isinstance(coordinator, AutodartsManualCoordinator) and coordinator.granboard:
        async_add_entities([GranboardConnectivity(coordinator)])


class AutodartsLocalConnectivity(AutodartsBoardEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AutodartsLocalCoordinator) -> None:
        super().__init__(coordinator, "local_connected")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success


class GranboardConnectivity(
    AutodartsLocalEntity[AutodartsManualCoordinator], BinarySensorEntity
):
    """Whether the Granboard of a dartboard without Autodarts is connected."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: AutodartsManualCoordinator) -> None:
        super().__init__(coordinator, "granboard_connected")

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.granboard and self.coordinator.granboard.connected)


class AutodartsLocalState(AutodartsBoardEntity, BinarySensorEntity):
    def __init__(
        self,
        coordinator: AutodartsLocalCoordinator,
        key: str,
        index: int | None = None,
    ) -> None:
        super().__init__(
            coordinator, key if index is None else f"camera_{index}_problem"
        )
        self._key, self._index = key, index
        if key in MOTION_SENSORS:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
            self._attr_entity_registry_enabled_default = key not in MOTION_DISABLED
            self._topic = Topic.MOTION
        elif key == "camera_problem":
            self._attr_device_class = BinarySensorDeviceClass.PROBLEM
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif key in ("cameras_active", "calibrating"):
            self._attr_device_class = BinarySensorDeviceClass.RUNNING
            if key == "cameras_active":
                self._topic = Topic.CAMERA_STATE
        else:  # realtime_connected and cloud_link
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        if index is not None:
            self._attr_translation_key = "individual_camera_problem"
            self._attr_translation_placeholders = {"number": str(index + 1)}
            self._attr_extra_state_attributes = {"camera": index + 1}

    @property
    def available(self) -> bool:
        if self._key == "realtime_connected":
            return True
        return super().available and self.is_on is not None

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        state = data.get("local", {})
        if self._key in MOTION_SENSORS:
            if (
                state.get("running") is False
                or str(state.get("status", "")).lower() in LIFECYCLE_STATUSES
            ):
                return False
            readings = self.coordinator.readings
            motion = readings.get("motion", {}).get(MOTION_SENSORS[self._key])
            return motion if isinstance(motion, bool) else None
        if self._key == "cameras_active":
            running = self.coordinator.readings.get("camera_state", {}).get("isRunning")
            return running if isinstance(running, bool) else None
        if self._key == "calibrating":
            # Board Manager 2.1 also counts the cameras it calibrates.
            if (data.get("system") or {}).get("calibrating_cameras"):
                return True
            status = state.get("status")
            return status.lower() == "calibrating" if isinstance(status, str) else None
        if self._key == "realtime_connected":
            return self.coordinator.stream_connected
        if self._key == "cloud_link":
            link = (data.get("system") or {}).get("cloud_link")
            return link == "connected" if isinstance(link, str) else None
        problems = data.get("camera_problems", [])
        if self._index is not None:
            return problems[self._index] if self._index < len(problems) else None
        if any(problem is True for problem in problems):
            return True
        return (
            False
            if problems and all(problem is False for problem in problems)
            else None
        )
