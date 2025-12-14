#!/usr/bin/env python3


import json
from pathlib import Path
import config

def fix_profile_values(profile_path):

    with open(profile_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    modified = False

    keys_to_fix = [
        'flat_area_defect_bias', 'flat_area_grain_bias', 'flat_area_exposure',
        'scratches_intensity', 'debris_intensity', 'micro_intensity',
        'large_stain_strength_range', 'fine_speckle_strength_range',
        'crease_darken_strength', 'crease_color_shift_strength',
        'emulsion_degradation_mix_ratio', 'grain_emphasis_on_color',
        'texture_trap_intensity', 'blur_range'
    ]

    for key in keys_to_fix:
        if key in data:
            value = data[key]
            if isinstance(value, list) and len(value) >= 2:

                if abs(value[0]) < 1.0 and abs(value[0]) > 0:
                    data[key][0] = value[0] * 100
                    modified = True
                if abs(value[1]) < 1.0 and abs(value[1]) > 0:
                    data[key][1] = value[1] * 100
                    modified = True
            elif isinstance(value, (int, float)):

                if abs(value) < 1.0 and abs(value) > 0:
                    data[key] = value * 100
                    modified = True

    if modified:
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        print(f"Исправлен профиль: {profile_path}")
        return True
    else:
        print(f"Профиль не требует исправлений: {profile_path}")
        return False

def main():
    if not config.PROFILES_DIR.exists():
        print(f"Директория профилей не найдена: {config.PROFILES_DIR}")
        return

    print(f"Поиск профилей в директории: {config.PROFILES_DIR}")

    fixed_count = 0
    for profile_file in config.PROFILES_DIR.glob('*.json'):
        if fix_profile_values(profile_file):
            fixed_count += 1

    print(f"\Исправлено профилей: {fixed_count}")

if __name__ == "__main__":
    main()

