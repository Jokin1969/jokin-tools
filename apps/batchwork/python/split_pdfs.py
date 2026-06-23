import argparse
from pathlib import Path


def _write_pages(reader, dest_file, indices):
    """Write the given page indices (0-based) into dest_file as one PDF."""
    from pypdf import PdfWriter

    w = PdfWriter()
    for idx in indices:
        w.add_page(reader.pages[idx])
    with open(dest_file, 'wb') as f:
        w.write(f)


def _block_ranges(total_pages, mode, block_size, pattern):
    """Return a list of (start, end) ranges (0-based, end exclusive) for the
    'blocks' and 'pattern' modes."""
    ranges = []
    if mode == 'pattern':
        # Cut sequentially using the given block sizes. The last size is clamped
        # to the remaining pages; if pages remain after the whole pattern, they
        # become one final block (nothing is lost).
        start = 0
        for size in (pattern or []):
            if start >= total_pages:
                break
            end = min(start + size, total_pages)
            ranges.append((start, end))
            start = end
        if start < total_pages:
            ranges.append((start, total_pages))
    else:  # blocks of fixed size
        n = max(1, block_size)
        for start in range(0, total_pages, n):
            ranges.append((start, min(start + n, total_pages)))
    return ranges


def split_file(fpath, output_dir, mode, block_size, pattern=None, grouping='byFile'):
    from pypdf import PdfReader

    reader = PdfReader(str(fpath))
    total_pages = len(reader.pages)
    stem = fpath.stem

    # Resolve the destination path according to the chosen grouping:
    #  - byFile  : output/<stem>/<byfile_name>           (a folder per source file)
    #  - byBlock : output/<block_label>/<stem>.pdf       (a folder per block; files
    #              keep their original name inside)
    def dest(block_label, byfile_name):
        if grouping == 'byBlock':
            d = Path(output_dir) / block_label
            name = f'{stem}.pdf'
        else:
            d = Path(output_dir) / stem
            name = byfile_name
        d.mkdir(parents=True, exist_ok=True)
        return d / name

    if mode == 'pages':
        for i in range(total_pages):
            _write_pages(reader, dest(f'pagina_{i+1:02d}', f'p{i+1:02d}.pdf'), [i])

    elif mode == 'even-odd':
        odds = [i for i in range(total_pages) if (i + 1) % 2 == 1]
        evens = [i for i in range(total_pages) if (i + 1) % 2 == 0]
        if odds:
            _write_pages(reader, dest('impares', 'impares.pdf'), odds)
        if evens:
            _write_pages(reader, dest('pares', 'pares.pdf'), evens)

    else:  # 'blocks' or 'pattern'
        ranges = _block_ranges(total_pages, mode, block_size, pattern)
        for num, (start, end) in enumerate(ranges, 1):
            p_start, p_end = start + 1, end
            if p_start == p_end:
                byfile_name = f'bloque_{num:02d}_pp{p_start:02d}.pdf'
            else:
                byfile_name = f'bloque_{num:02d}_pp{p_start:02d}-{p_end:02d}.pdf'
            _write_pages(reader, dest(f'bloque_{num:02d}', byfile_name), range(start, end))


def process(input_dir, output_dir, mode_arg, grouping='byFile'):
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() == '.pdf']
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron ficheros PDF", flush=True)
        return

    # Parse mode
    pattern = None
    if mode_arg.startswith('pattern:'):
        mode = 'pattern'
        block_size = 1
        pattern = [int(x) for x in mode_arg.split(':', 1)[1].split(',') if x.strip().isdigit() and int(x) > 0]
    elif mode_arg.startswith('blocks:'):
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
            split_file(fpath, output_dir, mode, block_size, pattern, grouping)
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', required=True)
    parser.add_argument('--grouping', default='byFile', choices=['byFile', 'byBlock'])
    args = parser.parse_args()
    process(args.input, args.output, args.mode, args.grouping)
