import pandas as pd

donations = pd.read_csv("data/donations.csv")
requests = pd.read_csv("data/requests.csv")

print("DONATIONS")
print(donations.head())
print()
print("REQUESTS")
print(requests.head())
print()
print("Verified requests:", (requests["verified"] == "yes").sum())