import os
import filecmp
from pathlib import Path

MORNING_DIR = Path(r"C:\Silent-Couple-Bot\image\morning")
EVENING_DIR = Path(r"C:\Silent-Couple-Bot\image\evening")
IMG_EXT = {'.jpg','.jpeg','.png','.bmp','.tiff','.tif','.webp'}
DUP_PREFIX = "w"

# ---------- утилиты ----------
def indexed_names(folder: Path, prefix: str):
    files = sorted([p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in IMG_EXT],
                   key=lambda x: x.name)
    return [(p, f"{prefix}_{i:03}{p.suffix.lower()}")
            for i, p in enumerate(files, 1)]

def mass_rename(mapping: list[tuple[Path, str]]):
    for old, new_name in mapping:
        new = old.with_name(new_name)
        if new.exists():
            print(f"Пропущено: {new_name}")
            continue
        old.rename(new)
        print(f"Переименовано: {old.name} → {new_name}")

def mark_duplicates(folder: Path, prefix: str):
    """Добавляет DUP_PREFIX к имени дубликатов (сравнение побайтово)."""
    candidates = sorted(folder.glob(f"{prefix}_*"))
    candidates = [p for p in candidates if p.suffix.lower() in IMG_EXT]

    # список уже помеченных, чтобы не сравнивать их повторно
    marked = set()

    for i, master in enumerate(candidates):
        if master in marked:
            continue
        for j, other in enumerate(candidates[i+1:], i+1):
            if other in marked:
                continue
            # быстрый размер → затем побайтово
            if master.stat().st_size == other.stat().st_size and \
               filecmp.cmp(master, other, shallow=False):
                new_name = f"{DUP_PREFIX}_{other.name}"
                other.rename(other.with_name(new_name))
                marked.add(other)
                print(f"Дубликат помечен: {other.name} → {new_name}")

# ---------- пайплайн ----------
def step1_to_neutral():
    print("=== 1️⃣  mo_*** / ev_*** ===")
    mass_rename(indexed_names(MORNING_DIR, "mo"))
    mass_rename(indexed_names(EVENING_DIR, "ev"))

def step2_mark_duplicates():
    print("=== 2️⃣  пометка дубликатов (сравнение побайтово) ===")
    mark_duplicates(MORNING_DIR, "mo")
    mark_duplicates(EVENING_DIR, "ev")

def step3_to_final():
    print("=== 3️⃣  morning_*** / evening_*** (уникальные) ===")
    def unique_only(folder, prefix):
        files = [p for p in folder.glob(f"{prefix}_*")
                 if not p.name.startswith(f"{DUP_PREFIX}_") and
                    p.suffix.lower() in IMG_EXT]
        return [(p, f"{prefix}_{i:03}{p.suffix.lower()}")
                for i, p in enumerate(sorted(files), 1)]

    mass_rename(unique_only(MORNING_DIR, "morning"))
    mass_rename(unique_only(EVENING_DIR, "evening"))

if __name__ == "__main__":
    step1_to_neutral()
    step2_mark_duplicates()
    step3_to_final()
    print("\n✅ Готово. Дубликаты помечены префиксом '{}'".format(DUP_PREFIX))