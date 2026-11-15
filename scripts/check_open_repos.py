from datasets import load_dataset_builder

for repo in ["gonnerthetooner/FaceForensics", "gonnerthetooner/DFDC-extracted-full", "Sarim-Hash/video_DEEPFAKE_dataset", "angads24/deepfake-video"]:
    print(f"\nChecking {repo}...")
    try:
        builder = load_dataset_builder(repo)
        print(f"  SUCCESS! Features: {list(builder.info.features.keys()) if builder.info.features else 'None'}")
    except Exception as e:
        print(f"  Error: {e}")

