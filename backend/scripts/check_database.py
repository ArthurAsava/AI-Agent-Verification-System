
from sqlalchemy import text

from app.core.database import engine


def main():
    with engine.connect() as connection:
        result = connection.execute(
            text("SELECT current_database(), current_user, version()")
        ).one()

        print("Database connection successful")
        print(f"Database: {result[0]}")
        print(f"User: {result[1]}")
        print(f"PostgreSQL: {result[2].split(',')[0]}")


if __name__ == "__main__":
    main()
