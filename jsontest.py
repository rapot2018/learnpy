import json

data = '{"name":"Ramesh","city":"Charlotte"}'

obj = json.loads(data)

print(obj["name"])