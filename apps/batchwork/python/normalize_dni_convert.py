"""Convert a single file (DOCX or image) to PDF at the given output path."""
import argparse
import subprocess
import sys
from pathlib import Path


def convert(input_path, output_path):
    src = Path(input_path)
    ext = src.suffix.lower()

    if ext == '.docx':
        # Use LibreOffice for DOCX → PDF
        out_dir = Path(output_path).parent
        result = subprocess.run(
            ['libreoffice', '--headless', '--convert-to', 'pdf',
             '--outdir', str(out_dir), str(src)],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"LibreOffice error: {result.stderr.strip()[:200]}")
        # LibreOffice names the output after the stem
        generated = out_dir / (src.stem + '.pdf')
        if generated != Path(output_path):
            generated.rename(output_path)

    elif ext in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp', '.gif', '.webp'}:
        from PIL import Image
        img = Image.open(src)
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(str(output_path), 'PDF', resolution=150)

    else:
        raise RuntimeError(f"Tipo de fichero no soportado para conversión: {ext}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        convert(args.input, args.output)
    except Exception as e:
        print(f"ERROR:{Path(args.input).name}:{e}", flush=True)
        sys.exit(1)
