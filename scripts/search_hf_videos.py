from huggingface_hub import list_datasets

print("Searching datasets...")
for q in ["deepfake video", "dfdc", "faceforensics", "deepfake-detection", "fake video"]:
    print(f"\n--- Query: {q} ---")
    results = list(list_datasets(search=q, limit=10))
    for ds in results:
        print(f"  {ds.id} | downloads={ds.downloads}")

