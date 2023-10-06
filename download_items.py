import json
import requests 
from PIL import Image

def download_images(data):
    for item in data:
        for i, url in enumerate(item['images']):
            if ".gif" in url: # skip gifs
                continue
            img_data = requests.get(url).content 
            img_file = open("../webshop_images/" + item['asin'] + "_" + str(i) + '.jpg','wb') 
            img_file.write(img_data) 
            img_file.close() 
        break

f = open('items_shuffle_1000.json')
json_data = json.load(f)
download_images(json_data)
f.close()