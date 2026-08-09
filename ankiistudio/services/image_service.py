from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


class ImageService:
    def __init__(self, images_dir: Path) -> None:
        self.images_dir = images_dir
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def optimize(
        self,
        raw: bytes,
        source_name: str,
        max_size: int = 900,
        *,
        flatten_transparency: bool = False,
    ) -> Path:
        processing_signature = b"flatten-alpha-v1" if flatten_transparency else b"preserve-alpha-v1"
        digest = hashlib.sha256(raw + processing_signature).hexdigest()[:16]
        safe_stem = "".join(ch if ch.isalnum() else "_" for ch in Path(source_name).stem)[:60]
        destination = self.images_dir / f"{safe_stem}_{digest}.webp"
        if destination.exists():
            return destination

        with Image.open(BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            has_alpha = "A" in image.getbands() or "transparency" in image.info
            if has_alpha:
                image = image.convert("RGBA")
            elif image.mode != "RGB":
                image = image.convert("RGB")

            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            if flatten_transparency and "A" in image.getbands():
                # Thumbnails rasterizadas de SVGs do Wikimedia podem ter RGB preto
                # em toda a tela e usar somente o alpha para desenhar o glifo. Se o
                # canal alpha for perdido no Anki/WebView, o resultado vira um bloco
                # preto. Compor explicitamente sobre branco produz um arquivo RGB
                # independente de transparência e consistente em temas claro/escuro.
                rgba = image.convert("RGBA")
                background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                background.alpha_composite(rgba)
                image = background.convert("RGB")

            save_kwargs = {"format": "WEBP", "quality": 85, "method": 6}
            image.save(destination, **save_kwargs)
        return destination

    @staticmethod
    def is_alpha_mask_artifact(path: Path) -> bool:
        """Detecta o artefato antigo: RGB totalmente preto + alpha variável."""
        try:
            with Image.open(path) as image:
                if "A" not in image.getbands():
                    return False
                rgba = image.convert("RGBA")
                red, green, blue, alpha = rgba.getextrema()
                return red == (0, 0) and green == (0, 0) and blue == (0, 0) and alpha[0] < alpha[1]
        except Exception:
            return False
