import re
from datetime import datetime

from backend import filenames
from backend.filenames import product_slug, timestamped_model_filename


def test_product_slug_keeps_safe_ascii_product_tokens():
    assert product_slug("Neo65 Custom Keyboard") == "neo65_custom_keyboard"


def test_product_slug_preserves_korean_product_names():
    # 한글이 소실되면 한국 셀러가 생성 모델 파일을 제품명으로 식별할 수 없다(QA 06-05).
    assert product_slug("크림 베이지 65% 커스텀 키보드") == "크림_베이지_65_커스텀_키보드"
    assert product_slug("../../etc/passwd") == "etc_passwd"
    assert product_slug("!!!", fallback="desk_setup") == "desk_setup"


def test_timestamped_model_filename_orders_date_time_then_product():
    filename = timestamped_model_filename("Neo65 Custom Keyboard")

    assert re.fullmatch(r"\d{8}_\d{6}_neo65_custom_keyboard\.glb", filename)


def test_unique_timestamped_model_path_adds_counter_on_collision(tmp_path, monkeypatch):
    class FixedDatetime:
        @classmethod
        def now(cls):
            return datetime(2026, 6, 4, 12, 0, 0)

    monkeypatch.setattr(filenames, "datetime", FixedDatetime)

    first = filenames.unique_timestamped_model_path(tmp_path, "Neo65")
    first.write_bytes(b"glTF")

    second = filenames.unique_timestamped_model_path(tmp_path, "Neo65")

    assert second.name.startswith(first.stem)
    assert second.name.endswith("_2.glb")
