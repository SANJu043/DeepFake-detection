from huggingface_hub import list_repo_tree
import itertools

repos = [
    "Sarim-Hash/video_DEEPFAKE_dataset",
    "UniDataPro/deepfake-videos-dataset",
    "ohjoonhee/DF40-Fake-Videos",
    "angads24/deepfake-video"
]

for r in repos:
    print(f"\n=== {r} ===")
    try:
        items = list(itertools.islice(list_repo_tree(r, repo_type="dataset"), 15))
        for item in items:
            fname = getattr(item, "rfilename", str(item))
            size = getattr(item, "size", None)
            sz_str = f"({size/1024/1024:.2f} MB)" if size else "(dir)"
            print(f"  {fname} {sz_str}")
    except Exception as e:
        print(f"  Error: {e}")

