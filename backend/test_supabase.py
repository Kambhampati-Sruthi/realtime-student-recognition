
from app.database.supabase_client import get_supabase_client


def test_connection():
    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("students")
            .select("id")
            .limit(1)
            .execute()
        )

        print("Supabase connection successful!")
        print("Students table is accessible.")
        print("Returned rows:", len(response.data))

    except Exception as error:
        print("Supabase connection failed!")
        print("Error:", error)


if __name__ == "__main__":
    test_connection()
