"""Extract per-page text from a (text, non-scanned) PDF for the "Preguntar a un
PDF" RAG app.

Reads one PDF and writes a JSONL file: one JSON object per page
    {"page": <1-based>, "text": "<page text>"}

Emits, on stdout, the batchwork progress protocol so the Node side can show a
progress bar:
    PROGRESS:<current>:<total>:<message>
    WARN:<file>:<message>
    ERROR:<file>:<message>

The final line is a machine-readable summary the caller parses:
    RESULT:{"pages": N, "empty_pages": M, "chars": C}

Designed for very large documents (3000+ pages): pages are streamed to the
output file one at a time so peak memory stays flat.
"""

import argparse
import json
import sys
from pathlib import Path


def extract(pdf_path, out_path):
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path), strict=False)
    # Some producers encrypt with an empty owner password; try to open it.
    if getattr(reader, "is_encrypted", False):
        try:
            reader.decrypt("")
        except Exception:
            pass

    total = len(reader.pages)
    name = pdf_path.name
    empty_pages = 0
    total_chars = 0

    print(f"PROGRESS:0:{total}:Leyendo {name}", flush=True)

    with open(out_path, "w", encoding="utf-8") as out:
        for i in range(total):
            try:
                text = reader.pages[i].extract_text() or ""
            except Exception as e:
                text = ""
                print(f"WARN:{name}:No se pudo extraer la pagina {i + 1}: {e}", flush=True)

            # Normalise whitespace lightly (collapse runs of blank lines) while
            # keeping line breaks that carry meaning.
            text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
            if not text:
                empty_pages += 1
            total_chars += len(text)

            out.write(json.dumps({"page": i + 1, "text": text}, ensure_ascii=False))
            out.write("\n")

            # Report progress every few pages (and always on the last one).
            if (i + 1) % 5 == 0 or (i + 1) == total:
                print(f"PROGRESS:{i + 1}:{total}:Extrayendo texto ({i + 1}/{total})", flush=True)

    if total and empty_pages == total:
        print(f"WARN:{name}:El PDF no contiene texto extraible (parece escaneado; necesitaria OCR)", flush=True)
    elif empty_pages > total * 0.4:
        print(f"WARN:{name}:{empty_pages} de {total} paginas sin texto (puede tener paginas escaneadas)", flush=True)

    print("RESULT:" + json.dumps({"pages": total, "empty_pages": empty_pages, "chars": total_chars}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        extract(Path(args.input), Path(args.output))
    except Exception as e:  # noqa: BLE001
        print(f"ERROR:{Path(args.input).name}:{e}", flush=True)
        sys.exit(1)
