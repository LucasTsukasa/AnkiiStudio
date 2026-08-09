from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from ankiistudio.services.image_service import ImageService


def _alpha_only_black_png() -> bytes:
    image = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
    alpha = Image.new("L", image.size, 0)
    draw = ImageDraw.Draw(alpha)
    draw.line((20, 20, 100, 100), fill=255, width=14)
    image.putalpha(alpha)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_svg_thumbnail_alpha_is_flattened_over_white(tmp_path: Path) -> None:
    service = ImageService(tmp_path)
    path = service.optimize(
        _alpha_only_black_png(),
        "File:Kana.svg",
        flatten_transparency=True,
    )
    with Image.open(path) as result:
        assert result.mode == "RGB"
        rgb = result.convert("RGB")
        extrema = rgb.getextrema()
        # Há fundo branco e traço escuro; não é um retângulo preto uniforme.
        assert extrema[0][0] < 32 and extrema[0][1] > 240
        assert extrema[1][0] < 32 and extrema[1][1] > 240
        assert extrema[2][0] < 32 and extrema[2][1] > 240


def test_old_alpha_mask_webp_is_detected_as_artifact(tmp_path: Path) -> None:
    source = Image.open(BytesIO(_alpha_only_black_png()))
    path = tmp_path / "old.webp"
    source.save(path, format="WEBP", lossless=True)
    assert ImageService.is_alpha_mask_artifact(path) is True


def test_flattened_svg_uses_different_cache_key(tmp_path: Path) -> None:
    raw = _alpha_only_black_png()
    service = ImageService(tmp_path)
    preserved = service.optimize(raw, "File:Kana.svg", flatten_transparency=False)
    flattened = service.optimize(raw, "File:Kana.svg", flatten_transparency=True)
    assert preserved != flattened
