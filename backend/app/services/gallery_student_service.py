
from app.services.gallery_service import load_face_gallery
from app.services.student_service import list_students


def normalize_gallery_label(label):
    """Normalize labels for case-insensitive matching."""
    if not isinstance(label, str):
        return ""

    return label.strip().casefold()


def load_gallery_student_mapping():
    """
    Associate every saved face-gallery identity with its
    corresponding Supabase student record.

    Returns:
        dict:
            {
                "Sruthi": {
                    "student_id": "...",
                    "name": "Sruthi",
                    "roll_no": "...",
                    "branch": "AI & DS",
                    "role": "Student",
                    "is_active": True,
                    "embeddings": numpy_array
                }
            }

    Raises:
        ValueError if a gallery identity cannot be mapped
        unambiguously to a student.
    """

    # Load existing face embeddings and metadata.
    gallery, manifest, config = load_face_gallery()

    # Retrieve current student records from Supabase.
    students = list_students(limit=500)

    if not students:
        raise ValueError("No student records found in Supabase.")

    # Build a normalized student lookup using gallery_label.
    student_lookup = {}

    for student in students:
        label = normalize_gallery_label(
            student.get("gallery_label")
        )

        # Students without a gallery label are not enrolled
        # in the existing face gallery.
        if not label:
            continue

        if label in student_lookup:
            raise ValueError(
                f"Duplicate gallery_label found in Supabase: {label}"
            )

        student_lookup[label] = student

    # Build the final recognition mapping.
    recognition_mapping = {}

    for gallery_label, embeddings in gallery.items():

        normalized_label = normalize_gallery_label(gallery_label)

        student = student_lookup.get(normalized_label)

        if student is None:
            raise ValueError(
                f"No Supabase student found for gallery identity: "
                f"{gallery_label}"
            )

        recognition_mapping[gallery_label] = {
            "student_id": str(student["id"]),
            "name": student["name"],
            "roll_no": student["roll_no"],
            "branch": student.get("branch"),
            "role": student.get("role"),
            "is_active": student.get("is_active", False),
            "gallery_label": gallery_label,
            "embeddings": embeddings,
        }

    # Verify that all gallery identities were mapped.
    if len(recognition_mapping) != len(gallery):
        raise ValueError(
            "Gallery-to-student mapping is incomplete."
        )

    return recognition_mapping


def get_gallery_student_summary():
    """
    Return safe summary information without exposing embeddings.
    """

    mapping = load_gallery_student_mapping()

    return {
        "status": "success",
        "identity_count": len(mapping),
        "active_identities": sum(
            1 for item in mapping.values()
            if item["is_active"]
        ),
        "inactive_identities": sum(
            1 for item in mapping.values()
            if not item["is_active"]
        ),
        "identities": [
            {
                "gallery_label": label,
                "name": item["name"],
                "roll_no": item["roll_no"],
                "branch": item["branch"],
                "is_active": item["is_active"],
                "embedding_shape": item["embeddings"].shape,
            }
            for label, item in mapping.items()
        ],
    }
