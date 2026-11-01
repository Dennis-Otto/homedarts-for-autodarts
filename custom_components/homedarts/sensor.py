"""Sensor platform for the Autodarts integration."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import SENSOR_BOARD_EVENT, SENSOR_LAST_THROW, SENSOR_NUM_THROWS
from .entity import (
    AutodartsBoardEntity,
    AutodartsLocalEntity,
    AutodartsStoredEntity,
    async_track_cameras,
    camera_count,
)
from .games_coordinator import AutodartsGamesCoordinator
from .local_coordinator import AutodartsLocalCoordinator
from .online import SENSOR_KEY as ONLINE_SENSOR_KEY
from .online import OnlineBridge
from .runtime import AutodartsConfigEntry
from .topics import Topic
from .tournament import STATES as TOURNAMENT_STATES
from .training import COUNTERS, DART_FLAGS

# Session values that can go down again, unlike the counters.
TRAINING_MEASUREMENTS = ("average", "highest_visit")
# Units match the live sensors: darts count darts, scores count points.
TRAINING_UNITS = {
    "darts": "darts",
    "triples": "darts",
    "doubles": "darts",
    "bulls": "darts",
    "misses": "darts",
    "points": "points",
    "average": "points",
    "highest_visit": "points",
    "visits": "visits",
    "scores_100": "visits",
    "scores_140": "visits",
    "scores_180": "visits",
}

PARALLEL_UPDATES = 0

# Board Manager detection states, translated in strings.json.
LOCAL_STATES = [
    "offline",
    "starting",
    "stopping",
    "stopped",
    "throw",
    "takeout",
    "takeout_in_progress",
    "calibrating",
    "error",
    # A dartboard without Autodarts, whose darts are entered by hand.
    "manual",
]

# ---------------------------------------------------------------------------
# Helpers to extract values from coordinator data
# ---------------------------------------------------------------------------
# coordinator.data = {"local": {...}, ...}, "local" with the board's state.


def _local(data: dict[str, Any]) -> dict[str, Any]:
    return data.get("local") or {}


# -- value extractors -------------------------------------------------------


def _text(value: Any) -> str | None:
    """Board text short enough for a state; Home Assistant stores 255 characters."""
    return value if isinstance(value, str) and 0 < len(value) <= 255 else None


def _get_board_event(data: dict[str, Any]) -> str | None:
    """Last event of the board's detection, else its status."""
    local = _local(data)
    return _text(local.get("event")) or _text(local.get("status"))


BEDS = frozenset(
    {"Single", "SingleInner", "SingleOuter", "Double", "Triple", "Outside"}
)
SEGMENT_KEYS = ("segment", "number", "multiplier", "bed")
# Camera jitter moves a dart by a millimetre or so from one reading to the next.
# In board radii, the double ring's 170 mm: 0.01 is about 1.7 mm.
JITTER = 0.01
# Darts that Home Assistant placed, entered or corrected by hand or thrown by the
# bot, are where they were put; no camera makes them jitter.
PLACED_FLAGS = ("manual", "corrected", "bot")


def _jitter(previous: dict[str, Any], dart: dict[str, Any]) -> bool:
    """Whether a camera's dart is the previous reading of the same dart, moved
    by jitter rather than to another spot."""
    return (
        all(previous.get(key) == dart[key] for key in SEGMENT_KEYS)
        and not any(
            item.get(flag) for item in (previous, dart) for flag in PLACED_FLAGS
        )
        and "x" in previous
        and "x" in dart
        and math.dist((previous["x"], previous["y"]), (dart["x"], dart["y"])) < JITTER
    )


def _dart(dart: Any) -> dict[str, Any] | None:
    """A dart's scoring segment and normalized board position for dashboards."""
    segment = dart.get("segment") if isinstance(dart, dict) else None
    if not isinstance(segment, dict):
        return None
    number, multiplier = segment.get("number"), segment.get("multiplier")
    if type(number) is not int or type(multiplier) is not int:
        return None
    # Only text can name a bed; a list or a dict would not even fit into a set.
    bed = segment.get("bed")
    result = {
        # Like any board text, short enough for the state of Last dart.
        "segment": _text(segment.get("name")),
        "number": number,
        "multiplier": multiplier,
        "score": number * multiplier,
        "bed": bed if isinstance(bed, str) and bed in BEDS else None,
    }
    coords = dart.get("coords")
    if isinstance(coords, dict) and all(
        type(coords.get(axis)) in (int, float) and math.isfinite(coords[axis])
        for axis in ("x", "y")
    ):
        # 1.0 is the outer edge of the double ring; y points to the 20.
        result["x"], result["y"] = round(coords["x"], 3), round(coords["y"], 3)
    # Darts corrected or entered by hand, the bot's, and the number of a dart
    # in the current visit.
    result.update({flag: True for flag in DART_FLAGS if dart.get(flag) is True})
    if type(dart.get("dart")) is int:
        result["dart"] = dart["dart"]
    return result


def _darts(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Valid darts of the current visit; malformed board data is ignored.

    The visit as Home Assistant knows it, with corrections, darts entered by
    hand and the bot's darts, once the board was followed.
    """
    throws = data["throws"] if "throws" in data else _local(data).get("throws")
    return list(filter(None, map(_dart, throws if isinstance(throws, list) else [])))


def _get_last_throw(data: dict[str, Any]) -> str | None:
    """Last detected throw segment name (e.g. T20, D16, S5, M2)."""
    darts = _darts(data)
    return darts[-1]["segment"] if darts else None


def _number(value: Any) -> int | float | None:
    """A board value a numeric sensor can show; anything else reads as unknown."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) else None


def _get_num_throws(data: dict[str, Any]) -> int | float | None:
    """Number of throws in the current turn (from local board, 0–3)."""
    return _number(_local(data).get("numThrows"))


# ---------------------------------------------------------------------------
# Sensor descriptions
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class AutodartsSensorEntityDescription(SensorEntityDescription):
    """Describe an Autodarts sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    # A frame rate or load of the board PC: value_fn reads the readings of
    # Topic.TELEMETRY instead of the data.
    telemetry: bool = False


# The darts and events of the board; a dartboard without Autodarts has only
# the last dart.
DART_SENSORS: tuple[AutodartsSensorEntityDescription, ...] = (
    AutodartsSensorEntityDescription(
        key=SENSOR_BOARD_EVENT,
        translation_key=SENSOR_BOARD_EVENT,
        # Last event repeats Detection status in the Board Manager's raw
        # English text with every dart: a diagnostic, off unless switched on.
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=_get_board_event,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_LAST_THROW,
        translation_key=SENSOR_LAST_THROW,
        value_fn=_get_last_throw,
    ),
    AutodartsSensorEntityDescription(
        key=SENSOR_NUM_THROWS,
        translation_key=SENSOR_NUM_THROWS,
        native_unit_of_measurement="darts",
        value_fn=_get_num_throws,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutodartsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Autodarts sensors from a config entry."""
    runtime = entry.runtime_data
    local = runtime.local
    entities: list[SensorEntity] = []
    entities.extend(
        (AutodartsTrainingDartsSensor if key == "darts" else AutodartsTrainingSensor)(
            local, key
        )
        for key in (*COUNTERS, *TRAINING_MEASUREMENTS, "started")
    )
    entities.append(AutodartsLastSessionSensor(local))
    entities.extend(
        AutodartsPracticeSensor(local, key)
        for key in ("remaining", "checkout", "target")
    )
    entities.extend(
        AutodartsPracticeStatistic(local, key) for key in PRACTICE_STATISTICS
    )
    # A dartboard without Autodarts detects nothing to correct.
    if not local.manual_board:
        entities.append(AutodartsCorrectionRate(local))
    entities.extend(
        (
            AutodartsPersonalBest(local),
            AutodartsDailyDarts(local),
            AutodartsStreak(local),
            AutodartsPlayerProfiles(local),
            AutodartsDoubles(local),
            AutodartsLastMatch(local),
            AutodartsWeeklyReport(local),
            AutodartsAchievements(local),
            AutodartsTournament(local),
        )
    )
    # Without a board, nothing counts the darts in it or reports its events.
    entities.extend(
        AutodartsLocalSensor(local, description)
        for description in DART_SENSORS
        if not local.manual_board or description.key == SENSOR_LAST_THROW
    )
    entities.extend(
        (
            AutodartsVisitSensor
            if description.key == "local_visit_score"
            else AutodartsLocalSensor
        )(local, description)
        for description in LOCAL_SENSORS
        if not description.telemetry
    )
    # Only a Board Manager reports its readings.
    if isinstance(local, AutodartsLocalCoordinator):
        if local.board_manager_2:
            entities.extend(
                AutodartsBoardSensor(local, description)
                for description in SYSTEM_SENSORS
            )
        entities.extend(
            AutodartsBoardSensor(local, description)
            for description in LOCAL_SENSORS
            if description.telemetry
        )
    if runtime.bridge:
        entities.append(AutodartsOnlineBridgeSensor(local, runtime.bridge))
    async_add_entities(entities)
    # A dartboard without Autodarts has no cameras.
    if isinstance(local, AutodartsLocalCoordinator):
        async_track_cameras(
            entry, local, partial(_camera_sensor, local), async_add_entities
        )


# ---------------------------------------------------------------------------
# Sensor entity classes
# ---------------------------------------------------------------------------


def _last_throw_score(data: dict[str, Any]) -> int | None:
    darts = _darts(data)
    return darts[-1]["score"] if darts else None


def _local_visit_score(data: dict[str, Any]) -> int:
    return sum(dart["score"] for dart in _darts(data))


def _local_status(data: dict[str, Any]) -> str | None:
    """Board Manager status as a translatable state; unknown ones read as unknown."""
    status = _local(data).get("status")
    if not isinstance(status, str):
        return None
    state = "_".join(status.lower().split())
    return state if state in LOCAL_STATES else None


def _camera_fps(data: dict[str, Any], index: int) -> float | None:
    fps = data.get("camera_stats", {}).get("fps")
    return _number(fps[index]) if isinstance(fps, list) and index < len(fps) else None


def _camera_sensor(
    coordinator: AutodartsLocalCoordinator, index: int
) -> AutodartsCameraSensor:
    """The frame rate of a camera, a sensor of each camera of the board."""
    return AutodartsCameraSensor(
        coordinator,
        index,
        AutodartsSensorEntityDescription(
            key=f"camera_{index}_fps",
            translation_key="camera_fps",
            translation_placeholders={"number": str(index + 1)},
            native_unit_of_measurement="fps",
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
            entity_registry_enabled_default=False,
            value_fn=partial(_camera_fps, index=index),
            telemetry=True,
        ),
    )


LOCAL_SENSORS = (
    AutodartsSensorEntityDescription(
        key="local_status",
        translation_key="local_status",
        device_class=SensorDeviceClass.ENUM,
        options=LOCAL_STATES,
        value_fn=_local_status,
    ),
    AutodartsSensorEntityDescription(
        key="last_throw_score",
        translation_key="last_throw_score",
        native_unit_of_measurement="points",
        value_fn=_last_throw_score,
    ),
    AutodartsSensorEntityDescription(
        key="local_visit_score",
        translation_key="local_visit_score",
        native_unit_of_measurement="points",
        value_fn=_local_visit_score,
    ),
    AutodartsSensorEntityDescription(
        key="detection_fps",
        translation_key="detection_fps",
        native_unit_of_measurement="fps",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _number(data.get("stats", {}).get("fps")),
        telemetry=True,
    ),
)


def _system(data: dict[str, Any], key: str) -> int | float | None:
    return _number((data.get("system") or {}).get(key))


# Host load reported by Board Manager 2.
def _host(data: dict[str, Any]) -> dict[str, Any]:
    host = data.get("board_pc")
    return host if isinstance(host, dict) else {}


def _operating_system(data: dict[str, Any]) -> str | None:
    """For example Debian 13, from the distribution or the plain system name."""
    host = _host(data)
    name = host.get("platform") or host.get("os")
    if not isinstance(name, str):
        return None
    version = host.get("platform_version")
    name = name[:1].upper() + name[1:]
    return f"{name} {version}" if isinstance(version, str) else name


SYSTEM_SENSORS = (
    AutodartsSensorEntityDescription(
        key="cpu_usage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
        # It changes with every read of the board: off unless wanted, like the
        # memory usage.
        entity_registry_enabled_default=False,
        value_fn=lambda data: _system(data, "cpu_percent"),
        telemetry=True,
    ),
    AutodartsSensorEntityDescription(
        key="memory_usage",
        translation_key="memory_usage",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.MEBIBYTES,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _system(data, "memory_bytes"),
        telemetry=True,
    ),
    AutodartsSensorEntityDescription(
        key="host_os",
        translation_key="host_os",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_operating_system,
        attr_fn=lambda data: {
            "kernel": _host(data).get("kernel"),
            "architecture": _host(data).get("architecture"),
        },
    ),
    AutodartsSensorEntityDescription(
        key="host_processor",
        translation_key="host_processor",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _host(data).get("cpu_model"),
        attr_fn=lambda data: {"cores": _host(data).get("cpu_cores")},
    ),
    AutodartsSensorEntityDescription(
        key="vision_version",
        translation_key="vision_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: _host(data).get("vision_version"),
        attr_fn=lambda data: {"opencv_version": _host(data).get("opencv_version")},
    ),
)


class AutodartsLocalSensor[
    CoordinatorT: AutodartsGamesCoordinator = AutodartsGamesCoordinator
](AutodartsLocalEntity[CoordinatorT], SensorEntity):
    entity_description: AutodartsSensorEntityDescription

    def __init__(
        self,
        coordinator: CoordinatorT,
        description: AutodartsSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_translation_key = description.translation_key

    def _values(self) -> dict[str, Any]:
        """The data that the value and the attributes are read from."""
        return self.coordinator.data or {}

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._values())

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        if attr_fn := self.entity_description.attr_fn:
            return attr_fn(self._values())
        # Such as the camera number of a camera's sensor.
        return super().extra_state_attributes


class AutodartsBoardSensor(
    AutodartsBoardEntity, AutodartsLocalSensor[AutodartsLocalCoordinator]
):
    """A sensor of the Board Manager, such as a frame rate, the load or the host."""

    def __init__(
        self,
        coordinator: AutodartsLocalCoordinator,
        description: AutodartsSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)
        if description.telemetry:
            # Updated by every poll, without the other entities of the board.
            self._topic = Topic.TELEMETRY

    def _values(self) -> dict[str, Any]:
        """The readings for a frame rate or the load, otherwise the data."""
        if self.entity_description.telemetry:
            return self.coordinator.readings
        return super()._values()


class AutodartsCameraSensor(AutodartsBoardSensor):
    """A per-camera value; the camera number lets cards group its entities."""

    def __init__(
        self,
        coordinator: AutodartsLocalCoordinator,
        index: int,
        description: AutodartsSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)
        self._attr_extra_state_attributes = {"camera": index + 1}
        self._index = index

    @property
    def available(self) -> bool:
        """Like the camera, unavailable once the board has fewer cameras."""
        return super().available and self._index < camera_count(self.coordinator)


class AutodartsVisitSensor(AutodartsLocalSensor):
    """The detected visit, with each dart's segment and position for cards."""

    # Live positions and recent visits are for display only and must not grow
    # the recorder database.
    _unrecorded_attributes = frozenset({"throws", "recent_visits"})

    def __init__(
        self,
        coordinator: AutodartsGamesCoordinator,
        description: AutodartsSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description)
        self._throws: list[dict[str, Any]] = []
        self._update_throws()

    def _update_throws(self) -> None:
        throws: list[dict[str, Any]] = []
        for dart in _darts(self.coordinator.data or {}):
            previous = (
                self._throws[len(throws)] if len(throws) < len(self._throws) else {}
            )
            if _jitter(previous, dart):
                # Camera jitter moves an unchanged dart slightly; keep it steady.
                # A dart moved in its bed, or the dart after one the board took
                # back, is drawn where it is now.
                dart |= {"x": previous["x"], "y": previous["y"]}
            throws.append(dart)
        self._throws = throws

    @callback
    def _handle_coordinator_update(self) -> None:
        self._update_throws()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "throws": self._throws,
            # Copies: a stored state must not change with the next visit.
            "recent_visits": [
                dict(visit) for visit in self.coordinator.games.training.recent_visits
            ],
        }


class AutodartsTrainingSensor(AutodartsStoredEntity, SensorEntity):
    """Locally stored session totals remain readable while the board is offline."""

    def __init__(self, coordinator: AutodartsGamesCoordinator, key: str) -> None:
        super().__init__(coordinator, f"training_{key}")
        self._key = key
        self._attr_native_unit_of_measurement = TRAINING_UNITS.get(key)
        if key == "started":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
        elif key in TRAINING_MEASUREMENTS:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            if key == "average":
                self._attr_suggested_display_precision = 1
        else:
            # Totals of the session, which starts them from zero. A correction
            # or an undone visit takes points and darts back, so they can
            # also go down.
            self._attr_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        if self.state_class is not SensorStateClass.TOTAL:
            return None
        return dt_util.parse_datetime(self.coordinator.games.training.started)

    def _session(self) -> dict[str, Any]:
        """The snapshot the coordinator published; computed only before the first."""
        session = (self.coordinator.data or {}).get("training")
        if isinstance(session, dict):
            return session
        return self.coordinator.games.training.snapshot()

    @property
    def native_value(self) -> datetime | float | int | None:
        session = self._session()
        if self._key == "started":
            return dt_util.parse_datetime(session["started"])
        if self._key == "average":
            # Points per three darts, as darts players compare their level.
            darts = session["darts"]
            return round(session["points"] / darts * 3, 2) if darts else None
        return int(session[self._key])


class AutodartsTrainingDartsSensor(AutodartsTrainingSensor):
    """Darts of the session, with hits per bed for heatmaps and the summary of
    the training report in the language of Home Assistant."""

    # The breakdown is for cards and the summary for the training report, which
    # reads it when it runs; long-term history only needs the total.
    _unrecorded_attributes = frozenset({"hits", "summary"})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        session = self._session()
        attributes: dict[str, Any] = {"hits": session["hits"]}
        # Home Assistant translates no blueprint, and no board event starts the
        # report; without the words, the blueprint says its own.
        if summary := self.coordinator.caller.training(session):
            attributes["summary"] = summary
        return attributes


class AutodartsLastSessionSensor(AutodartsStoredEntity, SensorEntity):
    """The 3-dart average of the last finished session, one value per session.

    Its history shows the progress from session to session; the attributes
    hold the details and the recent sessions for cards.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "points"
    _attr_suggested_display_precision = 1
    # The session list is for cards; the recorder keeps one value per session.
    _unrecorded_attributes = frozenset({"sessions"})

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "training_last_session")

    @property
    def native_value(self) -> float | None:
        history = self.coordinator.games.training.history
        return history[0]["average"] if history else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        history = [dict(summary) for summary in self.coordinator.games.training.history]
        last = history[0] if history else {}
        return {
            **{key: value for key, value in last.items() if key != "average"},
            "sessions": history,
        }


class AutodartsPracticeSensor(AutodartsStoredEntity, SensorEntity):
    """Remaining score and checkout of X01, the target of Cricket or a training game."""

    # Darts, scores, results and the match summary are for cards; the
    # recorder keeps the state.
    _unrecorded_attributes = frozenset(
        {"visit", "legs", "scores", "results", "summary", "plan", "plan_of_the_day"}
    )

    def __init__(self, coordinator: AutodartsGamesCoordinator, key: str) -> None:
        super().__init__(coordinator, f"practice_{key}")
        self._key = key

    def _game(self) -> dict[str, Any]:
        """The snapshot the coordinator published; computed only before the first."""
        game = (self.coordinator.data or {}).get("practice")
        return (
            game
            if isinstance(game, dict)
            else self.coordinator.games.practice.snapshot()
        )

    @property
    def native_value(self) -> int | str | None:
        game = self._game()
        if self._key == "target":
            return (game["drill"] or {}).get("target") or game.get("target")
        return game.get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        game = self._game()
        if self._key == "target":
            drill = game["drill"] or {}
            return {key: value for key, value in drill.items() if key != "target"}
        if self._key != "remaining":
            return None
        return {
            key: value
            for key, value in game.items()
            if key not in ("remaining", "drill")
        }


# Practice statistic -> unit; an undone visit that won a leg takes it back.
PRACTICE_STATISTICS = {
    "first_9_average": "points",
    "checkout_rate": PERCENTAGE,
    "doubles_rate": PERCENTAGE,
    "legs_played": None,
}


class AutodartsPracticeStatistic(AutodartsStoredEntity, SensorEntity):
    """First-9 average, checkout and doubles rate of the last ten legs."""

    def __init__(self, coordinator: AutodartsGamesCoordinator, key: str) -> None:
        super().__init__(coordinator, f"practice_{key}")
        self._key = key
        self._attr_native_unit_of_measurement = PRACTICE_STATISTICS[key]
        if key == "legs_played":
            self._attr_state_class = SensorStateClass.TOTAL
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | int | None:
        statistics = self.coordinator.games.practice.statistics()
        value: float | int | None = statistics[self._key]
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self._key == "legs_played":
            return None
        statistics = self.coordinator.games.practice.statistics()
        return {
            "legs_counted": statistics["legs_counted"],
            "darts_at_double": statistics["darts_at_double"],
        }


class RevisionCache:
    """Attributes worked out once per change of the training and games.

    The coordinator raises its revision with every change of the practice
    game, the profiles and the progress; the date changes trends and streaks.
    """

    def __init__(self) -> None:
        self._key: tuple[object, ...] | None = None
        self._value: dict[str, Any] = {}

    def get(
        self,
        coordinator: AutodartsGamesCoordinator,
        compute: Callable[[], dict[str, Any]],
        *changes: object,
    ) -> dict[str, Any]:
        """The attributes, worked out anew with the revision, the date or any of
        the further changes."""
        key = ((coordinator.data or {}).get("revision"), dt_util.now().date(), *changes)
        if key != self._key:
            self._key, self._value = key, compute()
        return self._value


class AutodartsRecordsEntity(AutodartsStoredEntity, SensorEntity):
    """Personal bests, darts per day and the streak; kept across restarts."""

    def _records(self) -> dict[str, Any]:
        return self.coordinator.games.records.snapshot(dt_util.now().date())


class AutodartsPersonalBest(AutodartsRecordsEntity):
    """When the last personal best fell, with every best value as attributes."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "personal_best")

    @property
    def native_value(self) -> datetime | None:
        latest = self._records()["latest"]
        return dt_util.parse_datetime(latest["date"]) if latest else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        records = self._records()
        latest = records["latest"] or {}
        return {
            **{key: latest.get(key) for key in ("record", "value", "previous", "name")},
            **records["bests"],
        }


class AutodartsDailyDarts(AutodartsRecordsEntity):
    """Darts detected today, towards the daily goal."""

    _attr_native_unit_of_measurement = "darts"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "darts_today")

    @property
    def native_value(self) -> int:
        value: int = self._records()["darts_today"]
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        records = self._records()
        return {key: records[key] for key in ("goal", "goal_reached", "progress")}


class AutodartsStreak(AutodartsRecordsEntity):
    """Days in a row with at least one dart; today does not break it yet."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "training_streak")

    @property
    def native_value(self) -> int:
        value: int = self._records()["streak"]
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        records = self._records()
        return {
            key: records[key] for key in ("best_streak", "trained_today", "last_day")
        }


class AutodartsPlayerProfiles(AutodartsStoredEntity, SensorEntity):
    """Named players with their statistics and personal bests."""

    _unrecorded_attributes = frozenset({"players"})
    _attr_native_unit_of_measurement = "players"

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "player_profiles")
        self._cache = RevisionCache()

    @property
    def native_value(self) -> int:
        return len(self.coordinator.games.practice.profiles.players)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # The best aims follow a visit, once they are worked out.
        return self._cache.get(
            self.coordinator, self._players, self.coordinator.aim_revision
        )

    def _players(self) -> dict[str, Any]:
        # Each profile with the player's progress: trend, hits and grouping.
        games, today = self.coordinator.games, dt_util.now().date()
        profiles = games.practice.profiles.snapshot()["players"]
        return {
            "players": [
                {**profile, **games.progress.summary(profile["name"], today)}
                for profile in profiles
            ]
        }


class AutodartsDoubles(AutodartsStoredEntity, SensorEntity):
    """The double hit best, with the hit rate of every double and how often every
    double was hit by any dart."""

    _unrecorded_attributes = frozenset({"doubles", "landed"})

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "favourite_double")

    @property
    def native_value(self) -> str | None:
        doubles = self.coordinator.games.practice.doubles.snapshot()
        value: str | None = doubles["favourite"]
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        practice = self.coordinator.games.practice
        snapshot = practice.doubles.snapshot()
        return {
            **{key: snapshot[key] for key in ("attempts", "hits", "rate", "doubles")},
            "landed": practice.double_hits.snapshot(),
        }


class AutodartsLastMatch(AutodartsStoredEntity, SensorEntity):
    """When the last match of several players ended, with the recent matches."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _unrecorded_attributes = frozenset({"matches", "head_to_head"})

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "last_match")
        self._cache = RevisionCache()

    @property
    def native_value(self) -> datetime | None:
        matches = self.coordinator.games.practice.profiles.matches
        return dt_util.parse_datetime(matches[0]["ended"]) if matches else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._cache.get(self.coordinator, self._matches)

    def _matches(self) -> dict[str, Any]:
        snapshot = self.coordinator.games.practice.profiles.snapshot()
        last = snapshot["matches"][0] if snapshot["matches"] else {}
        winner = last.get("winner")
        players = last.get("players", [])
        return {
            "game": last.get("game"),
            "winner": players[winner - 1].get("name")
            if isinstance(winner, int) and 0 < winner <= len(players)
            else None,
            "matches": snapshot["matches"],
            "head_to_head": snapshot["head_to_head"],
        }


class AutodartsTournament(AutodartsStoredEntity, SensorEntity):
    """The stage of the tournament, with its matches and its tables or brackets."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = TOURNAMENT_STATES
    # The matches, the tables and the brackets are for cards; the recorder keeps
    # the stage and the players.
    _unrecorded_attributes = frozenset(
        {
            "fixtures",
            "standings",
            "groups",
            "bracket",
            "losers_bracket",
            "current",
            "next",
            "next_ready",
            "last_result",
            "boards",
            "ends_at",
        }
    )

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "tournament")

    @property
    def native_value(self) -> str:
        return self.coordinator.games.tournament_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # A board of a tournament on several boards shows it with its own match.
        return self.coordinator.games.tournament_snapshot()


class AutodartsCorrectionRate(AutodartsLocalEntity, SensorEntity):
    """Share of the last hundred darts that the board corrected."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "correction_rate")

    @property
    def native_value(self) -> float | None:
        return self.coordinator.games.quality.rate

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        quality = self.coordinator.games.quality.snapshot()
        return {"darts": quality["darts"], "corrected": quality["corrected"]}


class AutodartsOnlineBridgeSensor(AutodartsStoredEntity, RestoreEntity, SensorEntity):
    """When the last moment of an online match arrived, to check the bridge."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: AutodartsGamesCoordinator, bridge: OnlineBridge
    ) -> None:
        super().__init__(coordinator, ONLINE_SENSOR_KEY)
        self._bridge = bridge

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if last := await self.async_get_last_state():
            self._bridge.restore(
                dt_util.parse_datetime(last.state),
                last.attributes.get("trigger"),
                last.attributes.get("event_type"),
            )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._bridge.signal, self.async_write_ha_state
            )
        )

    @property
    def native_value(self) -> datetime | None:
        return self._bridge.last_event

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "trigger": self._bridge.last_trigger,
            "event_type": self._bridge.last_event_type,
        }


class AutodartsWeeklyReport(AutodartsStoredEntity, SensorEntity):
    """Darts of the running report week, with the week so far and the last report."""

    _attr_native_unit_of_measurement = "darts"
    # A new week starts from zero; an undone visit can take a dart back.
    _attr_state_class = SensorStateClass.TOTAL
    _unrecorded_attributes = frozenset({"personal_bests", "last_week"})

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "weekly_report")

    @property
    def last_reset(self) -> datetime | None:
        return self.coordinator.reports.report.started

    @property
    def native_value(self) -> int:
        return self.coordinator.reports.report.counts["darts"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        snapshot = self.coordinator.reports.snapshot()
        return {key: value for key, value in snapshot.items() if key != "darts"}


class AutodartsAchievements(AutodartsStoredEntity, SensorEntity):
    """Achievements unlocked by all players, with every player's badges."""

    _attr_native_unit_of_measurement = "badges"
    _unrecorded_attributes = frozenset({"catalogue", "players"})

    def __init__(self, coordinator: AutodartsGamesCoordinator) -> None:
        super().__init__(coordinator, "achievements")
        self._cache = RevisionCache()

    def _achievements(self) -> dict[str, Any]:
        """Worked out once for the state and the attributes of each change."""
        return self._cache.get(
            self.coordinator,
            lambda: self.coordinator.games.progress.achievements(
                self.coordinator.games.practice.profiles
            ),
        )

    @property
    def native_value(self) -> int:
        return sum(player["unlocked"] for player in self._achievements()["players"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._achievements()
