from main import db, app
from main import User, TempUser, Friendship, DirectMessage  # Ensure all models are imported
from sqlalchemy import text

with app.app_context():
    # Drop the friendship table
    db.session.execute(text('DROP TABLE IF EXISTS friendship'))
    db.session.commit()
    print("Friendship table dropped successfully.")
    
    # Recreate the tables
    db.create_all()
    print("Tables created successfully.")