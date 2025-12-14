import numpy as np
import random
from scipy.ndimage import gaussian_filter
import PIL.Image

def apply_emulsion_degradation(arr, hue, strength_range, mix_range, is_extreme, extreme_mult=1.0):

    vulnerable_mask = (hue >= 80) & (hue <= 260)
    if not np.any(vulnerable_mask):
        return arr

    if is_extreme:

        var = 0.5
        mult_r = random.uniform(max(0.1, extreme_mult - var), extreme_mult + var)
        mult_g = random.uniform(max(0.1, extreme_mult - var), extreme_mult + var)
        mult_b = random.uniform(max(0.1, extreme_mult - var), extreme_mult + var)

        base_str = random.randint(int(strength_range[0]*extreme_mult), int(strength_range[1]*extreme_mult))
        base_sigma = random.uniform(1.0, 2.5)
    else:
        base_mults = [random.uniform(0.7, 1.3) for _ in range(3)]
        victim = random.randint(0, 2)
        base_mults[victim] *= random.uniform(1.2, 1.6)
        mult_r, mult_g, mult_b = base_mults
        base_str = random.randint(strength_range[0], strength_range[1])
        base_sigma = random.uniform(0.75, 1.2)

    noise = np.random.randint(-base_str, base_str, arr.shape).astype(np.float32)
    noise[:,:,0] *= mult_r
    noise[:,:,1] *= mult_g
    noise[:,:,2] *= mult_b

    if is_extreme and random.random() < 0.5:
        noise += np.random.normal(0, base_str * 0.5, arr.shape).astype(np.float32)

    for c in range(3):
        noise[:,:,c] = gaussian_filter(noise[:,:,c], sigma=base_sigma * random.uniform(0.8, 1.2))

    noisy_version = (arr + noise).clip(0, 255)

    if is_extreme:
        mix_ratio = random.uniform(0.5, 0.9)
    else:
        mix_ratio = random.uniform(mix_range[0], mix_range[1])

    mix_mask = np.repeat(vulnerable_mask[:, :, np.newaxis], 3, axis=2)
    output = np.copy(arr)
    output[mix_mask] = (arr[mix_mask] * (1 - mix_ratio)) + (noisy_version[mix_mask] * mix_ratio)

    return output

def apply_color_cast(arr, color_mask, is_extreme, extreme_mult=1.0):

    choices = ['blue', 'green', 'yellow_red']

    if not is_extreme:
        choices.append('none')

    cast_type = random.choice(choices)

    if cast_type == 'none':
        return arr

    mult = extreme_mult if is_extreme else 1.0

    if cast_type == 'blue':
        arr[:,:,2] += np.random.uniform(-3, 2) * color_mask * mult
    elif cast_type == 'green':
        arr[:,:,1] += np.random.uniform(1, 4) * color_mask * mult
    elif cast_type == 'yellow_red':
        arr[:,:,2] -= np.random.uniform(1.5, 5) * color_mask * mult

    return arr

