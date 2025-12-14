import os
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_FOLDER_CLEAN = '/home/jorj/Real-ESRGAN/dataset/IpsilonBeta'
OUTPUT_FOLDER_LQ = '/home/jorj/Real-ESRGAN/dataset/lq_archivist_strong'
OUTPUT_FOLDER_GT = '/home/jorj/Real-ESRGAN/dataset/gt_archivist_strong'

PROFILES_DIR = BASE_DIR / 'profiles'

RANDOM_SEED = 42

LARGE_STAIN_SIZE_RANGE = (8, 32)
LARGE_STAIN_SMOOTHNESS_RANGE = (20.0, 50.0)
LARGE_STAIN_COLORS = [(60, 80, 140), (130, 110, 70), (50, 110, 100)]

FINE_SPECKLE_SIZE_RANGE = (64, 128)
FINE_SPECKLE_SMOOTHNESS_RANGE = (3.0, 8.0)
FINE_SPECKLE_COLORS = [(150, 60, 60), (50, 140, 50), (70, 70, 160)]

DEGRADATION_PROFILES = {}
PROFILE_PROBABILITIES = {
    'names': [],
    'weights': []
}

def load_profiles():
    global DEGRADATION_PROFILES, PROFILE_PROBABILITIES

    DEGRADATION_PROFILES = {}
    PROFILE_PROBABILITIES = {'names': [], 'weights': []}

    if not PROFILES_DIR.exists():
        print(f"Warning: Profiles directory not found at {PROFILES_DIR}")

        DEGRADATION_PROFILES['default'] = {}
        PROFILE_PROBABILITIES['names'] = ['default']
        PROFILE_PROBABILITIES['weights'] = [1.0]
        return

    json_files = sorted(list(PROFILES_DIR.glob('*.json')))

    total_weight = 0.0
    temp_weights = []

    for p_file in json_files:
        try:
            with open(p_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            name = p_file.stem
            weight = data.pop('weight', 1.0)

            DEGRADATION_PROFILES[name] = data
            PROFILE_PROBABILITIES['names'].append(name)
            temp_weights.append(weight)
            total_weight += weight

            print(f"Loaded profile: {name} (weight: {weight})")

        except Exception as e:
            print(f"Error loading profile {p_file}: {e}")

    if total_weight > 0:
        PROFILE_PROBABILITIES['weights'] = [w / total_weight for w in temp_weights]
    else:

        count = len(PROFILE_PROBABILITIES['names'])
        if count > 0:
            PROFILE_PROBABILITIES['weights'] = [1.0 / count] * count

load_profiles()

