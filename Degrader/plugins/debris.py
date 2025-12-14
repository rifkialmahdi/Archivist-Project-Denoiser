import numpy as np
import random
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates
from core.utils import create_distorted_mask

def apply(img, count_range, intensity_range):
    arr = np.array(img, dtype=np.float32)
    h, w, _ = arr.shape

    num_debris = random.randint(*count_range)
    if num_debris == 0: return img

    mask_sharp = create_distorted_mask(h, w, int(num_debris * 0.7), size_factor=random.uniform(0.8, 1.2))
    mask_sharp *= np.random.normal(1.0, 0.2, (h, w))
    mask_sharp = np.clip(mask_sharp / 255.0, 0, 1)

    mask_blur = create_distorted_mask(h, w, int(num_debris * 0.3), size_factor=1.5)
    mask_blur = gaussian_filter(mask_blur, sigma=1.2)
    mask_blur = np.clip(mask_blur / 255.0, 0, 1)

    mask_blur = mask_blur ** 2.0

    mask_blur *= 0.6

    total_mask = np.clip(mask_sharp + mask_blur, 0, 1)

    threshold = 0.1
    total_mask = (total_mask - threshold)
    total_mask[total_mask < 0] = 0.0

    if np.max(total_mask) > 0:
        total_mask /= (1.0 - threshold)
    else:
        return img

    total_mask = np.clip(total_mask, 0, 1)
    total_mask = gaussian_filter(total_mask, sigma=random.uniform(0.3, 0.6))

    coverage = np.mean(total_mask)
    max_allowed_coverage = 0.15

    if coverage > max_allowed_coverage:
        factor = max_allowed_coverage / coverage
        total_mask *= factor

    if np.max(total_mask) < 0.01: return img

    gy, gx = np.gradient(total_mask)
    shift_amount = random.uniform(0.1, 0.5)
    y_grid, x_grid = np.indices((h, w))

    coords_y = y_grid - gy * shift_amount
    coords_x = x_grid - gx * shift_amount

    refracted_arr = np.zeros_like(arr)
    for c in range(3):
        refracted_arr[:,:,c] = map_coordinates(arr[:,:,c], [coords_y, coords_x], order=1, mode='reflect')

    if random.random() < 0.6:

        base_rgb = np.array(random.choice([(30,30,25), (25,30,30), (30,25,30)]), dtype=np.float32)
        blend_mode = 'darken'
    else:

        base_rgb = np.array(random.choice([(210,205,195), (195,205,210)]), dtype=np.float32)
        blend_mode = 'lighten'

    debris_layer = np.full((h, w, 3), base_rgb + np.random.uniform(-10, 10, 3), dtype=np.float32)
    debris_layer += np.random.normal(0, 10, (h, w, 3))

    opacity = random.uniform(*intensity_range)
    alpha_mask = total_mask[:,:,np.newaxis] * opacity

    if blend_mode == 'darken':
        final_arr = refracted_arr * (1 - alpha_mask) + (refracted_arr * 0.4) * alpha_mask
    else:
        final_arr = refracted_arr * (1 - alpha_mask) + (refracted_arr + debris_layer * 0.2) * alpha_mask

    return Image.fromarray(final_arr.clip(0, 255).astype(np.uint8))
