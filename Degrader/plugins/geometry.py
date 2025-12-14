import numpy as np
import random
from PIL import Image, ImageFilter
from scipy.ndimage import map_coordinates, gaussian_filter, shift

def apply_crease(img, spacing_range, disp_range, darken, color_shift):
    arr = np.array(img, dtype=np.float32)
    h, w, _ = arr.shape

    line_pattern = np.zeros((h, w), dtype=np.float32)

    line_spacing = random.randint(spacing_range[0], spacing_range[1])

    if line_spacing < 4: line_spacing = 4

    line_height = random.randint(1, 2)
    current_y = random.randint(0, line_spacing)

    while current_y < h:
        line_end = min(current_y + line_height, h)
        line_pattern[current_y:line_end, :] = 1.0
        current_y += line_spacing

    cont_h = max(1, h // 8)
    cont_w = max(1, w // 128)
    continuity_map_lowres = np.random.rand(cont_h, cont_w)

    continuity_img = Image.fromarray(continuity_map_lowres).resize((w, h), Image.BICUBIC)
    continuity_map = np.array(continuity_img)

    c_min, c_max = np.min(continuity_map), np.max(continuity_map)
    if c_max - c_min > 1e-6:
        continuity_map = (continuity_map - c_min) / (c_max - c_min)

    warp_h = max(1, h // 24)
    warp_w = max(1, w // 24)
    warp_field_low = np.random.randn(warp_h, warp_w)
    warp_field_img = Image.fromarray(warp_field_low).resize((w, h), Image.BICUBIC)
    warp_field = np.array(warp_field_img)

    y_coords, x_coords = np.indices((h, w))
    warped_y = y_coords + warp_field * random.uniform(0.5, 2.0)

    base_mask = line_pattern * continuity_map

    deformation_mask = map_coordinates(base_mask, [warped_y, x_coords], order=1)
    deformation_mask = gaussian_filter(deformation_mask, sigma=random.uniform(0.5, 1.0))

    dy = random.uniform(disp_range[0], disp_range[1]) * random.choice([-1, 1])
    dx = random.uniform(-0.4, 0.4)

    source_y = y_coords - dy * deformation_mask
    source_x = x_coords - dx * deformation_mask

    displaced_arr = np.zeros_like(arr)
    for c in range(3):
        displaced_arr[:, :, c] = map_coordinates(arr[:, :, c], [source_y, source_x], order=1, mode='reflect')

    mask_3d = deformation_mask[:, :, np.newaxis]

    processed_arr = displaced_arr * (1 - mask_3d * darken)

    luminance = np.mean(processed_arr, axis=2, keepdims=True)
    processed_arr = processed_arr * (1 - mask_3d * 0.15) + luminance * (mask_3d * 0.15)

    if color_shift > 0:
        color_shift_vec = np.array([1.05, 1.0, 0.95])
        shifted_color = processed_arr * color_shift_vec
        processed_arr = processed_arr * (1 - mask_3d * color_shift) + shifted_color * (mask_3d * color_shift)

    return Image.fromarray(processed_arr.clip(0, 255).astype(np.uint8))

def apply_emulsion_shift(img, shift_range):
    arr = np.array(img, dtype=np.float32)

    max_shift = random.randint(shift_range[0], shift_range[1])
    if max_shift == 0:
        return img

    shift_type = 'color' if random.random() < 0.8 else 'luma'

    shift_options = list(range(-max_shift, max_shift + 1))
    dx_r = random.choice(shift_options)
    dy_r = random.choice(shift_options)

    if dx_r == 0 and dy_r == 0:
        dx_r = 1

    dx_b, dy_b = -dx_r, -dy_r

    edge_mask = img.convert('L').filter(ImageFilter.FIND_EDGES)
    edge_mask = np.array(edge_mask, dtype=np.float32) / 255.0
    edge_mask = gaussian_filter(edge_mask, sigma=1.5)[:, :, np.newaxis]

    r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]

    if shift_type == 'color':
        r_shifted = shift(r, (dy_r, dx_r), cval=0, order=1)
        b_shifted = shift(b, (dy_b, dx_b), cval=0, order=1)
        shifted_arr = np.stack([r_shifted, g, b_shifted], axis=-1)
    else:
        luminance = np.mean(arr, axis=2)
        shifted_channel = shift(luminance, (dy_r, dx_r), cval=0, order=1)

        shifted_arr = arr * 0.8 + shifted_channel[:,:,np.newaxis] * 0.2

    output_arr = arr * (1 - edge_mask) + shifted_arr * edge_mask
    return Image.fromarray(output_arr.clip(0, 255).astype(np.uint8))

