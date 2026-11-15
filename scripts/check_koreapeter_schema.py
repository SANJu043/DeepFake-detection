from datasets import load_dataset

try:
    ds = load_dataset("KoreaPeter/faceforensics-c23", split="train", streaming=True)
    sample = next(iter(ds))
    print("Features:", list(sample.keys()))
    for k in sample.keys():
        if k != "image" and k != "frame":
            print(f"  {k}: {sample[k]}")
        else:
            print(f"  {k}: {type(sample[k])}")
except Exception as e:
    print("Error:", e)

