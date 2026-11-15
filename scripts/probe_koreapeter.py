from huggingface_hub import list_repo_tree
import itertools

print("=== KoreaPeter/faceforensics-c23/frames ===")
try:
    items = list(itertools.islice(list_repo_tree("KoreaPeter/faceforensics-c23", repo_type="dataset", path_in_repo="frames"), 30))
    for item in items:
        fname = getattr(item, "rfilename", str(item))
        size = getattr(item, "size", None)
        sz_str = f"({size/1024/1024:.2f} MB)" if size else "(dir)"
        print(f"  {fname} {sz_str}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== KoreaPeter/faceforensics-c23/videos ===")
try:
    items = list(itertools.islice(list_repo_tree("KoreaPeter/faceforensics-c23", repo_type="dataset", path_in_repo="videos"), 30))
    for item in items:
        fname = getattr(item, "rfilename", str(item))
        size = getattr(item, "size", None)
        sz_str = f"({size/1024/1024:.2f} MB)" if size else "(dir)"
        print(f"  {fname} {sz_str}")
except Exception as e:
    print(f"Error: {e}")

