import traceback
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image
from core.pipeline import apply_full_pipeline

class ImageGeneratorWorker(QThread):

    finished = pyqtSignal(object, dict)
    error = pyqtSignal(str)

    def __init__(self, img_path, profile):
        super().__init__()
        self.img_path = img_path
        self.profile = profile

    def run(self):
        try:
            clean_img = Image.open(self.img_path).convert('RGB')

            result_img, stats = apply_full_pipeline(clean_img, self.profile)

            self.finished.emit(result_img, stats)

        except Exception as e:
            traceback.print_exc()
            self.error.emit(str(e))

