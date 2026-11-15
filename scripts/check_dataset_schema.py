import urllib.request
import json
from datasets import load_dataset_builder

try:
    builder = load_dataset_builder("thenewsupercell/celeb-df-image-dataset")
    print("Features:", builder.info.features)
    print("Description:", builder.info.description)
except Exception as e:
    print("Error:", e)

