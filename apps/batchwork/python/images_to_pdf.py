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


def merge_pdfs(pdf_paths, output_file: Path):
    from pypdf import PdfWriter, PdfReader
    writer = PdfWriter()
    for p in pdf_paths:
        reader = PdfReader(str(p))
        for page in reader.pages:
            writer.add_page(page)
    with open(output_file, 'wb') as f:
        writer.write(f)


def process(input_dir: str, output_dir: str, resolution: int,
            mode: str, merged_name: str):
    files = sorted(
        [f for f in Path(input_dir).iterdir()
         if f.is_file() and f.suffix.lower() in SUPPORTED]
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron imágenes (PNG, JPG, SVG, TIFF) en el directorio", flush=True)
        return

    out_root = Path(output_dir)
    # En modo "merged" los PDFs intermedios se generan en un subdirectorio
    # temporal y se fusionan al final.
    if mode == 'merged':
        work_dir = out_root / '_parts_'
        work_dir.mkdir(exist_ok=True)
    else:
        work_dir = out_root

    generated = []
    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        ext = fpath.suffix.lower()
        out_path = work_dir / (fpath.stem + '.pdf')
        try:
            if ext in RASTER_EXTS:
                convert_raster(fpath, out_path, resolution)
            elif ext in VECTOR_EXTS:
                convert_svg(fpath, out_path)
            else:
                print(f"ERROR:{fpath.name}:Formato no soportado", flush=True)
                continue
            generated.append(out_path)
        except subprocess.TimeoutExpired:
            print(f"ERROR:{fpath.name}:Tiempo de conversión agotado", flush=True)
        except FileNotFoundError as e:
            print(f"ERROR:{fpath.name}:Herramienta no disponible ({e})", flush=True)
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)

    if mode == 'merged':
        if not generated:
            print("ERROR::No se pudo convertir ninguna imagen, no se genera el PDF unificado", flush=True)
            return
        # Ordenar por nombre original (case-insensitive) para conservar el
        # orden alfabético de los ficheros de entrada.
        generated.sort(key=lambda p: p.name.lower())
        final_name = (merged_name or 'imagenes.pdf').strip()
        if not final_name.lower().endswith('.pdf'):
            final_name += '.pdf'
        merged_out = out_root / final_name
        try:
            merge_pdfs(generated, merged_out)
            print(f"PROGRESS:{total}:{total}:Unificado en {final_name}", flush=True)
        except Exception as e:
            print(f"ERROR::Error al unir PDFs: {e}", flush=True)
        finally:
            # Limpieza de los PDFs intermedios
            for p in generated:
                try:
                    p.unlink()
                except Exception:
                    pass
            try:
                work_dir.rmdir()
            except Exception:
                pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--resolution', type=int, default=150,
                        help='DPI/resolución para imágenes ráster (PNG/JPG/TIFF)')
    parser.add_argument('--mode', choices=['independent', 'merged'],
                        default='independent',
                        help='independent: un PDF por imagen | merged: un único PDF')
    parser.add_argument('--merged-name', default='imagenes.pdf',
                        help='Nombre del PDF unificado (modo merged)')
    args = parser.parse_args()
    try:
        process(args.input, args.output, args.resolution,
                args.mode, args.merged_name)
    except Exception as e:
        print(f"ERROR::{e}", flush=True)
        sys.exit(1)
