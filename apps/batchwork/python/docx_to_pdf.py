import argparse
import subprocess
import sys
from pathlib import Path


def process(input_dir, output_dir):
    files = sorted(
        [f for f in Path(input_dir).iterdir() if f.is_file() and f.suffix.lower() == '.docx']
    )
    total = len(files)

    if total == 0:
        print("WARN::No se encontraron ficheros .docx en el directorio", flush=True)
        return

    for i, fpath in enumerate(files, 1):
        print(f"PROGRESS:{i}:{total}:{fpath.name}", flush=True)
        try:
            result = subprocess.run(
                ['libreoffice', '--headless', '--convert-to', 'pdf', '--outdir', output_dir, str(fpath)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                print(f"ERROR:{fpath.name}:LibreOffice error: {result.stderr.strip()[:200]}", flush=True)
        except subprocess.TimeoutExpired:
            print(f"ERROR:{fpath.name}:Tiempo de conversión agotado", flush=True)
        except FileNotFoundError:
            print("ERROR::LibreOffice no está disponible en este entorno", flush=True)
            sys.exit(1)
        except Exception as e:
            print(f"ERROR:{fpath.name}:{e}", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    process(args.input, args.output)
