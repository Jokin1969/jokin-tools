import argparse
from pathlib import Path


def process(input_dir, output_file):
    from pypdf import PdfWriter, PdfReader

    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() == '.pdf']
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron ficheros PDF", flush=True)
        return

    writer = PdfWriter()

    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        try:
            reader = PdfReader(str(fpath))
            for page in reader.pages:
                writer.add_page(page)
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)

    with open(output_file, 'wb') as f:
        writer.write(f)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    process(args.input, args.output)
