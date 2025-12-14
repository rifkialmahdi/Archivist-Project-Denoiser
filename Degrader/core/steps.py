import random
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import gaussian_filter

from plugins import debris, defects, geometry, stains, color, noise, digital, banding
import config

class BaseStep:
    def __init__(self, group_key=None, prob_key=None, seed_key=None):
        self.group_key = group_key
        self.prob_key = prob_key
        self.seed_key = seed_key

    def should_run(self, ctx):

        if self.group_key and not ctx.config.get(self.group_key, True):
            return False

        if self.seed_key:
            ctx.set_seed_for_group(self.seed_key)

        if self.prob_key:
            if not ctx.check_prob(self.prob_key):
                return False

        return True

    def process(self, ctx):
        pass

class TextureTrapStep(BaseStep):
    def process(self, ctx):

        pk = 'smart_trap_probability' if 'smart_trap_probability' in ctx.config else 'texture_trap_probability'
        if not ctx.check_prob(pk): return

        ik = 'smart_trap_intensity' if 'smart_trap_intensity' in ctx.config else 'texture_trap_intensity'

        arr = ctx.get_array()
        trap_range = ctx.get_float_range(ik)

        if not ctx.config.get('grp_debris', True):
            speckle_range = (0, 0)
        else:
            speckle_range = ctx.config.get('smart_trap_speckles', (5, 20))

        flat_thresh = ctx.get_scalar('flat_area_threshold', 15.0)

        arr = noise.apply_smart_texture_trap(arr, 1.0, trap_range, speckle_range, threshold=flat_thresh)
        ctx.set_image(arr)
        ctx.log_stat('trap_int', 1)

class CreaseStep(BaseStep):
    def process(self, ctx):
        img = ctx.get_image()

        sp = ctx.get_int('crease_line_spacing_range')
        disp = ctx.get_scalar('crease_displacement_range')
        dark = ctx.get_scalar('crease_darken_strength')
        shift = ctx.get_scalar('crease_color_shift_strength')

        ctx.log_stat('crease_spacing', sp)
        ctx.log_stat('crease_disp', disp)
        ctx.log_stat('crease_dark', dark)

        img = geometry.apply_crease(img, (sp, sp), (disp, disp), dark, shift)
        ctx.set_image(img)

class EmulsionShiftStep(BaseStep):
    def process(self, ctx):
        img = ctx.get_image()
        rng = ctx.get_int('emulsion_shift_range')
        ctx.log_stat('shift_px', rng)
        img = geometry.apply_emulsion_shift(img, (rng, rng))
        ctx.set_image(img)

class DebrisStep(BaseStep):
    def process(self, ctx):
        img = ctx.get_image()
        cnt = ctx.get_int('debris_count')
        inte = ctx.get_scalar('debris_intensity')

        ctx.log_stat('debris_cnt', cnt)
        ctx.log_stat('debris_int', inte)

        img = debris.apply(img, (cnt, cnt), (inte, inte))
        ctx.set_image(img)

class ScratchesStep(BaseStep):
    def process(self, ctx):
        arr = ctx.get_array()
        cnt = ctx.get_int('scratches_count')
        sz = ctx.get_int('scratches_size')
        inte = ctx.get_scalar('scratches_intensity')

        ctx.log_stat('scratch_cnt', cnt)
        ctx.log_stat('scratch_len', sz)
        ctx.log_stat('scratch_int', inte)

        arr = defects.apply_scratches(arr, (cnt, cnt), (sz, sz), (inte, inte))
        ctx.set_image(arr)

class MicroDefectsStep(BaseStep):
    def process(self, ctx):
        arr = ctx.get_array()
        dust = ctx.get_int('micro_dust_count')
        smudge = ctx.get_int('micro_smudge_count')
        inte = ctx.get_scalar('micro_intensity')

        ctx.log_stat('micro_dust', dust)
        arr = defects.apply_micro_defects(arr, (dust, dust), (smudge, smudge), (inte, inte))
        ctx.set_image(arr)

class StainsStep(BaseStep):
    def process(self, ctx):
        arr = ctx.get_array()

        if ctx.check_prob('large_stain_probability'):
            st_str = ctx.get_scalar('large_stain_strength_range')
            if st_str > 0:
                ctx.log_stat('stain_str', st_str)
                arr = stains.apply(arr,
                                   config.LARGE_STAIN_SIZE_RANGE,
                                   config.LARGE_STAIN_SMOOTHNESS_RANGE,
                                   (st_str, st_str),
                                   config.LARGE_STAIN_COLORS)

        if ctx.check_prob('fine_speckle_probability'):
            sp_str = ctx.get_scalar('fine_speckle_strength_range')
            if sp_str > 0:
                ctx.log_stat('speckle_str', sp_str)
                arr = stains.apply(arr,
                                   config.FINE_SPECKLE_SIZE_RANGE,
                                   config.FINE_SPECKLE_SMOOTHNESS_RANGE,
                                   (sp_str, sp_str),
                                   config.FINE_SPECKLE_COLORS)
        ctx.set_image(arr)

class EmulsionDegradationStep(BaseStep):
    def process(self, ctx):
        arr = ctx.get_array()
        h, _, _ = ctx.get_hsv()

        inte = ctx.get_int('emulsion_degradation_strength')
        mix = ctx.get_scalar('emulsion_degradation_mix_ratio')

        ctx.log_stat('emul_str', inte)
        ctx.log_stat('emul_mix', mix)

        arr = color.apply_emulsion_degradation(arr, h, (inte, inte), (mix, mix),
                                               is_extreme=ctx.extreme,
                                               extreme_mult=ctx.ext_mult)
        ctx.set_image(arr)

class ComplexGrainStep(BaseStep):
    def process(self, ctx):

        if not ctx.config.get('grain_enabled', True):
            return

        arr = ctx.get_array()

        color_mask = ctx.get_color_mask()
        h, _, _ = ctx.get_hsv()

        emp_val = ctx.get_scalar('grain_emphasis_on_color', 1.25)
        if emp_val < 0.1: emp_val = 1.25

        emphasis_map = np.ones(arr.shape[:2], dtype=np.float32)
        emphasis_map[(h >= 40) & (h <= 270)] = emp_val
        emphasis_map = gaussian_filter(emphasis_map, sigma=10)

        g_str = ctx.get_scalar('grain_strength_range')
        ctx.log_stat('grain_str', g_str)

        mono = ctx.check_prob('grain_monochrome_probability')
        if mono: ctx.log_stat('grain_mono', 1)

        arr = noise.apply_complex_grain(arr, g_str, color_mask, emphasis_map,
                                        is_extreme=ctx.extreme,
                                        extreme_mult=ctx.ext_mult,
                                        monochrome=mono)
        ctx.set_image(arr)

class ColorCastStep(BaseStep):
    def process(self, ctx):

        if not ctx.check_prob('color_cast_probability'):
            return

        arr = ctx.get_array()
        mask = ctx.get_color_mask()

        arr = color.apply_color_cast(arr, mask,
                                     is_extreme=ctx.extreme,
                                     extreme_mult=ctx.ext_cast)
        ctx.set_image(arr)

class LuminanceGrainStep(BaseStep):
    def process(self, ctx):

        if not ctx.config.get('grain_enabled', True):
            return

        arr = ctx.get_array()
        arr = noise.apply_luminance_grain(arr, (4.0, 8.0))
        ctx.set_image(arr)

class BlurStep(BaseStep):
    def process(self, ctx):

        if not ctx.config.get('blur_enabled', True):
            return

        if not ctx.check_prob('blur_probability'):
            return

        val = ctx.get_scalar('blur_range')
        if val > 0:
            ctx.log_stat('blur_rad', val)
            img = ctx.get_image()
            img = img.filter(ImageFilter.GaussianBlur(val))
            ctx.set_image(img)

class MpegStep(BaseStep):
    def process(self, ctx):

        if not ctx.check_prob('mpeg_probability'):
            return

        q_range = ctx.config.get('mpeg_quality_range', (5, 10))

        img = ctx.get_image()

        img = digital.apply_mpeg(img, q_range)

        ctx.set_image(img)

        if isinstance(q_range, (list, tuple)):
            ctx.log_stat('mpeg', int((q_range[0] + q_range[1]) / 2))
        else:
            ctx.log_stat('mpeg', int(q_range))

class BandingStep(BaseStep):
    def process(self, ctx):

        if not ctx.config.get('grp_banding', False):
            return

        if not ctx.check_prob('banding_probability'):
            return

        levels_range = ctx.config.get('banding_levels', (40, 100))

        op_range = ctx.get_float_range('banding_opacity', (0.5, 1.0))

        ctx.log_stat('band_lvl', int(np.mean(levels_range)))

        img = ctx.get_image()

        img = banding.apply_banding(img, levels_range, op_range, use_flatness_mask=True)
        ctx.set_image(img)
