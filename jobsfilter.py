jobs = [
 {"title":"Java Developer"},
 {"title":"Python Engineer"},
 {"title":"Spring Boot Engineer"}
]

for job in jobs:
    if "Java" in job["title"] or "Spring" in job["title"]:
        print("Apply:", job["title"])