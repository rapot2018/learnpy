import json

with open("jobs.json") as f:
    jobs = json.load(f)

for job in jobs:
    print(job["title"])