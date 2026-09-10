#!/usr/bin/env python3
"""
MCP Mod Deobfuscator

Decompiles every jar in a mods folder with Vineflower, then renames every
SRG-style identifier (field_NNN_x, func_NNN_x, p_NNN_N_) found in the
decompiled .java source using fields.csv/methods.csv/params.csv (MCP mapping
export). Finally splits the result into a standard Gradle source layout:
java package directories go to src/main/java, everything else (assets/,
mcmod.info, META-INF, pack.mcmeta, ...) goes to src/main/resources.

1.12.2 Forge mods are typically shipped SRG-named (not reobfuscated to notch)
because FML deobfuscates them against the vanilla jar at runtime - so no
bytecode remapping step is needed here, just decompile + textual rename.

Layout expected next to this script:
    vineflower.jar          - decompiler (needs Java 17+)
    jdk21/bin/java           - portable JDK used to run vineflower.jar
    mappings/fields.csv
    mappings/methods.csv
    mappings/params.csv

Usage:
    python3 deobfuscate_mods.py
    python3 deobfuscate_mods.py --only aquaculture
    python3 deobfuscate_mods.py --jobs 8
    python3 deobfuscate_mods.py --mods-dir /path/to/mods --out-dir /path/to/output
"""

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

TOOL_DIR = Path(__file__).parent
DEFAULT_MODS_DIR = Path("/home/nischi/minecraft/mods")
DEFAULT_OUT_DIR = TOOL_DIR / "output"
VINEFLOWER_JAR = TOOL_DIR / "vineflower.jar"
# Use system java (from PATH or JAVA_HOME)
JAVA_BIN = shutil.which("java") or Path(os.environ.get("JAVA_HOME", "")) / "bin" / "java"
MAPPINGS_DIR = TOOL_DIR / "mappings"

TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:field_[0-9]+_[A-Za-z0-9]+|func_[0-9]+_[A-Za-z0-9]+|p_[0-9]+_[0-9]+_)(?![A-Za-z0-9_])"
)


def load_mapping() -> dict:
    mapping = {}
    for filename, key_col in (("fields.csv", "searge"), ("methods.csv", "searge"), ("params.csv", "param")):
        path = MAPPINGS_DIR / filename
        if not path.exists():
            print(f"Error: mapping file not found: {path}")
            sys.exit(1)
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                name = row.get("name")
                if name:
                    mapping[row[key_col]] = name
    return mapping


def deobfuscate_text(text: str, mapping: dict) -> str:
    return TOKEN_RE.sub(lambda m: mapping.get(m.group(0), m.group(0)), text)


DECOMPILE_TIMEOUT_SECONDS = 20 * 60  # Vineflower can pathologically hang on certain jars (seen on
                                      # librarianlib: 5.5h+ spinning at 500%+ CPU, no progress) - a
                                      # single stuck jar must never block the rest of the batch.

# Whole third-party libraries some mods shade/bundle wholesale (Kotlin stdlib, fastutil, ...).
# These are never the mod's own code, dumping their source is pure noise, and their huge
# auto-generated classes (e.g. kotlin's ArraysKt___ArraysKt) are exactly what makes Vineflower
# hang or take hours on an otherwise-normal-sized mod (seen on librarianlib: 10k+ fastutil
# classes, 42MB, plus the full Kotlin stdlib). Strip them out before decompiling.
EXCLUDE_PATH_PREFIXES = ("kotlin/", "kotlinx/", "it/unimi/dsi/")
EXCLUDE_PATH_SEGMENTS = {"shade", "shaded"}


def is_excluded_class(class_path: str) -> bool:
    if class_path.startswith(EXCLUDE_PATH_PREFIXES):
        return True
    return any(part.lower() in EXCLUDE_PATH_SEGMENTS for part in class_path.split("/"))


def filter_jar(jar_path: Path, filtered_jar_path: Path, verbose: bool) -> int:
    """Copy jar_path to filtered_jar_path, dropping shaded third-party classes. Returns count dropped."""
    dropped = 0
    with zipfile.ZipFile(jar_path, "r") as src, zipfile.ZipFile(filtered_jar_path, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename.endswith(".class") and is_excluded_class(item.filename):
                dropped += 1
                continue
            dst.writestr(item, src.read(item.filename))
    if verbose and dropped:
        print(f"    filtered out {dropped} shaded third-party classes before decompiling")
    return dropped


def decompile(jar_path: Path, dest_dir: Path, verbose: bool) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            [str(JAVA_BIN), "-jar", str(VINEFLOWER_JAR), "--folder", str(jar_path), str(dest_dir)],
            capture_output=True,
            text=True,
            timeout=DECOMPILE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"    vineflower timed out after {DECOMPILE_TIMEOUT_SECONDS}s")
        return False
    if result.returncode != 0:
        if verbose:
            print(f"    vineflower failed:\n{result.stderr[-2000:]}")
        return False
    return True


def rename_identifiers(root: Path, mapping: dict) -> int:
    count = 0
    for java_file in root.rglob("*.java"):
        text = java_file.read_text(encoding="utf-8", errors="ignore")
        new_text = deobfuscate_text(text, mapping)
        if new_text != text:
            java_file.write_text(new_text, encoding="utf-8")
            count += 1
    return count


def split_source_layout(decompiled_root: Path, out_root: Path):
    java_dir = out_root / "src" / "main" / "java"
    resources_dir = out_root / "src" / "main" / "resources"
    java_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    for entry in decompiled_root.iterdir():
        is_java_source = entry.suffix == ".java" or (entry.is_dir() and any(entry.rglob("*.java")))
        target_root = java_dir if is_java_source else resources_dir
        shutil.move(str(entry), str(target_root / entry.name))


def is_already_done(out_root: Path) -> bool:
    marker = out_root / ".done"
    return marker.exists()


def process_jar(jar_path: Path, out_dir: Path, mapping: dict, verbose: bool, keep_raw: bool, force: bool) -> str:
    name = jar_path.stem
    out_root = out_dir / name

    if not force and is_already_done(out_root):
        return f"SKIP (already done): {name}"

    if out_root.exists():
        shutil.rmtree(out_root)

    with tempfile.TemporaryDirectory(prefix=f"mcpdeob-{name}-") as tmp:
        tmp_path = Path(tmp)
        decompiled_root = tmp_path / "decompiled"

        filtered_jar = tmp_path / "filtered.jar"
        dropped = filter_jar(jar_path, filtered_jar, verbose)
        decompile_input = filtered_jar if dropped else jar_path

        if not decompile(decompile_input, decompiled_root, verbose):
            return f"FAILED (decompile): {name}"

        if keep_raw:
            raw_copy = out_dir / "_raw" / name
            raw_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(decompiled_root, raw_copy, dirs_exist_ok=True)

        renamed = rename_identifiers(decompiled_root, mapping)
        out_root.mkdir(parents=True, exist_ok=True)
        split_source_layout(decompiled_root, out_root)

    (out_root / ".done").write_text("")
    return f"OK ({renamed} files renamed): {name}"


def main():
    parser = argparse.ArgumentParser(description="Decompile and MCP-deobfuscate all jars in a mods folder")
    parser.add_argument("--mods-dir", type=Path, default=DEFAULT_MODS_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--only", help="Only process jars whose filename contains this substring")
    parser.add_argument("--jobs", type=int, default=4, help="Parallel jar processing (default: 4)")
    parser.add_argument("--keep-raw", action="store_true", help="Keep pre-rename decompiled copy for debugging")
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess jars even if already marked done (default: skip them, for safe resume after interruption)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not JAVA_BIN or not Path(JAVA_BIN).exists():
        print(f"Error: java not found (checked PATH and JAVA_HOME)")
        sys.exit(1)
    if not VINEFLOWER_JAR.exists():
        print(f"Error: vineflower.jar not found at {VINEFLOWER_JAR}")
        sys.exit(1)

    print("Loading MCP mappings...")
    mapping = load_mapping()
    print(f"  {len(mapping)} identifiers loaded")

    jars = sorted(args.mods_dir.glob("*.jar"))
    if args.only:
        jars = [j for j in jars if args.only.lower() in j.name.lower()]
    if not jars:
        print("No matching jars found")
        sys.exit(1)

    print(f"Processing {len(jars)} jar(s) with {args.jobs} worker(s)...")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {
            pool.submit(process_jar, jar, args.out_dir, mapping, args.verbose, args.keep_raw, args.force): jar
            for jar in jars
        }
        for i, future in enumerate(as_completed(futures), 1):
            jar = futures[future]
            try:
                result = future.result()
            except Exception as e:
                result = f"FAILED (exception): {jar.stem}: {e}"
            print(f"[{i}/{len(jars)}] {result}")
            results.append(result)

    failed = [r for r in results if r.startswith("FAILED")]
    print()
    print(f"Done: {len(results) - len(failed)} ok, {len(failed)} failed")
    if failed:
        print("Failures:")
        for f in failed:
            print(f"  - {f}")


if __name__ == "__main__":
    main()
