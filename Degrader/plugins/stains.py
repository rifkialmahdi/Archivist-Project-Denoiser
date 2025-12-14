import numpy as np
import random
from PIL import Image
from scipy.ndimage import gaussian_filter

def apply(arr, size_range, smooth_range, str_range, colors):
    h, w = arr.shape[:2]

    size = random.randint(*size_range)
    noise = np.random.rand(size, size)
    noise_full = np.array(Image.fromarray(noise).resize((w, h), Image.BICUBIC))

    mask = gaussian_filter(noise_full, sigma=random.uniform(*smooth_range))

    mn, mx = mask.min(), mask.max()
    if mx - mn > 1e-6:
        mask = (mask - mn) / (mx - mn)
    else:
        mask = np.zeros_like(mask)

    threshold = 0.25
    mask = (mask - threshold)
    mask[mask < 0] = 0.0

    mask /= (1.0 - threshold)
    mask = np.clip(mask, 0, 1.0)

    lum = np.mean(arr, axis=2) / 255.0
    final_mask = (mask * np.sin(lum * np.pi))[:,:,np.newaxis]

    color = np.array(random.choice(colors), dtype=np.float32)
    strength = random.uniform(*str_range)

    inv_alpha = 1.0 - (final_mask * strength)
    color_add = np.full(arr.shape, color, dtype=np.float32) * (final_mask * strength)

    out = arr * inv_alpha + color_add

    return out
