from main import db, User, Friendship, app

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

def print_friends():
    with app.app_context():
        users = User.query.all()
        for user in users:
            friendships = Friendship.query.filter(
                ((Friendship.username == user.username) | (Friendship.friend_username == user.username))
            ).all()
            friends = []
            for friendship in friendships:
                if friendship.username == user.username:
                    friend = User.query.filter_by(username=friendship.friend_username).first()
                else:
                    friend = User.query.filter_by(username=friendship.username).first()
                friends.append(f"{friend.username} (status: {friendship.status})")
            print(f"Username: {user.username}, Friends: {', '.join(friends) if friends else 'No friends'}")

def clear_friends():
    with app.app_context():
        db.session.query(Friendship).delete()
        db.session.commit()
        print("All friendships have been deleted.")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage users and friendships in the database.")
    parser.add_argument("--clear", action="store_true", help="Clear all users from the database.")
    parser.add_argument("--clear-db", action="store_true", help="Clear the entire database.")
    parser.add_argument("--print-friends", action="store_true", help="Print the friends list for each user.")
    parser.add_argument("--clear-friends", action="store_true", help="Clear all friendships from the database.")
    args = parser.parse_args()

    if args.clear:
        clear_users()
    elif args.clear_db:
        clear_database()
    elif args.print_friends:
        print_friends()
    elif args.clear_friends:
        clear_friends()
    else:
        print_users()