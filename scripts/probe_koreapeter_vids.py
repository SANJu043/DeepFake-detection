from huggingface_hub import list_repo_tree
import itertools

for split in ["videos/train", "videos/test"]:
    print(f"\n=== KoreaPeter/faceforensics-c23/{split} ===")
    try:
        items = list(itertools.islice(list_repo_tree("KoreaPeter/faceforensics-c23", repo_type="dataset", path_in_repo=split), 30))
        for item in items:
            fname = getattr(item, "rfilename", str(item))
            size = getattr(item, "size", None)
            sz_str = f"({size/1024/1024:.2f} MB)" if size else "(dir)"
            print(f"  {fname} {sz_str}")
    except Exception as e:
        print(f"Error: {e}")

