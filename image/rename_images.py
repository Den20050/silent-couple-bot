import os
from pathlib import Path

MORNING_DIR = Path(r"C:\Silent-Couple-Bot\image\morning")
EVENING_DIR = Path(r"C:\Silent-Couple-Bot\image\evening")

IMG_EXT = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}

# ======================  UTIL  ======================
def build_indexed_names(folder: Path, prefix: str):
    """Возвращает список (Path, new_name) для всех картинок в папке."""
    files = sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in IMG_EXT],
        key=lambda p: p.name  # сортируем по алфавиту
    )
    return [(p, f"{prefix}_{i:03}{p.suffix.lower()}") for i, p in enumerate(files, 1)]

def mass_rename(mapping: list[tuple[Path, str]]):
    for old_path, new_name in mapping:
        new_path = old_path.with_name(new_name)
        if new_path.exists():
            print(f"Пропущено (уже есть): {new_name}")
            continue
        old_path.rename(new_path)
        print(f"Переименовано: {old_path.name} → {new_name}")

# ======================  STEPS  ======================
def step1_to_neutral():
    print("=== Шаг 1: переименование в mo_*** / ev_*** ===")
    mass_rename(build_indexed_names(MORNING_DIR, "mo"))
    mass_rename(build_indexed_names(EVENING_DIR, "ev"))

def step2_to_final():
    print("=== Шаг 2: возврат к morning_*** / evening_*** ===")
    mass_rename(build_indexed_names(MORNING_DIR, "morning"))
    mass_rename(build_indexed_names(EVENING_DIR, "evening"))

# ======================  RUN  ======================
if __name__ == "__main__":
    step1_to_neutral()
    step2_to_final()
    print("\n✅ Готово.")