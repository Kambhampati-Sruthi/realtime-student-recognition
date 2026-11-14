
from pathlib import Path

import pandas as pd

from app.database.supabase_client import get_supabase_client


# Resolve paths relative to this script.
BASE_DIR = Path(__file__).resolve().parent
EXCEL_PATH = BASE_DIR / "data" / "student_details.xlsx"

TABLE_NAME = "students"

REQUIRED_COLUMNS = [
    "gallery_label",
    "name",
    "roll_no",
    "branch",
    "role",
]


def clean_value(value):
    """Convert spreadsheet values into clean strings."""

    if pd.isna(value):
        return None

    return str(value).strip()


def validate_students(dataframe):
    """Validate student data before database insertion."""

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing Excel columns: {missing_columns}"
        )

    dataframe = dataframe[REQUIRED_COLUMNS].copy()

    for column in REQUIRED_COLUMNS:
        dataframe[column] = dataframe[column].apply(clean_value)

    if dataframe.isnull().any().any():
        raise ValueError(
            "Some student records contain missing values."
        )

    for column in REQUIRED_COLUMNS:
        if (dataframe[column] == "").any():
            raise ValueError(
                f"Empty values found in column: {column}"
            )

    if dataframe["roll_no"].duplicated().any():
        raise ValueError("Duplicate roll numbers found in Excel.")

    if dataframe["gallery_label"].duplicated().any():
        raise ValueError("Duplicate gallery labels found in Excel.")

    return dataframe


def import_students():
    """Import only new students without overwriting existing records."""

    if not EXCEL_PATH.exists():
        raise FileNotFoundError(
            f"Student Excel file not found: {EXCEL_PATH}"
        )

    print("Reading student Excel file...")

    dataframe = pd.read_excel(EXCEL_PATH)

    dataframe = validate_students(dataframe)

    client = get_supabase_client()

    print("Connected to Supabase.")

    # Retrieve existing student identities.
    response = (
        client.table(TABLE_NAME)
        .select("roll_no,gallery_label")
        .range(0, 9999)
        .execute()
    )

    existing_students = response.data or []

    existing_roll_numbers = {
        student["roll_no"]: student
        for student in existing_students
    }

    existing_gallery_labels = {
        student["gallery_label"]: student["roll_no"]
        for student in existing_students
        if student.get("gallery_label")
    }

    inserted = 0
    skipped = 0
    conflicts = 0
    failed = 0

    print("\nStarting student import...\n")

    for _, row in dataframe.iterrows():

        student = row.to_dict()

        roll_no = student["roll_no"]
        gallery_label = student["gallery_label"]

        # Never overwrite an existing student.
        if roll_no in existing_roll_numbers:

            existing = existing_roll_numbers[roll_no]

            if existing.get("gallery_label") not in (
                None,
                gallery_label,
            ):
                print(
                    f"CONFLICT: Existing roll number has a "
                    f"different gallery identity."
                )
                conflicts += 1
            else:
                print("SKIPPED: Student already exists.")
                skipped += 1

            continue

        # Prevent assigning another student's gallery identity.
        if gallery_label in existing_gallery_labels:

            print(
                "CONFLICT: Gallery label is already assigned "
                "to another roll number."
            )

            conflicts += 1
            continue

        try:
            # Insert only; never use upsert.
            client.table(TABLE_NAME).insert(student).execute()

            existing_roll_numbers[roll_no] = {
                "roll_no": roll_no,
                "gallery_label": gallery_label,
            }

            existing_gallery_labels[gallery_label] = roll_no

            inserted += 1

            print("INSERTED: New student registered.")

        except Exception:
            failed += 1

            print(
                "FAILED: Database rejected a student record. "
                "Check the Supabase error details."
            )

    print("\n========== IMPORT SUMMARY ==========")
    print(f"Excel records:       {len(dataframe)}")
    print(f"Successfully added:  {inserted}")
    print(f"Already existed:     {skipped}")
    print(f"Conflicts:           {conflicts}")
    print(f"Failed:              {failed}")
    print("====================================")

    if conflicts or failed:
        print(
            "Review the conflicts or failures before "
            "considering the import complete."
        )
    else:
        print("Student import completed successfully.")


if __name__ == "__main__":
    import_students()
