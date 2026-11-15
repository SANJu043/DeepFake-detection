"""Probe Ruchi2003/Celeb_DF_Frames deeper."""
from huggingface_hub import list_repo_tree
import itertools

print('=== Ruchi2003/Celeb_DF_Frames (deeper) ===')
try:
    items = list(itertools.islice(
        list_repo_tree('Ruchi2003/Celeb_DF_Frames', repo_type='dataset', recursive=True), 
        200
    ))
    for item in items:
        fname = getattr(item, 'rfilename', str(item))
        size = getattr(item, 'size', None)
        if size:
            print(f'  {fname}  ({size/1024:.1f} KB)')
        else:
            print(f'  {fname}/')
    print(f'\nTotal items shown: {len(items)}')
except Exception as e:
    print(f'Error: {e}')

print()

# Also try thenewsupercell/celeb-df-image-dataset deeper
print('=== thenewsupercell/celeb-df-image-dataset (deeper) ===')
try:
    items = list(itertools.islice(
        list_repo_tree('thenewsupercell/celeb-df-image-dataset', repo_type='dataset', recursive=True), 
        100
    ))
    for item in items:
        fname = getattr(item, 'rfilename', str(item))
        size = getattr(item, 'size', None)
        if size:
            print(f'  {fname}  ({size/1024/1024:.1f} MB)')
        else:
            print(f'  {fname}/')
    print(f'\nTotal items shown: {len(items)}')
except Exception as e:
    print(f'Error: {e}')
