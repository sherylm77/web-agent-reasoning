"""Replace the website placeholders with website domains from env_config
Generate the test data"""
import json
import os
# import sys
# sys.path.append("mmml\webarena\webarena")
# from browser_env.env_config import *

SHOPPING = "http://shop.junglegym.ai/"

def main() -> None:
    with open("..\\config_files\\shop.json", "r") as f: # replaced test.raw with shop data
        raw = f.read()
    # raw = raw.replace("__GITLAB__", GITLAB)
    # raw = raw.replace("__REDDIT__", REDDIT)
    raw = raw.replace("__SHOPPING__", SHOPPING)
    # raw = raw.replace("__SHOPPING_ADMIN__", SHOPPING_ADMIN)
    # raw = raw.replace("__WIKIPEDIA__", WIKIPEDIA)
    # raw = raw.replace("__MAP__", MAP)
    with open("..\\config_files\\test_shop.json", "w") as f:
        f.write(raw)
    # split to multiple files
    data = json.loads(raw)
    for idx, item in enumerate(data):
        with open(os.path.join("..\\config_files", f"{idx}.json"), "w") as f:
            json.dump(item, f, indent=2)


if __name__ == "__main__":
    main()
