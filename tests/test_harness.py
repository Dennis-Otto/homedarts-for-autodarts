"""The test harness of Home Assistant, as the tests of the integration set it up."""

from pathlib import Path

ROOT = Path(__file__).parents[1]


async def test_each_test_writes_into_a_configuration_folder_of_its_own(
    hass, tmp_path, tmp_path_factory
):
    """The integration writes backups, media and blueprints into Home Assistant's
    configuration folder: in a test, an empty temporary folder of that test alone,
    never a folder of the repository, where they would pile up and show up in Git,
    and not the test's tmp_path, which the test fills itself."""
    config = Path(hass.config.config_dir)
    assert config.is_relative_to(tmp_path_factory.getbasetemp())
    assert config != tmp_path
    assert not config.is_relative_to(ROOT)
    assert hass.config.media_dirs == {"local": str(config / "media")}
