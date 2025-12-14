import numpy as np
import random
from PIL import Image
from scipy.ndimage import gaussian_filter

class PipelineContext:
    def __init__(self, image: Image.Image, config: dict):
        self.original_pil = image
        self.current_pil = image
        self.current_arr = None
        self.config = config
        self.stats = {}

        self.seed_map = config.get('seed_map', {})
        if not self.seed_map and 'seed' in config:
            random.seed(int(config['seed']))
            np.random.seed(int(config['seed']))

        post_enabled = config.get('grp_post', True)
        is_extreme_allowed = config.get('extreme_mode', False)
        extreme_prob = float(config.get('extreme_mode_probability', 0.0))

        self.extreme = False
        self.ext_mult = 1.0
        self.ext_cast = 1.0

        if post_enabled and is_extreme_allowed:
            self.extreme = random.random() < extreme_prob

        self.stats['is_extreme'] = 1 if self.extreme else 0

        if self.extreme:

            s_range = config.get('extreme_strength_range', (1.5, 2.5))

            c_range = config.get('extreme_cast_range', (1.5, 2.2))

            if isinstance(s_range, (list, tuple)):
                self.ext_mult = random.uniform(float(s_range[0]), float(s_range[1]))
            else:
                self.ext_mult = float(s_range)

            if isinstance(c_range, (list, tuple)):
                self.ext_cast = random.uniform(float(c_range[0]), float(c_range[1]))
            else:
                self.ext_cast = float(c_range)

            self.stats['ext_mult'] = round(self.ext_mult, 2)
            self.stats['ext_cast'] = round(self.ext_cast, 2)

    def get_image(self) -> Image.Image:
        if self.current_pil is None and self.current_arr is not None:
            self.current_pil = Image.fromarray(self.current_arr.clip(0, 255).astype(np.uint8))
        return self.current_pil

    def get_array(self) -> np.ndarray:
        if self.current_arr is None:
            self.current_arr = np.array(self.current_pil, dtype=np.float32)
        return self.current_arr

    def set_image(self, img):
        if isinstance(img, np.ndarray):
            self.current_arr = img
            self.current_pil = None
        elif isinstance(img, Image.Image):
            self.current_pil = img
            self.current_arr = None

    def get_hsv(self):

        arr = self.get_array()

        pil_tmp = self.get_image()
        hsv = np.array(pil_tmp.convert('HSV'), dtype=np.float32)
        h = hsv[:,:,0] / 255.0 * 360
        s = hsv[:,:,1] / 255.0
        v = hsv[:,:,2] / 255.0
        return h, s, v

    def get_color_mask(self):
        h, s, v = self.get_hsv()
        arr = self.get_array()

        color_mask = np.ones(arr.shape[:2], dtype=np.float32) * 0.9

        blue_range = (h >= 180) & (h <= 270)
        color_mask[blue_range] += (1.0 - np.abs((h[blue_range] - 225) / 45)) * s[blue_range] * 1.3

        color_mask = np.clip(color_mask, 0.15, 2.5)
        return gaussian_filter(color_mask, sigma=6)

    def set_seed_for_group(self, group_key):
        if self.seed_map and group_key in self.seed_map:
            s = self.seed_map[group_key]
            random.seed(s)
            np.random.seed(s)

    def check_prob(self, key):
        val = self.config.get(key, 0.0)
        if isinstance(val, bool): return val
        return random.random() < float(val)

    def get_scalar(self, key, default=0.0):
        val = self.config.get(key, default)
        if isinstance(val, (list, tuple)):
            if len(val) >= 2: return random.uniform(val[0], val[1])
            return float(val[0])
        return float(val)

    def get_int(self, key, default=(0,0)):
        val = self.config.get(key, default)
        if isinstance(val, (list, tuple)):
            v1, v2 = int(round(val[0])), int(round(val[1])) if len(val) > 1 else int(round(val[0]))
            return random.randint(v1, v2)
        return int(round(val))

    def get_float_range(self, key, default=(0.0, 0.0)):
        val = self.config.get(key, default)
        if isinstance(val, (list, tuple)):
            return (float(val[0]), float(val[1]) if len(val) > 1 else float(val[0]))
        return (float(val), float(val))

    def log_stat(self, key, val):
        if isinstance(val, float):
            self.stats[key] = round(val, 3)
        else:
            self.stats[key] = val
