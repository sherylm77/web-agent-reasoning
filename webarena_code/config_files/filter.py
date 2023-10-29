import json

f = open('test_shop.json')
json_data = json.load(f)

ids = []

for item in json_data:
    ids.append(item['task_id'])

print(ids)