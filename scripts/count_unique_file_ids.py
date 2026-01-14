"""Count unique file_ids in skipped files."""

from pathlib import Path

skipped_file = Path("image/skipped_evening_evening.txt")

if not skipped_file.exists():
    print("Файл не найден")
    exit(1)

file_ids = set()
current_file_id = None

with open(skipped_file, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("Telegram file_id:"):
            file_id = line.replace("Telegram file_id:", "").strip()
            if file_id:
                file_ids.add(file_id)

print(f"Всего пропущено файлов: 939")
print(f"Уникальных file_id в пропущенных файлах: {len(file_ids)}")
print(f"Разница: {939 - len(file_ids)}")

if len(file_ids) < 939:
    print(f"\n⚠️  ВНИМАНИЕ: Telegram присвоил одинаковые file_id разным файлам!")
    print(f"   Это означает, что {939 - len(file_ids)} файлов имеют дублирующиеся file_id.")
    print(f"   Это нормально для Telegram - он может возвращать одинаковые file_id для одинаковых картинок.")
