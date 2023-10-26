import json

f = open('test.raw.json')
json_data = json.load(f)

shopping = []

for item in json_data:
    if item['sites'] == ["shopping"]:
        shopping.append(item)

s = open('shop.json', "w")
json.dump(shopping, s)