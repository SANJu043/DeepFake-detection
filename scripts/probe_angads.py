from huggingface_hub import list_repo_tree
import itertools

items = list(itertools.islice(list_repo_tree("angads24/deepfake-video", repo_type="dataset", path_in_repo="dataset"), 30))
print(f"Items in angads24/deepfake-video/dataset: {len(items)}")
for item in items:
    fname = getattr(item, "rfilename", str(item))
    size = getattr(item, "size", 0) or 0
    print(f"  {fname} ({size/1024/1024:.2f} MB)")

