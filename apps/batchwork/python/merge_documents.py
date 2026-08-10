"""Merge PDFs, Office documents (.docx, .doc, .odt, .rtf, .txt, .pptx, .ppt, .odp,
.xlsx, .xls, .ods) and images (.jpg, .png, .webp, .tif, .gif, .bmp) into a single
PDF, in alphabetical (natural) order of file name.

Each non-PDF is converted to PDF first:
  · Office documents → LibreOffice (headless).
  · Images → Pillow.
Then everything is concatenated with pypdf, in order. A file that fails to
convert or read is skipped with an ERROR line (the merge still completes with the
rest). Encrypted PDFs are transparently decrypted with qpdf when possible.

Emits the batchwork progress protocol on stdout (PROGRESS/WARN/ERROR).
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

OFFICE_EXTS = {'.docx', '.doc', '.odt', '.rtf', '.txt', '.pptx', '.ppt', '.odp',
               '.xlsx', '.xls', '.ods', '.csv'}
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff', '.gif', '.bmp'}


def natural_key(path):
    """Sort key so '2' comes before '10' (matches the file list in the UI)."""
    name = path.name.lower()
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', name)]


def office_to_pdf(fpath, tmpdir):
    """Convert an office document to PDF via LibreOffice. Returns the PDF path."""
    # A per-process user profile avoids lock clashes across repeated conversions.
    profile = f'-env:UserInstallation=file://{tmpdir}/loprofile'
    result = subprocess.run(
        ['libreoffice', profile, '--headless', '--convert-to', 'pdf', '--outdir', str(tmpdir), str(fpath)],
        capture_output=True, text=True, timeout=180
    )
    out = Path(tmpdir) / (fpath.stem + '.pdf')
    if not out.exists():
        raise RuntimeError(f'LibreOffice no generó el PDF: {result.stderr.strip()[:160]}')
    return out


def image_to_pdf(fpath, tmpdir, resolution):
    """Convert an image to a one-page PDF via Pillow. Returns the PDF path."""
    from PIL import Image

    img = Image.open(str(fpath))
    if img.mode in ('RGBA', 'LA', 'P'):
        # Flatten transparency onto white so the PDF page isn't black.
        img = img.convert('RGBA')
        bg = Image.new('RGB', img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    else:
        img = img.convert('RGB')
    out = Path(tmpdir) / (fpath.stem + '_img.pdf')
    img.save(str(out), 'PDF', resolution=float(resolution))
    return out


def read_pdf(fpath, tmpdir):
    """Return a PdfReader for fpath, decrypting with qpdf if needed."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(str(fpath))
        if getattr(reader, 'is_encrypted', False):
            try:
                reader.decrypt('')
            except Exception:
                pass
        _ = len(reader.pages)  # force parse so encryption errors surface here
        return reader
    except Exception:
        dec = Path(tmpdir) / (fpath.stem + '_dec.pdf')
        try:
            subprocess.run(['qpdf', '--decrypt', '--password=', str(fpath), str(dec)],
                           capture_output=True, timeout=120)
        except Exception:
            pass
        if dec.exists():
            return PdfReader(str(dec))
        raise


def to_pdf(fpath, tmpdir, resolution):
    """Return a PDF path for any supported input (converting if necessary)."""
    ext = fpath.suffix.lower()
    if ext == '.pdf':
        return fpath
    if ext in OFFICE_EXTS:
        return office_to_pdf(fpath, tmpdir)
    if ext in IMAGE_EXTS:
        return image_to_pdf(fpath, tmpdir, resolution)
    return None  # unsupported — skip


def process(input_dir, output_file, resolution):
    from pypdf import PdfWriter

    accepted = {'.pdf'} | OFFICE_EXTS | IMAGE_EXTS
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() in accepted],
        key=natural_key,
    )
    total = len(files)
    if total == 0:
        print('WARN::No se encontraron documentos admitidos (PDF, Office o imágenes)', flush=True)
        return

    writer = PdfWriter()
    added = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, fpath in enumerate(files, 1):
            print(f'PROGRESS:{i}:{total}:{fpath.name}', flush=True)
            try:
                pdf_path = to_pdf(fpath, tmpdir, resolution)
                if pdf_path is None:
                    print(f'WARN:{fpath.name}:Formato no admitido, se omite', flush=True)
                    continue
                reader = read_pdf(pdf_path, tmpdir)
                for page in reader.pages:
                    writer.add_page(page)
                added += 1
            except FileNotFoundError as e:
                # LibreOffice / qpdf missing.
                print(f'ERROR:{fpath.name}:Herramienta de conversión no disponible ({e})', flush=True)
            except Exception as e:  # noqa: BLE001
                print(f'ERROR:{fpath.name}:{e}', flush=True)

        if added == 0:
            print('WARN::No se pudo unir ningún documento', flush=True)
            return

        with open(output_file, 'wb') as f:
            writer.write(f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--resolution', default='150')
    args = parser.parse_args()
    try:
        process(args.input, args.output, args.resolution)
    except Exception as e:  # noqa: BLE001
        print(f'ERROR::{e}', flush=True)
        sys.exit(1)
