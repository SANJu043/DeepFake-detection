from huggingface_hub import list_repo_tree

fakes = list(list_repo_tree("angads24/deepfake-video", repo_type="dataset", path_in_repo="dataset/fake"))
reals = list(list_repo_tree("angads24/deepfake-video", repo_type="dataset", path_in_repo="dataset/real"))
print(f"Total fake videos: {len(fakes)}")
print(f"Total real videos: {len(reals)}")

