import mimetypes
from pathlib import Path
from app.database.supabase_client import get_supabase_client
from app.services.face_enrollment_service import enroll_student

# UPDATE THIS PATH to the folder shown by Get-ChildItem (e.g., Path(r"data") or Path(r"..\data"))
FOLDER_PATH = Path(r"data")
SOURCE_TYPE = "id_card"  # Change to "face" if they are direct face photos

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
all_images = [p for p in FOLDER_PATH.rglob("*") if p.suffix.lower() in IMAGE_EXTS]
print(f"Found {len(all_images)} images in {FOLDER_PATH.resolve()}: {[p.name for p in all_images]}\n")

sb = get_supabase_client()
students = sb.table("students").select("*").execute().data

for student in students:
    roll_no = student["roll_no"].strip()
    name = student["name"].strip()

    # Match by roll_no OR student first/full name (case-insensitive)
    matches = [
        p for p in all_images
        if p.stem.strip().lower() in {roll_no.lower(), name.lower()}
        or roll_no.lower() in p.stem.lower()
        or name.lower() in p.stem.lower()
    ]

    if not matches:
        print(f"[SKIP] {roll_no} ({name}) — no image found (sample student)")
        continue

    img_path = matches[0]
    mime_type = mimetypes.guess_type(img_path)[0] or "image/jpeg"
    print(f"[PROCESSING] {roll_no} ({name}) using {img_path.name}...")
    result = enroll_student(
        roll_no=roll_no,
        name=name,
        branch=student["branch"],
        year_of_study=student.get("year_of_study"),
        image_bytes=img_path.read_bytes(),
        mime_type=mime_type,
        source_type=SOURCE_TYPE,
    )
    print(f"[OK] Enrolled {roll_no} ({name}) -> {result['embedding_count']} embeddings saved")