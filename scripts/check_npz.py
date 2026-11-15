from huggingface_hub import hf_hub_download
import numpy as np

try:
    path = hf_hub_download(repo_id="Shironx/DFDC_Opencv_Face_Crops", filename="0_FAKE_0.npz", repo_type="dataset")
    data = np.load(path)
    print("Keys in npz:", list(data.keys()))
    for k in data.keys():
        print(f"  {k}: shape={data[k].shape}, dtype={data[k].dtype}")
except Exception as e:
    print("Error:", e)

