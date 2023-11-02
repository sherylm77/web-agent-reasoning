from bs4 import BeautifulSoup
from PIL import Image
import urllib.request
import random

from os import listdir
from os.path import isfile, join
onlyfiles = [f for f in listdir("/Users/sid/Desktop/MML/render_html") if isfile(join("/Users/sid/Desktop/MML/render_html", f))]



ids = random.sample(onlyfiles, 10)
print(ids)
for task_id in ids:
    html_file = open("/Users/sid/Desktop/MML/render_html/"+task_id, "r", encoding="latin_1")
    index = html_file.read()

    S = BeautifulSoup(index, "html.parser")
    imgs = S.find_all("img")

    urllib.request.urlretrieve(imgs[0]['src'], str(task_id) + ".png")

    query_image = Image.open(str(task_id) + ".png")