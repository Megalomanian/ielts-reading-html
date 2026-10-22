#!/usr/bin/env python3
"""Prepare phone photos of an IELTS paper for reading/OCR.

- applies EXIF orientation
- optionally downscales to a maximum side
- normalizes to RGB JPEG with mild contrast
- creates a numbered contact sheet for page ordering
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageOps
except ImportError:  # pragma: no cover
    print("[ERROR] 需要 Pillow。请先运行：python -m pip install Pillow")
    raise SystemExit(2)

try:  # optional HEIC support
    import pillow_heif  # type: ignore

    pillow_heif.register_heif_opener()
except Exception:
    pass

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".heic", ".heif"}
SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def collect_images(inputs: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[Path] = set()
    for raw in inputs:
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            candidates = sorted(
                p for p in path.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_EXTS
                and not p.name.lower().startswith("contact-sheet")
            )
        elif path.is_file():
            candidates = [path]
        else:
            print(f"[WARN] 跳过不存在的路径：{path}")
            continue
        for candidate in candidates:
            if candidate.suffix.lower() not in IMAGE_EXTS:
                print(f"[WARN] 跳过非图片文件：{candidate}")
                continue
            key = candidate.resolve()
            if key in seen:
                print(f"[WARN] 跳过重复输入：{candidate}")
                continue
            seen.add(key)
            files.append(candidate)
    return files


def safe_stem(path: Path) -> str:
    stem = SAFE_RE.sub("-", path.stem).strip("-._")
    return stem or "page"


def load_font(size: int, bold: bool = False):
    candidates = []
    if sys.platform == "win32":
        candidates = [
            Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
            Path(r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf"),
        ]
    candidates += [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
    ]
    for candidate in candidates:
        try:
            if candidate.exists():
                return ImageFont.truetype(str(candidate), size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def to_rgb(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def prepare_one(
    source: Path,
    output: Path,
    max_side: int,
    quality: int,
) -> tuple[int, int, int, int]:
    with Image.open(source) as opened:
        image = ImageOps.exif_transpose(opened)
        image.load()
        original_size = image.size
        image = to_rgb(image)
        image = ImageOps.autocontrast(image, cutoff=1)
        if max_side > 0:
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        final_size = image.size
        output.parent.mkdir(parents=True, exist_ok=True)
        image.save(output, "JPEG", quality=quality, optimize=True, progressive=True)
    return original_size[0], original_size[1], final_size[0], final_size[1]


def make_contact_sheet(
    entries: list[tuple[int, Path, Path]],
    output: Path,
    columns: int = 4,
    cell_w: int = 300,
    cell_h: int = 420,
    gap: int = 16,
) -> None:
    if not entries:
        return
    columns = max(1, min(columns, len(entries)))
    rows = (len(entries) + columns - 1) // columns
    label_h = 42
    width = gap + columns * (cell_w + gap)
    height = gap + rows * (cell_h + label_h + gap)
    sheet = Image.new("RGB", (width, height), (242, 239, 231))
    draw = ImageDraw.Draw(sheet)
    font = load_font(15, bold=True)
    small = load_font(11)

    for index, (page_no, source, prepared) in enumerate(entries):
        row, col = divmod(index, columns)
        x = gap + col * (cell_w + gap)
        y = gap + row * (cell_h + label_h + gap)
        draw.rounded_rectangle(
            (x, y, x + cell_w, y + cell_h + label_h - 4),
            radius=8, fill=(255, 253, 248), outline=(227, 220, 207), width=1,
        )
        with Image.open(prepared) as opened:
            thumb = opened.convert("RGB")
            thumb.thumbnail((cell_w - 16, cell_h - 16), Image.Resampling.LANCZOS)
            thumb_x = x + (cell_w - thumb.width) // 2
            thumb_y = y + 8 + (cell_h - 8 - thumb.height) // 2
            sheet.paste(thumb, (thumb_x, thumb_y))
        label = f"P{page_no:02d}"
        draw.text((x + 10, y + cell_h + 2), label, fill=(15, 118, 110), font=font)
        name = source.name
        if len(name) > 30:
            name = name[:27] + "…"
        draw.text((x + 55, y + cell_h + 7), name, fill=(72, 84, 95), font=small)

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "JPEG", quality=88, optimize=True, progressive=True)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Prepare phone photos of an IELTS paper.")
    parser.add_argument("inputs", nargs="+", help="Image files or folders")
    parser.add_argument("--out", default="prepared", help="Output folder (default: prepared)")
    parser.add_argument("--max-side", type=int, default=2200, help="Max long side in px; 0 = no resize")
    parser.add_argument("--quality", type=int, default=88, help="JPEG quality 1-100")
    parser.add_argument("--no-contact-sheet", action="store_true", help="Do not create contact-sheet.jpg")
    parser.add_argument("--keep-names", action="store_true", help="Keep original file stems (default: page-001)")
    parser.add_argument("--columns", type=int, default=4, help="Contact sheet columns (default: 4)")
    args = parser.parse_args(argv)

    if not 1 <= args.quality <= 100:
        print("[ERROR] --quality 必须在 1-100 之间。")
        return 2
    if args.max_side < 0:
        print("[ERROR] --max-side 不能为负数。")
        return 2

    sources = collect_images(args.inputs)
    if not sources:
        print("[ERROR] 没有找到图片。支持：" + ", ".join(sorted(IMAGE_EXTS)))
        return 2

    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    entries: list[tuple[int, Path, Path]] = []
    failures = 0
    used_names: set[str] = set()

    for index, source in enumerate(sources, start=1):
        if args.keep_names:
            base = safe_stem(source)
            name = base
            counter = 2
            while name.lower() in used_names:
                name = f"{base}-{counter}"
                counter += 1
            filename = f"{name}.jpg"
        else:
            filename = f"page-{index:03d}.jpg"
        used_names.add(filename.lower())
        target = out_dir / filename
        if target.resolve() == source.resolve():
            target = out_dir / f"{target.stem}-prepared{target.suffix}"
            print(f"[WARN] 输出会覆盖原图，已改为：{target.name}")
        try:
            ow, oh, nw, nh = prepare_one(source, target, args.max_side, args.quality)
            entries.append((index, source, target))
            print(f"[{index:02d}] {source.name} -> {target.name}  {ow}x{oh} -> {nw}x{nh}")
        except Exception as exc:
            failures += 1
            print(f"[ERROR] {source.name}: {exc}")
            if source.suffix.lower() in {".heic", ".heif"}:
                print("        HEIC 需要 pillow-heif 或先在系统里导出为 JPEG。")

    if entries and not args.no_contact_sheet:
        contact = out_dir / "contact-sheet.jpg"
        try:
            make_contact_sheet(entries, contact, columns=args.columns)
            print(f"\n联系表：{contact}")
        except Exception as exc:
            print(f"[WARN] 联系表生成失败：{exc}")

    print(f"\n完成：{len(entries)} 张成功，{failures} 张失败。输出目录：{out_dir}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
