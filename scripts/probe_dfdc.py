from huggingface_hub import list_repo_tree
import itertools

print("=== Shironx/DFDC_Opencv_Face_Crops ===")
files = list(itertools.islice(list_repo_tree("Shironx/DFDC_Opencv_Face_Crops", repo_type="dataset"), 100))
reals = []
fakes = []
for f in files:
    name = getattr(f, "rfilename", str(f))
    if "REAL" in name:
        reals.append(name)
    elif "FAKE" in name:
        fakes.append(name)

print(f"Sample REAL files ({len(reals)}):", reals[:5])
print(f"Sample FAKE files ({len(fakes)}):", fakes[:5])

