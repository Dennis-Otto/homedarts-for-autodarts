"""The live demo of the website: its recording plays every game to its end."""

import json
import os
from functools import partial
from pathlib import Path

from .demo_timeline import DEVICE, FORMAT, dump, record

TIMELINE = Path(__file__).parents[1] / "docs" / "demo" / "timeline.json"


def final(timeline: dict) -> dict[str, list]:
    """The states after the last step."""
    states: dict[str, list] = {}
    for step in timeline["steps"]:
        for entity, state in step["states"].items():
            if state is None:
                states.pop(entity, None)
            else:
                states[entity] = state
    return states


def by_key(timeline: dict, key: str) -> str:
    (found,) = [
        entity
        for entity, item in timeline["entities"].items()
        if f"{entity.split('.')[0]}.{item['translation_key']}" == key
    ]
    return found


async def test_the_demo_plays_every_game_to_its_end(hass, aioclient_mock, freezer):
    timeline = await record(hass, aioclient_mock, freezer)
    # scripts/record_demo.py runs this test to write the timeline of the website.
    text = dump(timeline)
    assert json.loads(text) == timeline
    assert timeline["format"] == FORMAT
    assert [chapter["key"] for chapter in timeline["chapters"]] == [
        "start",
        "x01",
        "cricket",
        "tournament",
    ]
    steps = timeline["steps"]
    moments = [step["at"] for step in steps]
    assert moments == sorted(moments) and moments[0] == 0
    # The first step holds every entity of the cards, the device's only.
    assert set(steps[0]["states"]) == set(timeline["entities"])
    assert {item["device_id"] for item in timeline["entities"].values()} == {DEVICE}
    assert timeline["device"]["name"] == "Dartboard"

    winners = []
    remaining = by_key(timeline, "sensor.practice_remaining")
    won = None
    for step in steps:
        if remaining not in step["states"]:
            continue
        game = step["states"][remaining][1]
        if game.get("winner") and not won:
            winners.append((game["game"], game["scores"][game["winner"] - 1]["name"]))
        won = game.get("winner")
    # Alex checks the 501 out against the bot and wins the Cricket; in the
    # tournament, the second player of each match checks the 101 out.
    assert winners == [
        (501, "Alex"),
        ("cricket", "Alex"),
        (101, "Robin"),
        (101, "Kim"),
        (101, "Kim"),
    ]
    tournament = final(timeline)[by_key(timeline, "sensor.tournament")]
    assert tournament[0] == "finished"
    assert tournament[1]["winner"] == "Kim"
    assert tournament[1]["matches_played"] == 3
    # The training card's positions come with the steps, for the session and players.
    answers = [step["positions"] for step in steps if "positions" in step]
    assert {player for answer in answers for player in answer} >= {"", "Alex", "Kim"}
    # With the aim model, as the aim map of the training card asks for it.
    assert all("aim" in found for answer in answers for found in answer.values())
    # Only a recording that passed every check above replaces the website's.
    if target := os.environ.get("DEMO_TIMELINE"):
        await hass.async_add_executor_job(
            partial(Path(target).write_text, text, encoding="utf-8", newline="\n")
        )


def test_the_website_has_a_recording_of_this_format():
    timeline = json.loads(TIMELINE.read_text(encoding="utf-8"))
    assert timeline["format"] == FORMAT
    assert [chapter["key"] for chapter in timeline["chapters"]][1:] == [
        "x01",
        "cricket",
        "tournament",
    ]
    assert set(timeline["steps"][0]["states"]) == set(timeline["entities"])
