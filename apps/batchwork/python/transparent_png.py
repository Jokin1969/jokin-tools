import argparse
import sys
from pathlib import Path


def process(input_dir, output_dir, threshold):
    from PIL import Image

    supported = {'.png', '.jpg', '.jpeg'}
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() in supported]
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron imágenes PNG/JPG en el directorio", flush=True)
        return

    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        try:
            img = Image.open(fpath).convert('RGBA')
            pixels = img.load()
            width, height = img.size
            for y in range(height):
                for x in range(width):
                    r, g, b, a = pixels[x, y]
                    if r < threshold and g < threshold and b < threshold:
                        pixels[x, y] = (0, 0, 0, 255)
                    else:
                        pixels[x, y] = (255, 255, 255, 0)
            out_path = Path(output_dir) / (fpath.stem + '.png')
            img.save(out_path, 'PNG')
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--threshold', type=int, default=60)
    args = parser.parse_args()
    process(args.input, args.output, args.threshold)
