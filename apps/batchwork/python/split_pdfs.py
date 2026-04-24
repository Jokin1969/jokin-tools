import argparse
from pathlib import Path


def split_file(fpath, output_dir, mode, block_size):
    from pypdf import PdfWriter, PdfReader

    reader = PdfReader(str(fpath))
    total_pages = len(reader.pages)
    file_out_dir = Path(output_dir) / fpath.stem
    file_out_dir.mkdir(parents=True, exist_ok=True)

    if mode == 'pages':
        for i in range(total_pages):
            w = PdfWriter()
            w.add_page(reader.pages[i])
            with open(file_out_dir / f'p{i+1:02d}.pdf', 'wb') as f:
                w.write(f)

    elif mode == 'even-odd':
        odd_w = PdfWriter()
        even_w = PdfWriter()
        for i in range(total_pages):
            if (i + 1) % 2 == 1:
                odd_w.add_page(reader.pages[i])
            else:
                even_w.add_page(reader.pages[i])
        with open(file_out_dir / 'impares.pdf', 'wb') as f:
            odd_w.write(f)
        with open(file_out_dir / 'pares.pdf', 'wb') as f:
            even_w.write(f)

    else:  # blocks:<n>
        n = block_size
        block_num = 0
        for start in range(0, total_pages, n):
            block_num += 1
            end = min(start + n, total_pages)
            w = PdfWriter()
            for idx in range(start, end):
                w.add_page(reader.pages[idx])
            p_start = start + 1
            p_end = end
            if p_start == p_end:
                fname = f'bloque_{block_num:02d}_pp{p_start:02d}.pdf'
            else:
                fname = f'bloque_{block_num:02d}_pp{p_start:02d}-{p_end:02d}.pdf'
            with open(file_out_dir / fname, 'wb') as f:
                w.write(f)


def process(input_dir, output_dir, mode_arg):
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() == '.pdf']
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron ficheros PDF", flush=True)
        return

    # Parse mode
    if mode_arg.startswith('blocks:'):
        mode = 'blocks'
        block_size = int(mode_arg.split(':')[1])
    elif mode_arg == 'even-odd':
        mode = 'even-odd'
        block_size = 2
    else:
        mode = 'pages'
        block_size = 1

    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        try:
            split_file(fpath, output_dir, mode, block_size)
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', required=True)
    args = parser.parse_args()
    process(args.input, args.output, args.mode)
