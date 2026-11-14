
import uuid
from app.database.supabase_client import get_supabase_client

def test_supabase_crud():
    supabase = get_supabase_client()

    # Unique temporary test record
    test_roll_no = f"TEST-{uuid.uuid4().hex[:10]}"

    student = {
        "roll_no": test_roll_no,
        "name": "Temporary Test Student",
        "branch": "TEST BRANCH",
        "role": "student",
        "is_active": True
    }

    inserted = False

    try:
        print("\n========== SUPABASE CRUD TEST ==========")

        # 1. INSERT
        print("\n1. Testing INSERT...")
        response = supabase.table("students").insert(student).execute()

        if not response.data:
            raise RuntimeError("Insert returned no data.")

        inserted = True
        print("INSERT successful.")

        # 2. READ
        print("\n2. Testing READ...")
        response = (
            supabase.table("students")
            .select("*")
            .eq("roll_no", test_roll_no)
            .execute()
        )

        if not response.data:
            raise RuntimeError("Inserted student could not be read.")

        print("READ successful.")
        print("Record:", response.data[0])

        # 3. UPDATE
        print("\n3. Testing UPDATE...")
        response = (
            supabase.table("students")
            .update({"branch": "UPDATED TEST BRANCH"})
            .eq("roll_no", test_roll_no)
            .execute()
        )

        if not response.data:
            raise RuntimeError("Update returned no data.")

        print("UPDATE successful.")

        # Verify update
        verification = (
            supabase.table("students")
            .select("branch")
            .eq("roll_no", test_roll_no)
            .execute()
        )

        if (
            not verification.data
            or verification.data[0]["branch"] != "UPDATED TEST BRANCH"
        ):
            raise RuntimeError("Updated value could not be verified.")

        print("UPDATE verification successful.")

    except Exception as error:
        print("\nCRUD TEST ERROR:", error)

    finally:
        # 4. DELETE temporary record
        if inserted:
            try:
                print("\n4. Cleaning up temporary record...")
                supabase.table("students").delete().eq(
                    "roll_no", test_roll_no
                ).execute()

                remaining = (
                    supabase.table("students")
                    .select("id")
                    .eq("roll_no", test_roll_no)
                    .execute()
                )

                if remaining.data:
                    print("WARNING: Temporary record still exists.")
                else:
                    print("DELETE successful. Temporary record removed.")

            except Exception as error:
                print("CLEANUP ERROR:", error)
                print("Check Supabase for roll number:", test_roll_no)

    print("\n========== TEST FINISHED ==========")


if __name__ == "__main__":
    test_supabase_crud()
