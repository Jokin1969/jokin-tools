"""Convert a batch of image files (PNG, JPG/JPEG, SVG, TIFF) to PDF.

PNG / JPG / TIFF se convierten con Pillow. SVG se convierte con svglib +
reportlab (puro Python). Si svglib no está disponible se intenta el
fallback con LibreOffice headless.
"""
import argparse
import subprocess
import sys
from pathlib import Path


RASTER_EXTS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff'}
VECTOR_EXTS = {'.svg'}
SUPPORTED = RASTER_EXTS | VECTOR_EXTS


def convert_raster(src: Path, dst: Path, resolution: int):
    from PIL import Image
    img = Image.open(src)

    # Multipágina (TIFF puede tener varias páginas)
    frames = []
    try:
        n = getattr(img, 'n_frames', 1)
    except Exception:
        n = 1

    for i in range(n):
        try:
            img.seek(i)
        except EOFError:
            break
        frame = img.copy()
        if frame.mode in ('RGBA', 'LA', 'P'):
            frame = frame.convert('RGB')
        elif frame.mode == '1':
            frame = frame.convert('RGB')
        frames.append(frame)

    if not frames:
        raise RuntimeError("La imagen no contiene fotogramas")

    first, rest = frames[0], frames[1:]
    save_kwargs = {'format': 'PDF', 'resolution': float(resolution)}
    if rest:
        save_kwargs['save_all'] = True
        save_kwargs['append_images'] = rest
    first.save(str(dst), **save_kwargs)


def convert_svg(src: Path, dst: Path):
    # Vía principal: svglib + reportlab (puro Python, fiable)
    try:
        from svglib.svglib import svg2rlg
        from reportlab.graphics import renderPDF
        drawing = svg2rlg(str(src))
        if drawing is None:
            raise RuntimeError("svglib no pudo leer el SVG")
        renderPDF.drawToFile(drawing, str(dst))
        return
    except ImportError:
        pass  # caer al fallback de LibreOffice

    out_dir = dst.parent
    result = subprocess.run(
        ['libreoffice', '--headless', '--convert-to', 'pdf',
         '--outdir', str(out_dir), str(src)],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice error: {result.stderr.strip()[:200]}")
    generated = out_dir / (src.stem + '.pdf')
    if not generated.exists():
        raise RuntimeError("LibreOffice no produjo el PDF esperado")
    if generated != dst:
        if dst.exists():
            dst.unlink()
        generated.rename(dst)


def process(input_dir: str, output_dir: str, resolution: int):
    files = sorted(
        [f for f in Path(input_dir).iterdir()
         if f.is_file() and f.suffix.lower() in SUPPORTED]
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron imágenes (PNG, JPG, SVG, TIFF) en el directorio", flush=True)
        return

    out_root = Path(output_dir)
    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        ext = fpath.suffix.lower()
        out_path = out_root / (fpath.stem + '.pdf')
        try:
            if ext in RASTER_EXTS:
                convert_raster(fpath, out_path, resolution)
            elif ext in VECTOR_EXTS:
                convert_svg(fpath, out_path)
            else:
                print(f"ERROR:{fpath.name}:Formato no soportado", flush=True)
        except subprocess.TimeoutExpired:
            print(f"ERROR:{fpath.name}:Tiempo de conversión agotado", flush=True)
        except FileNotFoundError as e:
            print(f"ERROR:{fpath.name}:Herramienta no disponible ({e})", flush=True)
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--resolution', type=int, default=150,
                        help='DPI/resolución para imágenes ráster (PNG/JPG/TIFF)')
    args = parser.parse_args()
    try:
        process(args.input, args.output, args.resolution)
    except Exception as e:
        print(f"ERROR::{e}", flush=True)
        sys.exit(1)
