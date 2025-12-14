import os
import time
import json
import multiprocessing
import random
import traceback
from pathlib import Path
from PIL import Image
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                             QFileDialog, QDialog, QScrollArea, QFrame, QListWidget,
                             QListWidgetItem, QSizePolicy, QCheckBox, QApplication, QProgressBar,
                             QLineEdit, QSpacerItem, QGridLayout, QSlider)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QSettings, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QCursor, QPixmap

import config
from .widgets import ComparisonViewer

class InteractiveDistributionBar(QWidget):
    distributionChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.setMouseTracking(True)
        self.items = []
        self.hovered_handle = -1
        self.dragging_handle = -1
        self.handle_width = 10

    def set_items(self, active_profiles, colors):
        self.items = []
        count = len(active_profiles)
        if count == 0:
            self.update()
            return
        weight = 1.0 / count
        for i, name in enumerate(active_profiles):
            color = colors[i % len(colors)]
            self.items.append({'name': name, 'color': color, 'weight': weight})
        self._normalize()
        self.update()
        self.distributionChanged.emit()

    def get_probs(self):
        names = [item['name'] for item in self.items]
        weights = [item['weight'] for item in self.items]
        return {'names': names, 'weights': weights}

    def _normalize(self):
        total = sum(item['weight'] for item in self.items)
        if total <= 0: return
        for item in self.items:
            item['weight'] /= total

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self.items:
            painter.setPen(QColor(100, 100, 100))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select at least one profile")
            return

        current_x = 0.0
        for i, item in enumerate(self.items):
            width = item['weight'] * w
            rect = QRectF(current_x, 0, width, h)
            painter.fillRect(rect, item['color'])
            if width > 40:
                percent = int(round(item['weight'] * 100))
                text = f"{percent}%"
                if width > 80: text = f"{item['name']}\n{percent}%"
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(rect.adjusted(1,1,1,1), Qt.AlignmentFlag.AlignCenter, text)
                painter.setPen(Qt.GlobalColor.white)
                painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
            current_x += width

        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        current_x = 0.0
        for i in range(len(self.items) - 1):
            current_x += self.items[i]['weight'] * w
            if i == self.hovered_handle or i == self.dragging_handle:
                painter.setPen(QPen(Qt.GlobalColor.white, 3))
                painter.drawLine(int(current_x), 0, int(current_x), h)
                painter.fillRect(int(current_x)-4, h//2-10, 8, 20, QColor(0,0,0,100))
                painter.drawRect(int(current_x)-4, h//2-10, 8, 20)
            else:
                painter.setPen(QPen(QColor(255,255,255,100), 1))
                painter.drawLine(int(current_x), 0, int(current_x), h)

    def mouseMoveEvent(self, event):
        w = self.width()
        x = event.pos().x()
        if self.dragging_handle != -1:
            idx = self.dragging_handle
            left_bound_x = sum(self.items[k]['weight'] for k in range(idx)) * w
            right_bound_x = sum(self.items[k]['weight'] for k in range(idx+2)) * w
            min_w = w * 0.01
            new_x = max(left_bound_x + min_w, min(right_bound_x - min_w, x))
            combined_weight = self.items[idx]['weight'] + self.items[idx+1]['weight']
            new_left_width = new_x - left_bound_x
            new_left_weight = new_left_width / w
            self.items[idx]['weight'] = new_left_weight
            self.items[idx+1]['weight'] = combined_weight - new_left_weight
            self.update()
            self.distributionChanged.emit()
            return
        current_x = 0.0
        found = -1
        for i in range(len(self.items) - 1):
            current_x += self.items[i]['weight'] * w
            if abs(x - current_x) < self.handle_width:
                found = i
                break
        if found != self.hovered_handle:
            self.hovered_handle = found
            self.update()
        if self.hovered_handle != -1: self.setCursor(Qt.CursorShape.SplitHCursor)
        else: self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.hovered_handle != -1: self.dragging_handle = self.hovered_handle

    def mouseReleaseEvent(self, event):
        self.dragging_handle = -1
        self.update()

class LegendItem(QWidget):
    toggled = pyqtSignal(str, bool)
    def __init__(self, name, color, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 5)
        self.chk = QCheckBox()
        self.chk.setChecked(True)
        self.chk.toggled.connect(lambda c: self.toggled.emit(name, c))
        layout.addWidget(self.chk)
        lbl_color = QLabel()
        lbl_color.setFixedSize(16, 16)
        lbl_color.setStyleSheet(f"background-color: {color.name()}; border-radius: 8px; border: 1px solid #555;")
        layout.addWidget(lbl_color)
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("font-size: 13px;")
        layout.addWidget(lbl_name)
        layout.addStretch()
        self.name = name

class BatchSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Processing - Setup")
        self.resize(700, 600)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")

        self.settings = QSettings("ProjectDegrader", "BatchConfig")
        self.input_path = self.settings.value("input_path", "")
        self.output_path = self.settings.value("output_path", "")
        self.folder_prefix = self.settings.value("folder_prefix", "")

        self.colors = [QColor("#e57373"), QColor("#ba68c8"), QColor("#64b5f6"), QColor("#4db6ac"), QColor("#fff176"), QColor("#ffb74d"), QColor("#a1887f"), QColor("#90a4ae")]
        self.all_profiles = []
        self.active_profiles_map = {}

        self._init_ui()
        self._load_profiles()
        self._check_ready()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        grp_paths = QFrame()
        grp_paths.setStyleSheet("background-color: #252526; border-radius: 5px;")
        l_paths = QVBoxLayout(grp_paths)

        h1 = QHBoxLayout()
        self.lbl_in = QLabel(self.input_path or "Input: Not selected")
        btn_in = QPushButton("📂 Input")
        btn_in.clicked.connect(self._sel_in)
        h1.addWidget(self.lbl_in, 1)
        h1.addWidget(btn_in)
        l_paths.addLayout(h1)

        h2 = QHBoxLayout()
        self.lbl_out = QLabel(self.output_path or "Output: Not selected")
        btn_out = QPushButton("📂 Output")
        btn_out.clicked.connect(self._sel_out)
        h2.addWidget(self.lbl_out, 1)
        h2.addWidget(btn_out)
        l_paths.addLayout(h2)

        h3 = QHBoxLayout()
        h3.addWidget(QLabel("Префикс папок:"))
        self.edit_prefix = QLineEdit(self.folder_prefix)
        self.edit_prefix.setPlaceholderText("Например: MyDataset (создаст MyDataset_GT и MyDataset_LQ)")
        self.edit_prefix.setStyleSheet("padding: 5px; border: 1px solid #444; border-radius: 3px; background: #333; color: white;")
        h3.addWidget(self.edit_prefix, 1)
        l_paths.addLayout(h3)

        layout.addWidget(grp_paths)
        layout.addWidget(QLabel("Distribution (drag borders):"))
        self.dist_bar = InteractiveDistributionBar()
        self.dist_bar.distributionChanged.connect(self._check_ready)
        layout.addWidget(self.dist_bar)
        layout.addWidget(QLabel("Active profiles:"))
        self.scroll_legend = QScrollArea()
        self.scroll_legend.setWidgetResizable(True)
        self.scroll_legend.setStyleSheet("background: transparent; border: none;")
        self.legend_container = QWidget()
        self.legend_layout = QVBoxLayout(self.legend_container)
        self.scroll_legend.setWidget(self.legend_container)
        layout.addWidget(self.scroll_legend, 1)
        btn_box = QHBoxLayout()
        self.btn_start = QPushButton("🚀 START")
        self.btn_start.setObjectName("GenButton")
        self.btn_start.setFixedHeight(45)
        self.btn_start.clicked.connect(self.save_and_accept)
        self.btn_start.setEnabled(False)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_box.addWidget(btn_cancel)
        btn_box.addWidget(self.btn_start, 1)
        layout.addLayout(btn_box)

    def _load_profiles(self):
        if not config.PROFILES_DIR.exists(): return
        files = sorted(list(config.PROFILES_DIR.glob('*.json')))
        for i, f in enumerate(files):
            name = f.stem
            self.all_profiles.append((name, f))
            self.active_profiles_map[name] = True
            color = self.colors[i % len(self.colors)]
            item = LegendItem(name, color)
            item.toggled.connect(self._on_profile_toggled)
            self.legend_layout.addWidget(item)
        self._refresh_bar()

    def _on_profile_toggled(self, name, is_active):
        self.active_profiles_map[name] = is_active
        self._refresh_bar()

    def _refresh_bar(self):
        active_list = []
        active_colors = []
        for i, (name, _) in enumerate(self.all_profiles):
            if self.active_profiles_map.get(name, False):
                active_list.append(name)
                active_colors.append(self.colors[i % len(self.colors)])
        self.dist_bar.set_items(active_list, active_colors)
        self._check_ready()

    def save_and_accept(self):
        self.settings.setValue("input_path", self.input_path)
        self.settings.setValue("output_path", self.output_path)
        self.settings.setValue("folder_prefix", self.edit_prefix.text())
        self.accept()

    def _sel_in(self):
        d = QFileDialog.getExistingDirectory(self, "Input", self.input_path)
        if d:
            self.input_path = d
            self.lbl_in.setText(f"Input: {d}")
            self._check_ready()

    def _sel_out(self):
        d = QFileDialog.getExistingDirectory(self, "Output", self.output_path)
        if d:
            self.output_path = d
            self.lbl_out.setText(f"Output: {d}")
            self._check_ready()

    def _check_ready(self):
        probs = self.dist_bar.get_probs()
        has_profiles = len(probs['names']) > 0
        ready = bool(self.input_path) and bool(self.output_path) and has_profiles
        self.btn_start.setEnabled(ready)
        if has_profiles:
            self.btn_start.setText(f"🚀 START ({len(probs['names'])} profiles)")
        else:
            self.btn_start.setText("Select profiles")

    def get_configuration(self):
        return {
            'input': self.input_path,
            'output': self.output_path,
            'prefix': self.edit_prefix.text().strip(),
            'probs': self.dist_bar.get_probs()
        }

def _run_batch_task(args):
    try:
        img_path, lq_path, gt_path, seed, probs_config = args

        import config
        from core.pipeline import apply_full_pipeline
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
        import random
        import numpy as np

        config.load_profiles()

        config.PROFILE_PROBABILITIES = probs_config

        t0 = time.time()

        profile_name = "default"
        if config.PROFILE_PROBABILITIES['names']:
            profile_name = random.choices(
                config.PROFILE_PROBABILITIES['names'],
                weights=config.PROFILE_PROBABILITIES['weights'],
                k=1
            )[0]

        p = config.DEGRADATION_PROFILES.get(profile_name, {}).copy()
        p['seed'] = seed

        clean_img = Image.open(img_path).convert('RGB')
        clean_img.save(gt_path)

        lq_img, stats = apply_full_pipeline(clean_img, p)

        meta_data = {
            'origin': img_path.name,
            'profile': profile_name,
            'seed': seed,
            'params': stats
        }
        json_str = json.dumps(meta_data)

        ext = lq_path.suffix.lower()
        if ext == '.png':
            metadata = PngInfo()
            metadata.add_text("DegradationParams", json_str)
            lq_img.save(lq_path, pnginfo=metadata)
        elif ext in ['.jpg', '.jpeg']:
            exif = lq_img.getexif()
            exif[0x010E] = json_str
            lq_img.save(lq_path, exif=exif)
        else:
            lq_img.save(lq_path)

        dt = time.time() - t0

        info_parts = [f"[{profile_name}]"]
        if stats.get('scratch_cnt', 0) > 0: info_parts.append(f"Scr:{stats['scratch_cnt']}")
        if stats.get('debris_cnt', 0) > 0: info_parts.append(f"Deb:{stats['debris_cnt']}")
        if stats.get('blur_rad', 0) > 0: info_parts.append(f"Blur:{stats['blur_rad']:.1f}")
        if stats.get('is_extreme', 0): info_parts.append("!!! EXTREME !!!")

        return (lq_path.name, " ".join(info_parts), dt, str(lq_path), False, stats, str(gt_path))

    except Exception as e:
        err_msg = str(e)
        if not err_msg: err_msg = repr(e)

        return (str(args[0].name) if args else "Unknown", err_msg, 0.0, "", True, {}, "")

class BatchWorker(QThread):
    progress = pyqtSignal(int, int)

    file_finished = pyqtSignal(str, str, float, str, dict, str)
    finished = pyqtSignal()
    stopped = pyqtSignal()

    def __init__(self, conf):
        super().__init__()
        self.conf = conf
        self.is_running = True

    def run(self):
        in_dir = Path(self.conf['input'])
        out_dir = Path(self.conf['output'])
        probs = self.conf['probs']
        prefix = self.conf['prefix']

        gt_folder_name = f"{prefix}_GT" if prefix else "GT"
        lq_folder_name = f"{prefix}_LQ" if prefix else "LQ"

        gt_dir = out_dir / gt_folder_name
        lq_dir = out_dir / lq_folder_name
        gt_dir.mkdir(parents=True, exist_ok=True)
        lq_dir.mkdir(parents=True, exist_ok=True)

        files = sorted([f for f in in_dir.glob('*') if f.suffix.lower() in ['.png', '.jpg', '.jpeg', '.bmp', '.tif']])
        total = len(files)
        if total == 0:
            self.finished.emit()
            return

        random_indices = list(range(1, total + 1))
        random.shuffle(random_indices)

        tasks = []
        for i, img_path in enumerate(files):
            idx = random_indices[i]
            ext = img_path.suffix
            new_filename = f"{idx:06d}{ext}"

            lq_path = lq_dir / new_filename
            gt_path = gt_dir / new_filename

            seed = int(time.time() * 1000) % 999999 + i
            tasks.append((img_path, lq_path, gt_path, seed, probs))

        cpu_count = max(1, multiprocessing.cpu_count() - 1)

        with multiprocessing.Pool(processes=cpu_count) as pool:
            try:
                iterator = pool.imap_unordered(_run_batch_task, tasks)

                for i, result in enumerate(iterator):
                    if not self.is_running:
                        break

                    filename, info, dt, lq_img_path, is_error, stats, gt_img_path = result

                    if is_error:
                        self.file_finished.emit(filename, f"ERROR: {info}", 0.0, "", {}, "")
                    else:
                        self.file_finished.emit(filename, info, dt, lq_img_path, stats, gt_img_path)

                    self.progress.emit(i + 1, total)

                if self.is_running:
                    self.finished.emit()
                else:
                    self.stopped.emit()

            except Exception as e:
                print(f"Main Pool Error: {e}")
                self.stopped.emit()

    def stop(self):
        self.is_running = False

class CompactViewerSettings(QWidget):
    settings_changed = pyqtSignal(int, int, int)
    speed_changed = pyqtSignal(float)
    magnifier_toggled = pyqtSignal(bool)
    freeze_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("ProjectDegrader", "ViewerState")

        layout = QGridLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(5)

        r = self.settings.value("magnifier_radius", 150, type=int)
        c = self.settings.value("magnifier_capture", 15, type=int)
        s = self.settings.value("magnifier_speed", 50, type=int)

        self.sl_radius = self._make_slider(50, 400, r)
        self.lbl_radius = self._make_label(f"R: {r}px")

        self.sl_capture = self._make_slider(5, 50, c)
        self.lbl_capture = self._make_label(f"Zoom: {c}%")

        self.sl_speed = self._make_slider(10, 200, s)
        self.lbl_speed = self._make_label(f"Spd: {s/100:.1f}x")

        layout.addWidget(self.sl_radius, 0, 0)
        layout.addWidget(self.lbl_radius, 1, 0)

        layout.addWidget(self.sl_capture, 0, 1)
        layout.addWidget(self.lbl_capture, 1, 1)

        layout.addWidget(self.sl_speed, 0, 2)
        layout.addWidget(self.lbl_speed, 1, 2)

        self.cb_enable = QCheckBox("Magnifier")
        self.cb_freeze = QCheckBox("Freeze")
        self.cb_enable.setChecked(False)
        self.cb_freeze.setEnabled(False)

        chk_style = "QCheckBox { font-size: 11px; margin-left: 5px; }"
        self.cb_enable.setStyleSheet(chk_style)
        self.cb_freeze.setStyleSheet(chk_style)

        layout.addWidget(self.cb_enable, 0, 3)
        layout.addWidget(self.cb_freeze, 1, 3)

        self.sl_radius.valueChanged.connect(self._update)
        self.sl_capture.valueChanged.connect(self._update)
        self.sl_speed.valueChanged.connect(self._update)
        self.cb_enable.toggled.connect(self._on_enable_toggled)
        self.cb_freeze.toggled.connect(self.freeze_toggled.emit)

    def _make_slider(self, min_v, max_v, val):
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(min_v, max_v)
        sl.setValue(val)
        sl.setFixedWidth(80)
        return sl

    def _make_label(self, text):
        l = QLabel(text)
        l.setStyleSheet("color: #aaa; font-size: 10px;")
        l.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return l

    def _on_enable_toggled(self, checked):
        self.cb_freeze.setEnabled(checked)
        self.magnifier_toggled.emit(checked)

    def _update(self):
        r = self.sl_radius.value()
        c = self.sl_capture.value()
        s = self.sl_speed.value()

        self.lbl_radius.setText(f"R: {r}px")
        self.lbl_capture.setText(f"Zoom: {c}%")
        self.lbl_speed.setText(f"Spd: {s/100:.1f}x")

        self.settings.setValue("magnifier_radius", r)
        self.settings.setValue("magnifier_capture", c)
        self.settings.setValue("magnifier_speed", s)

        self.settings_changed.emit(r, c, 1)
        self.speed_changed.emit(s / 100.0)

class BatchExecutionView(QWidget):
    stop_requested = pyqtSignal()
    stats_received = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 20)
        layout.setSpacing(10)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setSpacing(10)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_pause = QPushButton("⏸ PAUSE")
        self.btn_pause.setCheckable(True)
        self.btn_pause.setFixedSize(120, 40)
        self.btn_pause.setStyleSheet("""
            QPushButton { background-color: #0277BD; color: white; font-weight: bold; border-radius: 4px; }
            QPushButton:checked { background-color: #F57C00; }
        """)
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_prev = QPushButton("◀")
        self.btn_prev.setFixedSize(30, 40)
        self.btn_prev.clicked.connect(lambda: self.navigate(-1))

        self.btn_next = QPushButton("▶")
        self.btn_next.setFixedSize(30, 40)
        self.btn_next.clicked.connect(lambda: self.navigate(1))

        self.lbl_history_idx = QLabel("")
        self.lbl_history_idx.setStyleSheet("color: #aaa; font-size: 12px; font-weight: bold;")
        self.lbl_history_idx.setFixedWidth(60)
        self.lbl_history_idx.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_bar_layout.addWidget(self.btn_pause)
        top_bar_layout.addWidget(self.btn_prev)
        top_bar_layout.addWidget(self.lbl_history_idx)
        top_bar_layout.addWidget(self.btn_next)

        self.compact_settings = CompactViewerSettings()
        self.compact_settings.setVisible(False)

        top_bar_layout.addWidget(self.compact_settings)
        top_bar_layout.addStretch()

        layout.addLayout(top_bar_layout)

        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #252526; border-radius: 5px;")
        stats_layout = QHBoxLayout(stats_frame)
        self.lbl_counter = QLabel("0 / 0")
        self.lbl_speed = QLabel("0.0 img/s")
        self.lbl_eta = QLabel("ETA: --:--")
        for l in [self.lbl_counter, self.lbl_speed, self.lbl_eta]:
            l.setStyleSheet("font-size: 16px; font-weight: bold; color: #ddd;")
            stats_layout.addWidget(l)
        layout.addWidget(stats_frame)

        self.pbar = QProgressBar()
        self.pbar.setFixedHeight(8)
        self.pbar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        layout.addWidget(self.pbar)

        self.viewer = ComparisonViewer()
        layout.addWidget(self.viewer, 1)

        self.compact_settings.settings_changed.connect(self.viewer.set_magnifier_params)
        self.compact_settings.speed_changed.connect(self.viewer.set_move_speed)
        self.compact_settings.magnifier_toggled.connect(self.viewer.toggle_magnifier)
        self.compact_settings.freeze_toggled.connect(self.viewer.toggle_freeze)

        self.list_log = QListWidget()
        self.list_log.setFixedHeight(100)
        self.list_log.setStyleSheet("background-color: #111; border: 1px solid #444; font-size: 10px;")
        layout.addWidget(self.list_log)

        self.btn_stop = QPushButton("⏹ STOP BATCH")
        self.btn_stop.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold; padding: 10px;")
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        layout.addWidget(self.btn_stop)

        self.start_time = 0
        self.history = []
        self.is_paused = False
        self.current_history_index = -1
        self.last_auto_preview_time = 0

        self.btn_prev.setVisible(False)
        self.btn_next.setVisible(False)

        QTimer.singleShot(0, self.compact_settings._update)

    def reset(self):
        self.pbar.setValue(0)
        self.list_log.clear()
        self.viewer.set_images(None, None)
        self.viewer.update()

        self.start_time = time.time()
        self.last_auto_preview_time = 0
        self.lbl_counter.setText("0 / 0")
        self.btn_stop.setEnabled(True)
        self.btn_stop.setText("⏹ STOP BATCH")

        self.history = []
        self.is_paused = False
        self.current_history_index = -1
        self.btn_pause.setChecked(False)
        self.btn_pause.setText("⏸ PAUSE")
        self.btn_prev.setVisible(False)
        self.btn_next.setVisible(False)
        self.lbl_history_idx.setText("")

        self.compact_settings.setVisible(False)

    def toggle_pause(self):
        self.is_paused = self.btn_pause.isChecked()

        self.compact_settings.setVisible(self.is_paused)

        if self.is_paused:
            self.btn_pause.setText("▶ RESUME")
            self.btn_prev.setVisible(True)
            self.btn_next.setVisible(True)

            if self.history and self.current_history_index == -1:
                self.current_history_index = len(self.history) - 1

            self._update_nav_ui()
            self._show_history_item(self.current_history_index)
        else:
            self.btn_pause.setText("⏸ PAUSE")
            self.btn_prev.setVisible(False)
            self.btn_next.setVisible(False)
            self.lbl_history_idx.setText("")
            self.current_history_index = len(self.history) - 1

            if self.compact_settings.cb_enable.isChecked():
                self.compact_settings.cb_enable.setChecked(False)

    def navigate(self, delta):
        if not self.history: return
        new_idx = self.current_history_index + delta
        if 0 <= new_idx < len(self.history):
            self.current_history_index = new_idx
            self._show_history_item(new_idx)
            self._update_nav_ui()

    def _update_nav_ui(self):
        if not self.history:
            self.lbl_history_idx.setText("No images")
            self.btn_prev.setEnabled(False)
            self.btn_next.setEnabled(False)
            return

        idx = self.current_history_index + 1
        total = len(self.history)
        self.lbl_history_idx.setText(f"{idx} / {total}")
        self.btn_prev.setEnabled(self.current_history_index > 0)
        self.btn_next.setEnabled(self.current_history_index < total - 1)

    def _show_history_item(self, index):
        if index < 0 or index >= len(self.history): return

        item = self.history[index]
        lq_path = item['lq_path']
        gt_path = item['gt_path']
        stats = item['stats']

        self.stats_received.emit(stats)

        try:
            pil_lq = None
            pil_gt = None

            if os.path.exists(lq_path):
                pil_lq = Image.open(lq_path).convert("RGBA")

            if gt_path and os.path.exists(gt_path):
                pil_gt = Image.open(gt_path).convert("RGBA")
            else:

                pil_gt = pil_lq

            self.viewer.set_images(pil_gt, pil_lq)

        except Exception as e:
            print(f"Error loading preview: {e}")

    def update_progress(self, current, total):
        self.pbar.setRange(0, total)
        self.pbar.setValue(current)
        self.lbl_counter.setText(f"{current} / {total}")
        elapsed = time.time() - self.start_time
        if elapsed > 0 and current > 0:
            speed = current / elapsed
            self.lbl_speed.setText(f"{speed:.2f} img/s")
            remaining = total - current
            self.lbl_eta.setText(f"ETA: {int(remaining/speed)//60:02d}:{int(remaining/speed)%60:02d}")

    def update_file_info(self, filename, profile, dt, lq_path, stats, gt_path):

        item = QListWidgetItem(f"[{dt:.2f}s] {filename} -> {profile}")
        item.setForeground(QColor("#ff5252") if "ERROR" in profile else QColor("#81c784"))
        self.list_log.addItem(item)
        self.list_log.scrollToBottom()

        history_item = {
            'filename': filename,
            'lq_path': lq_path,
            'gt_path': gt_path,
            'stats': stats,
            'profile': profile
        }
        self.history.append(history_item)

        if not self.is_paused:
            self.current_history_index = len(self.history) - 1
            now = time.time()

            if now - self.last_auto_preview_time >= 0.2:
                self._show_history_item(self.current_history_index)
                self.last_auto_preview_time = now
        else:

            self._update_nav_ui()
