import json

from image_renamer import DEFAULT_CONFIG, load_config


def test_load_config_recovers_from_empty_file(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("", encoding="utf-8")

    config = load_config(config_path)

    assert config.input_dir == DEFAULT_CONFIG["input_dir"]
    assert config.output_dir == DEFAULT_CONFIG["output_dir"]
    assert json.loads(config_path.read_text(encoding="utf-8"))["model_name"] == DEFAULT_CONFIG["model_name"]
