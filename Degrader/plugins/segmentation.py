import numpy as np
from scipy.ndimage import sobel, binary_dilation, gaussian_filter

def get_flatness_mask(arr, threshold=15.0):

    if not isinstance(arr, np.ndarray):
        arr = np.array(arr, dtype=np.float32)

    if arr.ndim == 3:
        img_gray = np.mean(arr, axis=2)
    else:
        img_gray = arr

    sx = sobel(img_gray, axis=0, mode='constant')
    sy = sobel(img_gray, axis=1, mode='constant')
    sob = np.hypot(sx, sy)

    edges = sob > threshold

    edges = binary_dilation(edges, iterations=3)

    flat_mask = (~edges).astype(np.float32)

    flat_mask = gaussian_filter(flat_mask, sigma=2.0)

    return flat_mask[:, :, np.newaxis]

get_flat_area_mask = get_flatness_mask

def apply_exposure_bias(img, mask, bias):
    if abs(bias) < 0.001: return img
    from PIL import Image
    arr = np.array(img, dtype=np.float32)
    mask_3d = mask if mask.ndim == 3 else mask[:, :, np.newaxis]
    output = arr * (1.0 + mask_3d * bias)
    return Image.fromarray(output.clip(0, 255).astype(np.uint8))
