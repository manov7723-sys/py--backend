# datasets/convert_tmx_to_json.py

import xml.etree.ElementTree as ET
import json
import os

# Path to your TMX file
TMX_PATH = os.path.join(os.path.dirname(__file__), "translations.tmx")
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "en_ca_translations.json")

def parse_tmx(tmx_path, max_entries=500):
    tree = ET.parse(tmx_path)
    root = tree.getroot()

    body = root.find("body") or root.find(".//{*}body")

    data = []
    for idx, tu in enumerate(body.findall("tu")):
        en_text = None
        ca_text = None
        for tuv in tu.findall("tuv"):
            lang = tuv.attrib.get("{http://www.w3.org/XML/1998/namespace}lang")
            seg_element = tuv.find("seg")
            seg = seg_element.text.strip() if seg_element is not None and seg_element.text else None

            if lang == "en-GB":
                en_text = seg
            elif lang == "ca-ES":
                ca_text = seg

        if en_text and ca_text:
            data.append({
                "id": f"tmx-{idx:04d}",
                "source": en_text,
                "target": ca_text
            })

        if len(data) >= max_entries:
            break

    return data

if __name__ == "__main__":
    print(f"🔄 Parsing TMX from: {TMX_PATH}")
    parsed = parse_tmx(TMX_PATH, max_entries=500)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)

    print(f"✅ Saved {len(parsed)} EN–CA pairs to: {OUTPUT_PATH}")
