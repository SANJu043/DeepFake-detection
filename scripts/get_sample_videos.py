import os
import shutil
from huggingface_hub import hf_hub_download

os.makedirs('sample_videos', exist_ok=True)

print("Downloading sample real video...")
p_real = hf_hub_download('angads24/deepfake-video', filename='dataset/real/01__exit_phone_room.mp4', repo_type='dataset')
shutil.copy(p_real, 'sample_videos/sample_real_video.mp4')

print("Downloading sample deepfake video...")
p_fake = hf_hub_download('angads24/deepfake-video', filename='dataset/fake/01_02__outside_talking_still_laughing__YVGY8LOK.mp4', repo_type='dataset')
shutil.copy(p_fake, 'sample_videos/sample_deepfake_video.mp4')

print("\nReady! Sample videos in sample_videos/:")
for f in os.listdir('sample_videos'):
    sz = os.path.getsize(os.path.join('sample_videos', f)) / (1024 * 1024)
    print(f"  {f} ({sz:.2f} MB)")

