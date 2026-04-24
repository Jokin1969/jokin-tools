import argparse
from pathlib import Path


def process(input_dir, output_dir):
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() == '.pdf']
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron ficheros .pdf en el directorio", flush=True)
        return

    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        try:
            from pdf2docx import Converter
            out_path = str(Path(output_dir) / (fpath.stem + '.docx'))
            cv = Converter(str(fpath))
            cv.convert(out_path)
            cv.close()
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    process(args.input, args.output)
