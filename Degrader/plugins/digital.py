import os
import random
import subprocess
import shutil
import uuid
from PIL import Image

FFMPEG_BIN = shutil.which("ffmpeg")

def apply_mpeg(img, quality_range):
    if not FFMPEG_BIN:

        return img

    if isinstance(quality_range, (list, tuple)):
        q = random.randint(int(quality_range[0]), int(quality_range[1]))
    else:
        q = int(quality_range)

    q = max(1, min(31, q))

    uid = uuid.uuid4().hex
    tmp_in = f"tmp_in_{uid}.png"
    tmp_vid = f"tmp_vid_{uid}.mpg"
    tmp_out = f"tmp_out_{uid}.png"

    result_img = img

    try:

        img.save(tmp_in, format='PNG')

        cmd_enc = [
            FFMPEG_BIN, '-y',
            '-hide_banner', '-loglevel', 'error',
            '-i', tmp_in,
            '-c:v', 'mpeg2video',
            '-q:v', str(q),
            '-frames:v', '1',
            '-f', 'mpeg',
            tmp_vid
        ]

        subprocess.run(cmd_enc, check=True, timeout=5)

        cmd_dec = [
            FFMPEG_BIN, '-y',
            '-hide_banner', '-loglevel', 'error',
            '-i', tmp_vid,
            '-frames:v', '1',
            tmp_out
        ]

        subprocess.run(cmd_dec, check=True, timeout=5)

        if os.path.exists(tmp_out):
            loaded_img = Image.open(tmp_out).convert('RGB')
            loaded_img.load()
            result_img = loaded_img

    except Exception as e:

        print(f"[MPEG Plugin Error] {e}")
        return img

    finally:

        for f in [tmp_in, tmp_vid, tmp_out]:
            if os.path.exists(f):
                try:
                    os.remove(f)
                except OSError:
                    pass

    return result_img
