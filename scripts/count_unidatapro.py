from huggingface_hub import list_repo_tree

for p in ["deepfake", "video"]:
    items = list(list_repo_tree("UniDataPro/deepfake-videos-dataset", repo_type="dataset", path_in_repo=p))
    print(f"Total files in {p}: {len(items)}")
    for item in items[:10]:
        fname = getattr(item, "rfilename", str(item))
        size = getattr(item, "size", 0) or 0
        print(f"  {fname} ({size/1024/1024:.2f} MB)")

