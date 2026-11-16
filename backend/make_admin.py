"""Create an admin account. Run from C:\\Needbridge:   python -m backend.make_admin"""
from getpass import getpass

from backend.auth import create_user

name = input("Admin name: ")
email = input("Admin email: ")
password = getpass("Password (hidden, at least 8 characters): ")
user, errors = create_user(name, email, password, "admin", allow_admin=True)
print("Created admin account for " + user["email"] if user else "Could not create: " + " ".join(errors))