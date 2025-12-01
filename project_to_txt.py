# project_to_txt.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Concatène tous les fichiers texte d'un projet dans un seul fichier .txt.

- Ajoute un en-tête clair avant chaque fichier :
    ===== FILE: chemin/vers/fichier.py =====
- Détecte (et ignore) les binaires et les très gros fichiers
- Ignore les dossiers lourds (.git, node_modules, build, etc.)
- Tolère les encodages (UTF-8 puis Latin-1 si besoin)
- Options CLI: --toc, --include, --exclude-dirs, --max-bytes

Usage minimal:
    python project_to_txt.py
    # -> parcourt le dossier du script et écrit ./local.txt

Usage avec options :
    python project_to_txt.py ./mon_projet export.txt --toc --max-bytes 2097152 \
      --include "py,js,ts,tsx,jsx,html,css,md,txt,yml,yaml,json,ini,cfg,conf,sql,sh" \
      --exclude-dirs ".git,node_modules,build,dist,.idea,.vscode,.venv,__pycache__"
"""

import argparse
import os
import sys
import datetime
import textwrap

DEFAULT_EXCLUDE_DIRS = {
    ".git", "target", "node_modules", "build", "dist", ".idea", ".vscode",
    ".venv", "__pycache__", ".mvn", ".gradle", ".pytest_cache",
    ".scannerwork", ".sonar", "coverage", "out", "jacoco-report"
}

DEFAULT_INCLUDE_EXT = {
    "py","js","ts","tsx","jsx","html","css",
    "md","markdown","txt","yml","yaml","json","xml","xsd",
    "properties","ini","cfg","conf","sql","sh","bash","ksh","bat",
    "groovy","kt","gradle","rb","go","c","cc","cpp","h","hpp","env","dockerfile","jenkinsfile"
}

SPECIAL_FILENAMES = {"dockerfile", "jenkinsfile"}  # sans extension mais utiles

def parse_args():
    p = argparse.ArgumentParser(
        description="Concatène tous les fichiers texte d'un projet en un seul .txt"
    )
    p.add_argument("root", nargs="?", default=None,
                   help="Racine à parcourir (défaut: dossier du script)")
    p.add_argument("output", nargs="?", default=None,
                   help="Fichier de sortie .txt (défaut: local.txt à côté du script)")
    p.add_argument("--max-bytes", type=int, default=1_000_000,
                   help="Taille max d'un fichier (défaut: 1 Mo)")
    p.add_argument("--include", type=str, default="",
                   help="Extensions à inclure, séparées par des virgules (ex: py,js,md)")
    p.add_argument("--exclude-dirs", type=str, default="",
                   help="Dossiers à exclure, séparés par des virgules")
    p.add_argument("--toc", action="store_true",
                   help="Ajoute une table des matières au début")
    return p.parse_args()

def looks_binary(path, sample_size=2048):
    try:
        with open(path, "rb") as f:
            chunk = f.read(sample_size)
        return b"\x00" in chunk
    except Exception:
        return True  # si doute, on évite

def read_text_safely(path, max_bytes):
    try:
        size = os.path.getsize(path)
        if size > max_bytes:
            return None, f"IGNORED (size {size} > {max_bytes} bytes)"
        if looks_binary(path):
            return None, "IGNORED (binary file)"
        with open(path, "rb") as f:
            data = f.read()
        try:
            return data.decode("utf-8"), None
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="replace"), "NOTE (decoded as latin-1 with replacements)"
    except Exception as e:
        return None, f"IGNORED (error reading: {e})"

def should_include(filename, include_exts):
    lower = filename.lower()
    if lower in SPECIAL_FILENAMES:
        return True
    if "." in lower:
        ext = lower.rsplit(".", 1)[-1]
        return ext in include_exts
    return False

def gather_files(root, include_exts, exclude_dirs):
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in sorted(dirnames) if d not in exclude_dirs]
        for fname in sorted(filenames):
            if should_include(fname, include_exts):
                files.append(os.path.join(dirpath, fname))
    return files

def write_header(out, root, files, add_toc):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    out.write("# TEXT EXPORT OF PROJECT\n")
    out.write(f"Root: {root}\n")
    out.write(f"Generated: {now}\n")
    out.write(f"Files found: {len(files)}\n")
    out.write("#" * 80 + "\n\n")
    if add_toc:
        out.write("TABLE OF CONTENTS\n")
        for i, fpath in enumerate(files, 1):
            rel = os.path.relpath(fpath, root)
            out.write(f"{i:04d}. {rel}\n")
        out.write("\n" + "#" * 80 + "\n\n")

def write_file_block(out, rel_path, text, note):
    sep = "-" * 80
    if text is None:
        out.write(f"===== FILE: {rel_path} ({note}) =====\n")
        out.write(sep + "\n\n")
        return
    out.write(f"===== FILE: {rel_path} =====\n")
    out.write(sep + "\n")
    wrapper = textwrap.TextWrapper(
        width=500, replace_whitespace=False, drop_whitespace=False,
        break_long_words=True, break_on_hyphens=False
    )
    for raw in text.splitlines():
        wrapped = wrapper.wrap(raw)
        out.write(("\n".join(wrapped) if wrapped else "") + "\n")
    out.write(sep + "\n")
    out.write(f"===== END FILE: {rel_path} =====\n\n")

def main():
    args = parse_args()
    script_dir = os.path.abspath(os.path.dirname(__file__))
    root = os.path.abspath(args.root or script_dir)
    output = os.path.abspath(args.output or os.path.join(script_dir, "local.txt"))

    if not os.path.isdir(root):
        print(f"ERROR: directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    include_exts = DEFAULT_INCLUDE_EXT.copy()
    if args.include.strip():
        include_exts = {x.strip().lower().lstrip(".") for x in args.include.split(",") if x.strip()}

    exclude_dirs = DEFAULT_EXCLUDE_DIRS.copy()
    if args.exclude_dirs.strip():
        exclude_dirs |= {x.strip() for x in args.exclude_dirs.split(",") if x.strip()}

    files = gather_files(root, include_exts, exclude_dirs)

    os.makedirs(os.path.dirname(output), exist_ok=True)
    written = 0
    with open(output, "w", encoding="utf-8", newline="\n") as out:
        write_header(out, root, files, args.toc)
        for f in files:
            rel = os.path.relpath(f, root)
            text, note = read_text_safely(f, args.max_bytes)
            write_file_block(out, rel, text, note)
            if text is not None:
                written += 1

    print(f"Export complete: {output}")
    print(f"Files successfully written: {written}/{len(files)}")

if __name__ == "__main__":
    main()
