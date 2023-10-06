import json
import requests 
from PIL import Image
import re

def download_images(data):
    for item in data:
        if len(item['name'].split()) < 7:
            prod_name = '_'.join(item['name'].split())
        else:
            prod_name = '_'.join(item['name'].split()[:7]) # take first 7 words from product name
        prod_name = re.sub(r'[^\w\s]', '', prod_name)
        for i, url in enumerate(item['images']):
            if ".gif" in url: # skip gifs
                continue
            img_data = requests.get(url).content 
            img_file = open("../webshop_images/" + prod_name + "_" + str(i) + '.jpg','wb') 
            img_file.write(img_data) 
            img_file.close() 

f = open('items_shuffle_1000.json')
json_data = json.load(f)
download_images(json_data)
f.close()