import numpy as np
import random
from PIL import Image
from scipy.ndimage import gaussian_filter
from plugins import segmentation

def apply_banding(img, levels_range, opacity_range, use_flatness_mask=True):
    arr = np.array(img, dtype=np.float32)

    if isinstance(levels_range, (list, tuple)):
        levels = random.randint(int(levels_range[0]), int(levels_range[1]))
    else:
        levels = int(levels_range)

    if levels >= 250:
        return img

    base_blur = gaussian_filter(arr, sigma=2.0)

    details = arr - base_blur

    step = 255.0 / levels

    quantized_base = np.floor(base_blur / step) * step

    banded_arr = quantized_base + details

    mask = np.ones(arr.shape[:2], dtype=np.float32)

    if use_flatness_mask:

        flat_mask = segmentation.get_flatness_mask(base_blur, threshold=5.0)
        mask *= flat_mask[:, :, 0]

    if isinstance(opacity_range, (list, tuple)):
        opacity = random.uniform(opacity_range[0], opacity_range[1])
    else:
        opacity = float(opacity_range)

    blend_mask = (mask * opacity)[:, :, np.newaxis]

    final_arr = arr * (1.0 - blend_mask) + banded_arr * blend_mask

    return Image.fromarray(np.clip(final_arr, 0, 255).astype(np.uint8))
