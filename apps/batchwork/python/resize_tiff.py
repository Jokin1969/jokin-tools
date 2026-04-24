import argparse
import os
import io
from pathlib import Path


def process(input_dir, output_dir, max_mb):
    from PIL import Image

    supported = {'.tif', '.tiff'}
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() in supported]
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron ficheros TIFF en el directorio", flush=True)
        return

    max_bytes = max_mb * 1024 * 1024

    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        try:
            img = Image.open(fpath)
            img = img.convert(img.mode)  # ensure mutable copy

            # Set DPI to 300
            dpi = (300, 300)

            # Check size iteratively, reduce if needed
            scale = 1.0
            while True:
                if scale < 1.0:
                    new_w = max(1, int(img.width * scale))
                    new_h = max(1, int(img.height * scale))
                    resized = img.resize((new_w, new_h), Image.LANCZOS)
                else:
                    resized = img

                buf = io.BytesIO()
                resized.save(buf, format='TIFF', dpi=dpi, compression='tiff_lzw')
                if buf.tell() <= max_bytes or scale < 0.05:
                    break
                scale -= 0.05

            out_path = Path(output_dir) / fpath.name
            buf.seek(0)
            out_path.write_bytes(buf.read())

        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-mb', type=float, default=12.0)
    args = parser.parse_args()
    process(args.input, args.output, args.max_mb)
