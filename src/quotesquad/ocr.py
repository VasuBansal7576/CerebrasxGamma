from __future__ import annotations

import shutil
import subprocess
import tempfile

from quotesquad.schemas import ProviderGap

IMAGE_SUFFIXES = frozenset((".jpg", ".jpeg", ".png", ".heic", ".webp"))


def extract_image_text(payload: bytes, suffix: str) -> tuple[str, tuple[ProviderGap, ...]]:
    tesseract = shutil.which("tesseract")
    if tesseract is None:
        return "", (_ocr_gap("Tesseract is not installed on this host."),)

    normalized = suffix if suffix in IMAGE_SUFFIXES else ".img"
    try:
        with tempfile.NamedTemporaryFile(suffix=normalized) as image_file:
            _ = image_file.write(payload)
            image_file.flush()
            completed = subprocess.run(  # noqa: S603
                [tesseract, image_file.name, "stdout"],
                capture_output=True,
                check=False,
                encoding="utf-8",
                timeout=15,
            )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", (_ocr_gap(f"Tesseract failed before producing output: {exc}"),)

    if completed.returncode != 0:
        detail = " ".join(completed.stderr.split()) or "Tesseract could not read image text."
        return "", (_ocr_gap(detail),)
    text = completed.stdout.strip()
    if not text:
        return "", (_ocr_gap("Tesseract did not find readable quote text in the image."),)
    return text, ()


def _ocr_gap(reason: str) -> ProviderGap:
    return ProviderGap(
        provider="ocr",
        reason=reason,
        blocks="Line-item extraction from photo uploads",
    )
