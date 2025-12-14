import numpy as np
import random
from PIL import Image, ImageDraw
from scipy.ndimage import map_coordinates, gaussian_filter

def create_distorted_mask(h, w, count, size_factor=1.0):
    mask = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(mask)
    types = ['speck'] * 5 + ['blob'] * 3 + ['crumb'] * 2 + ['short_hair'] * 1

    for _ in range(count):
        kind = random.choice(types)
        cx, cy = random.randint(0, w), random.randint(0, h)
        if kind == 'speck':
            r = random.randint(1, 2)

            draw.ellipse([cx, cy, cx+r, cy+r], fill=random.randint(180, 255))
        elif kind == 'blob':
            rx = random.randint(1, 3) * size_factor
            ry = random.randint(1, 3) * size_factor
            draw.ellipse([cx-rx, cy-ry, cx+rx, cy+ry], fill=random.randint(200, 255))
        elif kind == 'short_hair':
            length = random.randint(4, 12) * size_factor
            angle = random.uniform(0, 3.14159 * 2)
            ex = cx + np.cos(angle) * length
            ey = cy + np.sin(angle) * length
            draw.line([(cx, cy), (ex, ey)], fill=random.randint(180, 255), width=1)
        elif kind == 'crumb':
            points = []
            rad = random.randint(2, 4)
            for _ in range(3):
                points.append((cx + random.randint(-rad, rad), cy + random.randint(-rad, rad)))
            draw.polygon(points, fill=random.randint(200, 255))

    mask_arr = np.array(mask, dtype=np.float32)
    grid_scale = 64
    h_grid, w_grid = h // grid_scale + 1, w // grid_scale + 1
    dx = np.random.normal(0, 1.0, (h_grid, w_grid)) * random.uniform(2.0, 4.0)
    dy = np.random.normal(0, 1.0, (h_grid, w_grid)) * random.uniform(2.0, 4.0)
    dx_full = np.array(Image.fromarray(dx).resize((w, h), Image.BICUBIC))
    dy_full = np.array(Image.fromarray(dy).resize((w, h), Image.BICUBIC))
    y_grid, x_grid = np.indices((h, w))
    indices = [y_grid + dy_full, x_grid + dx_full]
    distorted_mask = map_coordinates(mask_arr, indices, order=1, mode='reflect')
    return gaussian_filter(distorted_mask, sigma=random.uniform(0.3, 0.7))

