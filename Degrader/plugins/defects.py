import numpy as np
import random
import math
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

def apply_micro_defects(arr, dust_count, smudge_count, intensity_range, intensity_map=None):

    h, w = arr.shape[:2]
    mask_layer = Image.new('F', (w, h), 0.0)
    draw = ImageDraw.Draw(mask_layer)

    num_dust = random.randint(*dust_count)
    for _ in range(num_dust):
        cx, cy = random.randint(0, w), random.randint(0, h)
        rx = random.uniform(0.8, 2.2)
        ry = random.uniform(0.8, 2.2)
        val = random.uniform(0.5, 0.95)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=val)

    dust_arr = np.array(mask_layer)
    dust_arr = gaussian_filter(dust_arr, sigma=random.uniform(0.4, 0.8))

    smudge_layer = Image.new('F', (w, h), 0.0)
    draw_smudge = ImageDraw.Draw(smudge_layer)
    num_smudge = random.randint(*smudge_count)

    for _ in range(num_smudge):
        cx, cy = random.randint(0, w), random.randint(0, h)
        if random.random() < 0.6:
            steps, width, step_len = random.randint(2, 4), 1, random.randint(1, 3)
        else:
            steps, width, step_len = random.randint(3, 7), random.randint(1, 2), random.randint(2, 4)
        val = random.uniform(0.3, 0.7)
        points = [(cx, cy)]
        angle = random.uniform(0, 6.28)
        current_x, current_y = cx, cy
        for _ in range(steps):
            angle += random.uniform(-0.6, 0.6)
            current_x += math.cos(angle) * step_len
            current_y += math.sin(angle) * step_len
            points.append((current_x, current_y))
        if len(points) > 1:
            try:
                draw_smudge.line(points, fill=val, width=width, joint='curve')
            except TypeError:
                draw_smudge.line(points, fill=val, width=width)

    smudge_arr = np.array(smudge_layer)
    smudge_arr = gaussian_filter(smudge_arr, sigma=random.uniform(0.8, 1.2))

    total_mask = np.maximum(dust_arr, smudge_arr)
    if intensity_map is not None:
        total_mask *= intensity_map
    base_intensity = random.uniform(*intensity_range)
    delta = total_mask * base_intensity
    if random.random() < 0.85:
        out = arr * (1.0 - delta[:,:,np.newaxis])
    else:
        out = arr + (255 - arr) * delta[:,:,np.newaxis]
    return out.clip(0, 255)

def apply_scratches(arr, count_range, size_range, intensity_range, intensity_map=None):
    h, w = arr.shape[:2]
    layer_light = Image.new('L', (w, h), 0)
    draw_light = ImageDraw.Draw(layer_light)
    layer_dark = Image.new('L', (w, h), 0)
    draw_dark = ImageDraw.Draw(layer_dark)

    num_scratches = random.randint(*count_range)

    for _ in range(num_scratches):
        y, x = random.randint(0, h-1), random.randint(0, w-1)
        length = random.randint(*size_range)
        angle = random.uniform(0, 2*np.pi)
        width = random.uniform(1.0, 1.5)
        intensity = random.uniform(*intensity_range)

        points_pil = []
        for i in range(0, length, 4):
            deviation = random.uniform(-0.8, 0.8)
            new_y = int(y + i * np.sin(angle) + deviation)
            new_x = int(x + i * np.cos(angle) + deviation)
            if -50 <= new_y < h+50 and -50 <= new_x < w+50:
                points_pil.append((new_x, new_y))

        if len(points_pil) < 2: continue

        fill_val = int(min(abs(intensity) * 255 * 3.5, 255))
        if fill_val < 10: fill_val = 10

        try:
            if intensity > 0:
                draw_light.line(points_pil, fill=fill_val, width=int(width), joint='curve')
            else:
                draw_dark.line(points_pil, fill=fill_val, width=int(width), joint='curve')
        except TypeError:
            if intensity > 0:
                draw_light.line(points_pil, fill=fill_val, width=int(width))
            else:
                draw_dark.line(points_pil, fill=fill_val, width=int(width))

    mask_light = np.array(layer_light, dtype=np.float32) / 255.0
    mask_dark = np.array(layer_dark, dtype=np.float32) / 255.0

    if np.max(mask_light) > 0:

        mask_light = gaussian_filter(mask_light, sigma=random.uniform(0.5, 0.9))

        mask_light = np.clip(mask_light, 0, 1)

    if np.max(mask_dark) > 0:
        mask_dark = gaussian_filter(mask_dark, sigma=random.uniform(0.5, 0.9))

        mask_dark = np.clip(mask_dark, 0, 1)

    if intensity_map is not None:
        mask_light *= intensity_map
        mask_dark *= intensity_map

    out = arr.copy()
    if np.max(mask_light) > 0:
        out += (255 - out) * mask_light[:,:,None]
    if np.max(mask_dark) > 0:
        out *= (1.0 - mask_dark[:,:,None])

    return out.clip(0, 255)

