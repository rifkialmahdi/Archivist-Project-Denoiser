import numpy as np
import random
from PIL import Image
from scipy.ndimage import gaussian_filter, sobel, binary_dilation

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

def apply_smart_texture_trap(arr, prob, intensity_range, speckle_count_range, threshold=15.0):
    if random.random() > prob:
        return arr

    h, w = arr.shape[:2]
    arr_float = arr.astype(np.float32)

    flat_mask = get_flatness_mask(arr_float, threshold=threshold)

    if np.mean(flat_mask) < 0.1:
        return arr

    noise = np.random.normal(0, 1, (h, w, 3)).astype(np.float32)
    sigma = random.uniform(0.5, 1.2)
    for c in range(3):
        noise[:,:,c] = gaussian_filter(noise[:,:,c], sigma=sigma)

    min_i, max_i = intensity_range
    if max_i > 2.0:
        min_i /= 100.0
        max_i /= 100.0

    strength = random.uniform(min_i, max_i) * 127.5
    noise_layer = noise * strength

    speckle_layer = np.zeros_like(arr_float)
    if speckle_count_range:
        num_speckles = random.randint(*speckle_count_range)
        if num_speckles > 0:
            ys = np.random.randint(0, h, num_speckles)
            xs = np.random.randint(0, w, num_speckles)
            for i in range(num_speckles):
                radius = random.randint(2, 6)
                cy, cx = ys[i], xs[i]
                y_min, y_max = max(0, cy - radius), min(h, cy + radius)
                x_min, x_max = max(0, cx - radius), min(w, cx + radius)
                val = random.choice([-50.0, 50.0])
                speckle_layer[y_min:y_max, x_min:x_max] = val
            speckle_layer = gaussian_filter(speckle_layer, sigma=1.5)

    combined_noise = noise_layer + speckle_layer
    output = arr_float + combined_noise * flat_mask

    return output

def get_edge_protection_mask(arr, sigma=1.0):
    if arr.ndim == 3:
        gray = np.mean(arr, axis=2)
    else:
        gray = arr

    sx = sobel(gray, axis=0, mode='constant')
    sy = sobel(gray, axis=1, mode='constant')
    sob = np.hypot(sx, sy)

    max_val = np.max(sob)
    if max_val > 0:
        sob /= max_val

    sob = gaussian_filter(sob, sigma=sigma)

    protection_strength = 0.6
    mask = 1.0 - (sob * protection_strength)

    return np.clip(mask, 0.2, 1.0)[:, :, np.newaxis]

def apply_complex_grain(arr, strength, color_mask, emphasis_map, is_extreme, extreme_mult=1.0, monochrome=False):
    h, w = arr.shape[:2]

    edge_protection = get_edge_protection_mask(arr)

    uniform_range = np.sqrt(3)

    if monochrome:
        base_grain_gray = np.random.uniform(-uniform_range, uniform_range, (h, w)).astype(np.float32)
        base_grain_gray = gaussian_filter(base_grain_gray, sigma=random.uniform(0.75, 1.2))
        base_grain = np.stack([base_grain_gray] * 3, axis=-1)
    else:
        base_grain = np.random.uniform(-uniform_range, uniform_range, (h, w, 3)).astype(np.float32)
        for c in range(3):
            base_grain[:,:,c] = gaussian_filter(base_grain[:,:,c], sigma=random.uniform(0.75, 1.2))

    if is_extreme:
        strength *= extreme_mult

        scale_factor = random.randint(4, 8)

        h_low, w_low = max(1, h // scale_factor), max(1, w // scale_factor)

        clump_map_low = np.random.normal(0, 1, (h_low, w_low)).astype(np.float32)

        clump_map = np.array(Image.fromarray(clump_map_low).resize((w, h), Image.BICUBIC))

        threshold = random.uniform(-0.5, 0.5)

        mask_3d = np.where(clump_map > threshold, 1.0, 0.0)

        mask_3d = gaussian_filter(mask_3d, sigma=0.5)[:, :, np.newaxis]

        chroma_grain = np.random.normal(0, 1, (h, w, 3)).astype(np.float32)

        chroma_mult = np.array([random.uniform(1.2, 1.5),
                                random.uniform(0.8, 1.0),
                                random.uniform(1.3, 1.6)]
                               ).astype(np.float32)

        chroma_grain *= chroma_mult

        clumped_grain = chroma_grain * 2.0

        base_grain = base_grain * (1.0 - mask_3d) + clumped_grain * mask_3d

    std = np.std(base_grain, axis=(0,1), keepdims=True)
    base_grain = base_grain / (std + 1e-8) * strength

    pass

    for c in range(3):
        base_grain[:,:,c] *= color_mask * emphasis_map

    desat = (np.mean(arr, axis=2, keepdims=True) * [0.55, 0.52, 0.5] - arr) * (color_mask * 0.07)[:,:,np.newaxis]

    return arr + base_grain + desat

def apply_luminance_grain(arr, strength_range):
    hsv = np.array(Image.fromarray(arr.clip(0, 255).astype(np.uint8)).convert('HSV'), dtype=np.float32)
    saturation_mask = hsv[:, :, 1] / 255.0
    saturation_mask = gaussian_filter(saturation_mask, sigma=3)

    h, w = arr.shape[:2]

    h_small, w_small = max(1, h // 2), max(1, w // 2)
    small_noise = np.random.normal(0, 1, (h_small, w_small)).astype(np.float32)

    noise_img = Image.fromarray(small_noise)
    noise_img = noise_img.resize((w, h), resample=Image.Resampling.NEAREST)
    noise = np.array(noise_img)

    strength = np.random.uniform(*strength_range)
    noise = noise * strength

    noise_mask = (noise * saturation_mask)[:, :, np.newaxis]

    output_arr = arr + noise_mask
    return output_arr.clip(0, 255)

def apply_texture_trap(arr, prob, intensity_range):
    return apply_smart_texture_trap(arr, prob, intensity_range, (0,0), threshold=15.0)
