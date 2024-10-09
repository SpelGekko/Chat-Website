from main import db, User, app

def print_users():
    with app.app_context():
        users = User.query.all()
        for user in users:
            print(f"Username: {user.username}, Password: {user.password}")

def clear_users():
    with app.app_context():
        db.session.query(User).delete()
        db.session.commit()
        print("All users have been deleted.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage users in the database.")
    parser.add_argument("--clear", action="store_true", help="Clear all users from the database.")
    args = parser.parse_args()

    if args.clear:
        clear_users()
    else:
        print_users()