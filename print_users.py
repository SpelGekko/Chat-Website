from main import db, User, app

def print_users():
    with app.app_context():
        users = User.query.all()
        for user in users:
            print(f"Username: {user.username}, Password: {user.password}, Email: {user.email}")

def clear_users():
    with app.app_context():
        db.session.query(User).delete()
        db.session.commit()
        print("All users have been deleted.")

def clear_database():
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("The entire database has been cleared and recreated.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage users in the database.")
    parser.add_argument("--clear", action="store_true", help="Clear all users from the database.")
    parser.add_argument("--clear-db", action="store_true", help="Clear the entire database.")
    args = parser.parse_args()

    if args.clear:
        clear_users()
    elif args.clear_db:
        clear_database()
    else:
        print_users()