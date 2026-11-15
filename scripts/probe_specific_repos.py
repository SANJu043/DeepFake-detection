from huggingface_hub import list_repo_tree
import itertools

repos = [
    "Shironx/DFDC_Opencv_Face_Crops",
    "irisxue/real-and-fake-video-frames",
    "gonnerthetooner/FaceForensics",
    "KoreaPeter/faceforensics-c23"
]

for r in repos:
    print(f"\n=== {r} ===")
    try:
        items = list(itertools.islice(list_repo_tree(r, repo_type="dataset"), 20))
        for item in items:
            fname = getattr(item, "rfilename", str(item))
            size = getattr(item, "size", None)
            sz_str = f"({size/1024/1024:.1f} MB)" if size else "(dir)"
            print(f"  {fname} {sz_str}")
    except Exception as e:
        print(f"  Error: {e}")

