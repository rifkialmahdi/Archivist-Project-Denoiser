import os
from PIL import Image
from PyQt6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                             QPushButton, QScrollArea, QFileDialog, QMessageBox, QProgressBar,
                             QApplication, QLineEdit, QAbstractSpinBox,
                             QStackedWidget)
from PyQt6.QtCore import Qt, QTimer, QEvent
from PyQt6.QtGui import QImage, QPixmap
import numpy as np
from plugins import segmentation

from .styles import DARK_THEME
from .widgets import ComparisonViewer, GenerationInfoBar
from .panels import SettingsPanel, ViewerSettingsPanel
from .worker import ImageGeneratorWorker
from .batch import BatchSetupDialog, BatchExecutionView, BatchWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Degrader Ultimate")
        self.resize(1600, 950)
        self.setStyleSheet(DARK_THEME)

        self.current_path = None
        self.img_original = None
        self.img_processed = None

        self.last_profile = None
        self.last_seeds = None

        self.mask_timer = QTimer()
        self.mask_timer.setSingleShot(True)
        self.mask_timer.setInterval(100)
        self.mask_timer.timeout.connect(self._perform_mask_calculation)
        self.pending_threshold = 10.0

        self._init_ui()

        QApplication.instance().installEventFilter(self)

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)

        left_container = QWidget()
        left_container.setFixedWidth(400)
        left_container.setObjectName("SettingsPanel")
        self.left_container = left_container
        left_layout = QVBoxLayout(left_container)

        btn_box = QHBoxLayout()
        self.btn_load = QPushButton("📂 Img")
        self.btn_save = QPushButton("💾 Img")
        self.btn_load.clicked.connect(self.load_image)
        self.btn_save.clicked.connect(self.save_image)
        btn_box.addWidget(self.btn_load)
        btn_box.addWidget(self.btn_save)
        left_layout.addLayout(btn_box)

        self.viewer_settings = ViewerSettingsPanel()
        left_layout.addWidget(self.viewer_settings)

        btn_batch = QPushButton("📦 BATCH PROCESSING")
        btn_batch.setStyleSheet("background-color: #FF9800; color: white; font-weight: bold; padding: 8px;")
        btn_batch.clicked.connect(self.open_batch_dialog)
        left_layout.addWidget(btn_batch)

        prof_box = QHBoxLayout()
        self.btn_load_prof = QPushButton("📂 Profile")
        self.btn_save_prof = QPushButton("💾 Profile")
        self.btn_load_prof.clicked.connect(self.load_profile)
        self.btn_save_prof.clicked.connect(self.save_profile)
        prof_box.addWidget(self.btn_load_prof)
        prof_box.addWidget(self.btn_save_prof)
        left_layout.addLayout(prof_box)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.settings = SettingsPanel()
        self.settings.setObjectName("ControlsWidget")
        scroll.setWidget(self.settings)
        left_layout.addWidget(scroll)

        gen_layout = QHBoxLayout()
        self.btn_gen = QPushButton("⚡ RANDOM GEN")
        self.btn_gen.setObjectName("GenButton")
        self.btn_gen.clicked.connect(lambda: self.start_generation(smart=False))

        self.btn_smart_gen = QPushButton("♻️ SMART GEN")
        self.btn_smart_gen.setObjectName("GenButton")
        self.btn_smart_gen.setStyleSheet("background-color: #2196F3;")
        self.btn_smart_gen.clicked.connect(lambda: self.start_generation(smart=True))
        gen_layout.addWidget(self.btn_gen, 1)
        gen_layout.addWidget(self.btn_smart_gen, 1)
        left_layout.addLayout(gen_layout)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        left_layout.addWidget(self.progress)

        main_layout.addWidget(self.left_container)

        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        right_layout.setSpacing(0)

        self.stack = QStackedWidget()
        right_layout.addWidget(self.stack, 1)

        self.info_bar = GenerationInfoBar()
        right_layout.addWidget(self.info_bar)

        main_layout.addWidget(right_container, 1)

        self.viewer = ComparisonViewer()
        self.stack.addWidget(self.viewer)

        self.batch_view = BatchExecutionView()
        self.batch_view.stop_requested.connect(self.stop_batch)
        self.stack.addWidget(self.batch_view)

        self.viewer_settings.settings_changed.connect(self.viewer.set_magnifier_params)
        self.viewer_settings.speed_changed.connect(self.viewer.set_move_speed)
        self.viewer_settings.magnifier_toggled.connect(self.viewer.toggle_magnifier)
        self.viewer_settings.freeze_toggled.connect(self.viewer.toggle_freeze)

        self.settings.request_mask_preview.connect(self.queue_mask_preview)
        self.settings.clear_mask_preview.connect(lambda: self.viewer.set_mask_overlay(None))

        self.settings.request_solo_gen.connect(self.run_solo_generation)

        QTimer.singleShot(0, self.viewer_settings._update)

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress or event.type() == QEvent.Type.KeyRelease:
            key = event.key()

            target_keys = {
                Qt.Key.Key_W, Qt.Key.Key_A, Qt.Key.Key_S, Qt.Key.Key_D,
                Qt.Key.Key_Q, Qt.Key.Key_E, Qt.Key.Key_Shift
            }

            if key in target_keys:
                focus_w = QApplication.focusWidget()
                if isinstance(focus_w, (QLineEdit, QAbstractSpinBox)):
                    return super().eventFilter(source, event)

                active_viewer = None
                if self.stack.currentIndex() == 0:
                    active_viewer = self.viewer
                elif self.stack.currentIndex() == 1:
                    active_viewer = self.batch_view.viewer

                if active_viewer:
                    if event.type() == QEvent.Type.KeyPress:
                        if not event.isAutoRepeat():
                            active_viewer.handle_external_key_press(key)
                    else:
                        if not event.isAutoRepeat():
                            active_viewer.handle_external_key_release(key)

                return True

        return super().eventFilter(source, event)

    def load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.tif)")
        if path:
            self.current_path = path
            self.img_original = Image.open(path).convert('RGB')
            self.viewer.set_images(self.img_original, self.img_original)
            self.setWindowTitle(f"Project Degrader - {os.path.basename(path)}")
            self.last_profile = None
            self.last_seeds = None

    def start_generation(self, smart=False):
        if not self.current_path:
            QMessageBox.warning(self, "Error", "Load an image!")
            return

        if smart:
            profile, seeds = self.settings.get_smart_profile(self.last_profile, self.last_seeds)
        else:
            profile, seeds = self.settings.get_smart_profile(None, None)

        self.last_profile = profile.copy()
        if 'seed_map' in self.last_profile:
            del self.last_profile['seed_map']
        self.last_seeds = seeds

        self.set_ui_busy(True)
        self.worker = ImageGeneratorWorker(self.current_path, profile)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def set_ui_busy(self, busy):
        self.btn_gen.setEnabled(not busy)
        self.btn_smart_gen.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy: self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
            self.progress.setValue(100)

    def on_finished(self, result_img, stats):
        self.img_processed = result_img
        self.viewer.set_images(self.img_original, self.img_processed)
        self.set_ui_busy(False)
        self.info_bar.update_data(stats)

    def on_error(self, err):
        QMessageBox.critical(self, "Error", err)
        self.set_ui_busy(False)

    def save_image(self):
        if not self.img_processed: return
        path, _ = QFileDialog.getSaveFileName(self, "Save", "", "PNG (*.png);;JPEG (*.jpg)")
        if path: self.img_processed.save(path)

    def save_profile(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Profile", "", "JSON (*.json)")
        if path: self.settings.save_profile_json(path)

    def load_profile(self):
        if not self.settings.check_unsaved_changes():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load Profile", "", "JSON (*.json)")
        if path:
            self.settings.load_profile_json(path)
            self.settings.combo_profiles.blockSignals(True)
            self.settings.combo_profiles.setCurrentIndex(-1)
            self.settings.combo_profiles.setPlaceholderText(os.path.basename(path))
            self.settings._prev_combo_index = -1
            self.settings.combo_profiles.blockSignals(False)

    def queue_mask_preview(self, threshold):
        self.pending_threshold = threshold
        self.mask_timer.start()

    def _perform_mask_calculation(self):
        if not self.img_original: return
        threshold = self.pending_threshold
        mask = segmentation.get_flat_area_mask(self.img_original, threshold=threshold)
        h, w = mask.shape
        img_data = np.zeros((h, w, 4), dtype=np.uint8)
        img_data[:, :, 0] = 255
        img_data[:, :, 3] = (mask * 180).astype(np.uint8)
        qimg = QImage(img_data.data, w, h, w * 4, QImage.Format.Format_RGBA8888)
        self.viewer.set_mask_overlay(QPixmap.fromImage(qimg))

    def open_batch_dialog(self):
        dlg = BatchSetupDialog(self)
        if dlg.exec():
            conf = dlg.get_configuration()
            self.run_batch(conf)

    def run_batch(self, conf):

        self.left_container.setVisible(False)

        self.stack.setCurrentIndex(1)
        self.batch_view.reset()

        self.batch_worker = BatchWorker(conf)
        self.batch_worker.progress.connect(self.batch_view.update_progress)
        self.batch_worker.file_finished.connect(self.batch_view.update_file_info)
        self.batch_view.stats_received.connect(self.info_bar.update_data)
        self.batch_worker.finished.connect(self.on_batch_finished)
        self.batch_worker.stopped.connect(self.on_batch_stopped)
        self.batch_worker.start()

    def stop_batch(self):
        if hasattr(self, 'batch_worker') and self.batch_worker.isRunning():
            self.batch_view.btn_stop.setText("STOPPING...")
            self.batch_view.btn_stop.setEnabled(False)
            self.batch_worker.stop()

    def on_batch_finished(self):
        QMessageBox.information(self, "Done", "Batch processing finished!")
        self.restore_ui_after_batch()

    def on_batch_stopped(self):
        QMessageBox.warning(self, "Stop", "Processing stopped by user.")
        self.restore_ui_after_batch()

    def restore_ui_after_batch(self):

        self.left_container.setVisible(True)
        self.stack.setCurrentIndex(0)

    def run_solo_generation(self, profile):
        if not self.current_path:
            return
        self.set_ui_busy(True)
        self.worker = ImageGeneratorWorker(self.current_path, profile)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def closeEvent(self, event):
        if self.settings.check_unsaved_changes():
            event.accept()
        else:
            event.ignore()
