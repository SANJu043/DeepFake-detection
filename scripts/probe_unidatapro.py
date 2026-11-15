from huggingface_hub import list_repo_tree
import itertools

for p in ["deepfake", "video"]:
    print(f"\n=== UniDataPro/deepfake-videos-dataset/{p} ===")
    items = list(itertools.islice(list_repo_tree("UniDataPro/deepfake-videos-dataset", repo_type="dataset", path_in_repo=p), 15))
    for item in items:
        fname = getattr(item, "rfilename", str(item))
        size = getattr(item, "size", None)
        sz_str = f"({size/1024/1024:.2f} MB)" if size else "(dir)"
        print(f"  {fname} {sz_str}")

