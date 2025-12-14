from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout,
                             QCheckBox, QLabel, QHBoxLayout, QSlider, QSpinBox,
                             QPushButton, QComboBox, QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QSettings
import json
import random
import math
from pathlib import Path
import config

class ViewerSettingsPanel(QWidget):
    settings_changed = pyqtSignal(int, int, int)
    speed_changed = pyqtSignal(float)
    magnifier_toggled = pyqtSignal(bool)
    freeze_toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("ProjectDegrader", "ViewerState")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)

        gb = QGroupBox("🔍 Tools")
        gb_layout = QFormLayout()
        gb_layout.setSpacing(8)
        gb.setLayout(gb_layout)

        saved_radius = self.settings.value("magnifier_radius", 150, type=int)
        saved_capture = self.settings.value("magnifier_capture", 15, type=int)
        saved_speed = self.settings.value("magnifier_speed", 50, type=int)
        saved_interp = self.settings.value("magnifier_interp", 1, type=int)

        self.cb_enable = QCheckBox("Enable Magnifier")
        self.cb_freeze = QCheckBox("Freeze")
        h = QHBoxLayout()
        h.addWidget(self.cb_enable)
        h.addWidget(self.cb_freeze)
        gb_layout.addRow(h)

        self.sl_radius = self._make_slider(50, 400, saved_radius)
        self.lbl_radius = QLabel(f"{saved_radius} px")
        h1 = QHBoxLayout()
        h1.addWidget(self.sl_radius)
        h1.addWidget(self.lbl_radius)
        gb_layout.addRow("Magnifier Size", h1)

        self.sl_capture = self._make_slider(5, 50, saved_capture)
        self.lbl_capture = QLabel(f"{saved_capture}%")
        h2 = QHBoxLayout()
        h2.addWidget(self.sl_capture)
        h2.addWidget(self.lbl_capture)
        gb_layout.addRow("Capture Size", h2)

        self.sl_speed = self._make_slider(10, 200, saved_speed)
        self.lbl_speed = QLabel(f"{saved_speed/100:.1f}x")
        h3 = QHBoxLayout()
        h3.addWidget(self.sl_speed)
        h3.addWidget(self.lbl_speed)
        gb_layout.addRow("Speed", h3)

        self.cb_interp = QComboBox()
        self.cb_interp.addItems(["Nearest", "Bilinear", "Bicubic", "Lanczos"])
        self.cb_interp.setCurrentIndex(saved_interp)
        gb_layout.addRow("Interpolation", self.cb_interp)

        layout.addWidget(gb)

        self.cb_enable.toggled.connect(self.magnifier_toggled.emit)
        self.cb_enable.toggled.connect(lambda v: self.cb_freeze.setEnabled(v))
        self.cb_freeze.setEnabled(False)
        self.cb_freeze.toggled.connect(self.freeze_toggled.emit)

        self.sl_radius.valueChanged.connect(self._update)
        self.sl_capture.valueChanged.connect(self._update)
        self.sl_speed.valueChanged.connect(self._update)
        self.cb_interp.currentIndexChanged.connect(self._update)

    def _make_slider(self, min_v, max_v, val):
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(min_v, max_v)
        sl.setValue(val)
        return sl

    def _update(self):
        r = self.sl_radius.value()
        c = self.sl_capture.value()
        s = self.sl_speed.value()
        i = self.cb_interp.currentIndex()

        self.lbl_radius.setText(f"{r} px")
        self.lbl_capture.setText(f"{c}%")
        self.lbl_speed.setText(f"{s/100:.1f}x")

        self.settings.setValue("magnifier_radius", r)
        self.settings.setValue("magnifier_capture", c)
        self.settings.setValue("magnifier_speed", s)
        self.settings.setValue("magnifier_interp", i)

        self.settings_changed.emit(r, c, i)
        self.speed_changed.emit(s / 100.0)

class SettingsPanel(QWidget):
    request_mask_preview = pyqtSignal(float)
    clear_mask_preview = pyqtSignal()
    request_solo_gen = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(10)

        self.widgets = {}
        self.scales = {}
        self.group_dependencies = {}

        self.last_loaded_state = {}
        self._prev_combo_index = -1
        self._ignore_change_events = True

        self._init_profile_manager()
        self._init_ui()
        self.layout.addStretch()

        self.last_loaded_state = self.get_profile()
        self.refresh_profiles_list()
        self._ignore_change_events = False

    def _init_profile_manager(self):
        pm_widget = QWidget()
        pm_layout = QHBoxLayout(pm_widget)
        pm_layout.setContentsMargins(0, 0, 0, 5)

        self.combo_profiles = QComboBox()
        self.combo_profiles.setMinimumHeight(28)
        self.combo_profiles.currentIndexChanged.connect(self._on_profile_combo_changed)

        btn_new = QPushButton("➕")
        btn_new.setToolTip("Create new profile")
        btn_new.setFixedSize(28, 28)
        btn_new.clicked.connect(self._quick_create_profile)

        btn_delete = QPushButton("🗑️")
        btn_delete.setToolTip("Delete selected profile")
        btn_delete.setFixedSize(28, 28)
        btn_delete.clicked.connect(self._delete_selected_profile)

        btn_save = QPushButton("💾")
        btn_save.setToolTip("Save current profile")
        btn_save.setFixedSize(28, 28)
        btn_save.clicked.connect(self._quick_save_current_profile)

        btn_refresh = QPushButton("🔄")
        btn_refresh.setToolTip("Refresh list from folder")
        btn_refresh.setFixedSize(28, 28)
        btn_refresh.clicked.connect(self.refresh_profiles_list)

        pm_layout.addWidget(QLabel("Profile:"))
        pm_layout.addWidget(self.combo_profiles, 1)
        pm_layout.addWidget(btn_new)
        pm_layout.addWidget(btn_delete)
        pm_layout.addWidget(btn_save)
        pm_layout.addWidget(btn_refresh)

        self.layout.addWidget(pm_widget)

    def refresh_profiles_list(self):
        if not self._ignore_change_events:
            if not self.check_unsaved_changes():
                return
        self.combo_profiles.blockSignals(True)
        self.combo_profiles.clear()
        if config.PROFILES_DIR.exists():
            files = sorted(list(config.PROFILES_DIR.glob('*.json')))
            for f in files:
                self.combo_profiles.addItem(f.stem, str(f))
        if self.combo_profiles.count() > 0:
            self.combo_profiles.setCurrentIndex(0)
            self._prev_combo_index = 0
            path = self.combo_profiles.currentData()
            self._load_profile_internal(path)
        else:
            self._prev_combo_index = -1
        self.combo_profiles.blockSignals(False)

    def _on_profile_combo_changed(self, index):
        if self._ignore_change_events:
            return
        if index < 0: return
        if not self.check_unsaved_changes():
            self._ignore_change_events = True
            self.combo_profiles.setCurrentIndex(self._prev_combo_index)
            self._ignore_change_events = False
            return
        path = self.combo_profiles.currentData()
        if path:
            self._prev_combo_index = index
            self._load_profile_internal(path)

    def _quick_create_profile(self):
        if not self.check_unsaved_changes():
            return
        name, ok = QInputDialog.getText(self, "New Profile", "Enter profile name:")
        if ok and name:
            safe_name = "".join(x for x in name if x.isalnum() or x in " _-").strip()
            if not safe_name: return
            path = config.PROFILES_DIR / f"{safe_name}.json"
            self.save_profile_json(path)
            self.refresh_profiles_list()
            index = self.combo_profiles.findText(safe_name)
            if index >= 0:
                self.combo_profiles.setCurrentIndex(index)

    def _quick_save_current_profile(self):
        index = self.combo_profiles.currentIndex()
        if index < 0: return
        path = Path(self.combo_profiles.currentData())
        name = self.combo_profiles.currentText()
        reply = QMessageBox.question(self, "Save",
                                   f"Overwrite profile '{name}'?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.save_profile_json(path)

    def _delete_selected_profile(self):
        index = self.combo_profiles.currentIndex()
        if index < 0:
            QMessageBox.warning(self, "Delete Profile", "First select a profile to delete")
            return
        path = Path(self.combo_profiles.currentData())
        name = self.combo_profiles.currentText()
        reply = QMessageBox.question(self, "Delete Profile",
                                   f"Are you sure you want to delete profile '{name}'?\n\nThis action cannot be undone.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if path.exists():
                    path.unlink()
                self.refresh_profiles_list()
                QMessageBox.information(self, "Delete Profile", f"Profile '{name}' successfully deleted")
            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete profile '{name}':\n{str(e)}")

    def _load_profile_from_path(self, path):
        self._load_profile_internal(path)

    def _load_profile_internal(self, path):
        old_state = self._ignore_change_events
        self._ignore_change_events = True
        self.load_profile_json(path)
        self.last_loaded_state = self.get_profile()
        self._ignore_change_events = old_state

    def _init_ui(self):

        g_main = self._add_group("0. Generation (Seed)")
        seed_widget = QWidget()
        seed_layout = QHBoxLayout(seed_widget)
        seed_layout.setContentsMargins(0,0,0,0)
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 999999999)
        self.seed_spin.setValue(42)
        self.seed_spin.setStyleSheet("padding: 5px;")
        btn_rand = QPushButton("🎲 Rand")
        btn_rand.setFixedWidth(60)
        btn_rand.clicked.connect(lambda: self.seed_spin.setValue(random.randint(0, 999999)))
        seed_layout.addWidget(self.seed_spin)
        seed_layout.addWidget(btn_rand)
        g_main.addRow("Seed:", seed_widget)

        g1 = self._add_group("1. Scene Analysis", master_key="flat_areas_enabled")
        self._register_dep("flat_areas_enabled", ["flat_area_threshold", "flat_area_defect_bias"])

        rs = self._add_range(g1, "flat_area_threshold", "Threshold", 0, 500, (100, 100), 0.1)
        rs.interactionStarted.connect(self.clear_mask_preview.emit)

        self._add_range(g1, "flat_area_defect_bias", "Defect Bias", 0, 50, (15, 15), 0.1)
        self._add_range(g1, "flat_area_grain_bias", "Grain Bias", 0, 30, (13, 13), 0.1)
        self._add_range(g1, "flat_area_exposure", "Exposure", -50, 50, (2, 2), 0.01)

        g2 = self._add_group("2. Scratches", master_key="grp_scratches")
        self._register_dep("grp_scratches", "scratches_probability")

        self._add_prob(g2, "scratches_probability", "Probability", 1.0)
        self._add_range(g2, "scratches_count", "Count", 0, 100, (1, 5))
        self._add_range(g2, "scratches_size", "Length (px)", 10, 500, (20, 100))
        self._add_range(g2, "scratches_intensity", "Opacity", -100, 100, (10, 20), 0.01)

        g3 = self._add_group("3. Debris & Dust", master_key="grp_debris")
        self._register_dep("grp_debris", ["debris_probability", "micro_defects_probability"])

        self._add_prob(g3, "debris_probability", "Debris Prob", 1.0)
        self._add_range(g3, "debris_count", "Count", 0, 200, (5, 20))
        self._add_range(g3, "debris_intensity", "Intensity", 0, 100, (20, 40), 0.01)

        self._add_prob(g3, "micro_defects_probability", "Micro Prob", 1.0)
        self._add_range(g3, "micro_dust_count", "Micro Dust", 0, 200, (10, 30))
        self._add_range(g3, "micro_smudge_count", "Micro Smudges", 0, 100, (5, 15))
        self._add_range(g3, "micro_intensity", "Micro Intensity", 0, 100, (5, 15), 0.01)

        g4 = self._add_group("4. Stains", master_key="grp_stains")
        self._register_dep("grp_stains", ["large_stain_probability", "fine_speckle_probability"])

        self._add_prob(g4, "large_stain_probability", "Stain Prob", 0.0)
        self._add_range(g4, "large_stain_strength_range", "Stain Strength", 0, 100, (10, 20), 0.01)

        self._add_prob(g4, "fine_speckle_probability", "Speckle Prob", 1.0)
        self._add_range(g4, "fine_speckle_strength_range", "Speckle Strength", 0, 100, (20, 30), 0.01)

        g5 = self._add_group("5. Geometry", master_key="grp_geo")
        self._register_dep("grp_geo", ["crease_probability", "emulsion_shift_probability"])

        self._add_prob(g5, "crease_probability", "Crease Prob", 0.0)
        self._add_range(g5, "crease_line_spacing_range", "Line Spacing", 2, 100, (10, 20))
        self._add_range(g5, "crease_displacement_range", "Distortion", 0, 20, (1, 2))
        self._add_range(g5, "crease_darken_strength", "Darkening", 0, 50, (5, 10), 0.01)
        self._add_range(g5, "crease_color_shift_strength", "Color Shift (Crease)", 0, 50, (0, 5), 0.01)

        self._add_prob(g5, "emulsion_shift_probability", "Shift Prob", 0.0)
        self._add_range(g5, "emulsion_shift_range", "Shift (px)", 0, 20, (1, 3))

        g6 = self._add_group("6. Emulsion", master_key="grp_emul")
        self._register_dep("grp_emul", "emulsion_degradation_probability")

        self._add_prob(g6, "emulsion_degradation_probability", "Degradation Prob", 1.0)
        self._add_range(g6, "emulsion_degradation_strength", "Strength", 0, 200, (20, 40))
        self._add_range(g6, "emulsion_degradation_mix_ratio", "Mix Ratio", 0, 100, (30, 50), 0.01)

        g7 = self._add_group("7. Grain", master_key="grp_grain")
        self._register_dep("grp_grain", ["grain_enabled", "texture_trap_probability"])

        self._add_check(g7, "grain_enabled", "Enable Grain", True)
        self._add_range(g7, "grain_strength_range", "Grain Strength", 0, 100, (5, 8), 1.0)
        self._add_range(g7, "grain_emphasis_on_color", "Color Emphasis", 0, 300, (110, 130), 0.01)

        self._add_prob(g7, "grain_monochrome_probability", "Monochrome Prob", 0.0)

        self._add_prob(g7, "texture_trap_probability", "Trap Prob", 0.0)
        self._add_range(g7, "texture_trap_intensity", "Trap Intensity", 0, 100, (4, 8), 0.01)

        g9 = self._add_group("9. Banding (Gradients)", master_key="grp_banding", default=False)
        self._register_dep("grp_banding", ["banding_probability"])

        self._add_prob(g9, "banding_probability", "Probability", 0.3)

        self._add_range(g9, "banding_levels", "Levels (Lower=Worse)", 5, 200, (30, 80))

        self._add_range(g9, "banding_opacity", "Opacity", 0, 100, (80, 100), 0.01)

        g8 = self._add_group("8. Final / Post", master_key="grp_post")
        self._register_dep("grp_post", ["blur_enabled", "blur_probability", "mpeg_probability", "extreme_mode"])

        self._add_check(g8, "blur_enabled", "Enable Blur", False)
        self._add_prob(g8, "blur_probability", "Blur Chance", 0.5)
        self._add_range(g8, "blur_range", "Blur Strength", 0, 50, (0, 5), 0.1)

        self._add_prob(g8, "mpeg_probability", "MPEG Prob", 0.0)
        self._add_range(g8, "mpeg_quality_range", "Quality (Quantizer)", 1, 31, (2, 8))

        self._add_check(g8, "extreme_mode", "EXTREME MODE", False)

        self._register_dep("extreme_mode", [
            "extreme_mode_probability",
            "extreme_strength_range",
            "extreme_cast_range"
        ])

        self._add_prob(g8, "extreme_mode_probability", "Probability", 0.0)

        self._add_range(g8, "extreme_strength_range", "Strength Mult (x)", 100, 500, (150, 300), 0.01)

        self._add_range(g8, "extreme_cast_range", "Cast Strength", 100, 400, (150, 250), 0.01)

        self._add_prob(g8, "color_cast_probability", "Tint Prob (Batch)", 0.0)

    def _add_group(self, title, master_key=None, default=True):
        gb = QGroupBox()

        if master_key:
            check = QCheckBox(title)
            check.setChecked(default)
            check.setStyleSheet("""
                QCheckBox { font-weight: bold; font-size: 13px; color: #4CAF50; }
                QCheckBox::indicator { width: 16px; height: 16px; }
            """)
            gb.setTitle("")

            gb_main_layout = QVBoxLayout()
            gb_main_layout.setContentsMargins(5, 5, 5, 5)
            gb_main_layout.addWidget(check)

            lay = QFormLayout()
            lay.setSpacing(4)
            lay.setContentsMargins(10, 0, 5, 5)

            gb_main_layout.addLayout(lay)
            gb.setLayout(gb_main_layout)

            self.widgets[master_key] = check

            def toggle_content(checked):
                for i in range(lay.count()):
                    w = lay.itemAt(i).widget()
                    if w: w.setEnabled(checked)
            check.toggled.connect(toggle_content)

        else:
            gb.setTitle(title)
            lay = QFormLayout()
            lay.setSpacing(2)
            gb.setLayout(lay)

        self.layout.addWidget(gb)
        return lay

    def _register_dep(self, master, slaves):
        if not isinstance(slaves, list): slaves = [slaves]
        self.group_dependencies[master] = slaves

    def _add_check(self, layout, key, title, default):
        cb = QCheckBox()
        cb.setChecked(default)
        layout.addRow(title, cb)
        self.widgets[key] = cb
        return cb

    def _add_prob(self, layout, key, title, default=1.0):
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0, 0, 0, 0)

        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(0, 100)
        val_int = int(default * 100)
        sl.setValue(val_int)

        lbl = QLabel(f"{val_int}%")
        lbl.setFixedWidth(40)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color: #4CAF50; font-weight: bold;" if val_int > 0 else "color: #777;")

        def update_text(val):
            lbl.setText(f"{val}%")
            if val == 0: lbl.setStyleSheet("color: #777;")
            else: lbl.setStyleSheet("color: #4CAF50; font-weight: bold;")

        sl.valueChanged.connect(update_text)

        l.addWidget(sl)
        l.addWidget(lbl)
        layout.addRow(title, w)
        self.widgets[key] = sl
        return sl

    def _add_range(self, layout, key, title, min_v, max_v, default_tuple, scale=1.0):
        from .widgets import RangeSlider
        w = QWidget()
        l = QHBoxLayout(w)
        l.setContentsMargins(0,0,0,0)
        rs = RangeSlider(min_v, max_v)
        rs.set_range(default_tuple[0], default_tuple[1])

        val_lbl = QLabel()
        val_lbl.setFixedWidth(70)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        val_lbl.setStyleSheet("color: #aaa; font-size: 11px;")

        def update_lbl(low, high):
            if scale == 1.0:
                txt = f"{low}" if low == high else f"{low}-{high}"
            else:
                txt = f"{low*scale:.2f}" if low == high else f"{low*scale:.2f}-{high*scale:.2f}"
            val_lbl.setText(txt)

        rs.valueChanged.connect(update_lbl)
        update_lbl(default_tuple[0], default_tuple[1])

        rs.previewRequested.connect(lambda v, k=key, s=scale: self._on_range_preview_click(k, v, s))

        l.addWidget(rs)
        l.addWidget(val_lbl)

        layout.addRow(title, w)

        self.widgets[key] = rs
        self.scales[key] = scale
        return rs

    def get_profile(self):
        p = {'name': "Custom", 'seed': self.seed_spin.value()}
        for key, w in self.widgets.items():
            if isinstance(w, QCheckBox):
                if key.startswith('grp_'): p[key] = w.isChecked()
                else: p[key] = w.isChecked()
            elif isinstance(w, QSlider):
                p[key] = w.value() / 100.0
            elif hasattr(w, 'low'):
                s = self.scales.get(key, 1.0)
                p[key] = (float(w.low) * s, float(w.high) * s)

        return p

    def get_smart_profile(self, last_profile, last_seeds):
        current_profile = self.get_profile()
        new_seeds = {}

        groups = [
            'scratches', 'debris', 'micro', 'stains',
            'emulsion', 'grain', 'geometry', 'post'
        ]

        for effect in groups:
            if last_seeds and effect in last_seeds:
                new_seeds[effect] = last_seeds[effect]
            else:
                new_seeds[effect] = random.randint(0, 999999999)

        current_profile['seed_map'] = new_seeds
        return current_profile, new_seeds

    def _profiles_are_equal(self, p1, p2):
        if p1 is None or p2 is None: return False

        keys1 = set(k for k in p1.keys() if k != 'name')
        keys2 = set(k for k in p2.keys() if k != 'name')

        if keys1 != keys2: return False

        for k in keys1:
            v1 = p1[k]
            v2 = p2[k]

            if isinstance(v1, (list, tuple)) and isinstance(v2, (list, tuple)):
                if len(v1) != len(v2): return False
                for i in range(len(v1)):
                    if isinstance(v1[i], float) or isinstance(v2[i], float):
                        if abs(v1[i] - v2[i]) > 0.0001: return False
                    elif v1[i] != v2[i]: return False

            elif isinstance(v1, float) or isinstance(v2, float):
                if abs(v1 - v2) > 0.0001: return False

            elif v1 != v2:
                return False

        return True

    def check_unsaved_changes(self):
        if self._ignore_change_events:
            return True

        current_state = self.get_profile()

        if self._profiles_are_equal(current_state, self.last_loaded_state):
            return True

        reply = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Profile settings have been changed.\nSave before switching?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Yes:
            self._quick_save_current_profile()
            self.last_loaded_state = self.get_profile()
            return True
        elif reply == QMessageBox.StandardButton.No:
            return True
        else:
            return False

    def save_profile_json(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        data = self.get_profile()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.last_loaded_state = self.get_profile()
        except Exception as e:
            print(f"Error saving profile: {e}")

    def load_profile_json(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'grain_monochrome_probability' not in data:
                data['grain_monochrome_probability'] = 0.0

            if 'seed' in data: self.seed_spin.setValue(int(data['seed']))

            for key, val in data.items():
                if key in self.widgets:
                    w = self.widgets[key]
                    if isinstance(w, QCheckBox):
                        w.setChecked(bool(val))
                    elif isinstance(w, QSlider):
                        w.setValue(int((float(val) * 100) if not isinstance(val, bool) else (100 if val else 0)))
                    elif hasattr(w, 'low'):
                        s = self.scales.get(key, 1.0)

                        def to_slider(v):
                            if s == 0: return int(v)
                            slider_pos = int(round(v / s))
                            if v > 0 and slider_pos == 0: slider_pos = 1
                            if v < 0 and slider_pos == 0: slider_pos = -1
                            return slider_pos

                        if isinstance(val, (list, tuple)):
                            w.set_range(to_slider(val[0]), to_slider(val[1]))
                        else:
                            w.set_range(to_slider(val), to_slider(val))

                        w.valueChanged.emit(int(w.low), int(w.high))

            for master, slaves in self.group_dependencies.items():
                if master in data:
                    self.widgets[master].setChecked(bool(data[master]))

        except Exception as e:
            print(f"Error loading: {e}")

    def _on_range_preview_click(self, key, val, scale):
        real_val = val * scale

        if key == 'flat_area_threshold':
            self.request_mask_preview.emit(real_val)
            return

        solo = self.get_profile()
        solo['name'] = f"SOLO: {key}"

        if 'extreme' not in key:
            solo['extreme_mode'] = False

        target = None
        if 'blur' in key: target = 'blur'
        elif 'grain' in key or 'trap' in key: target = 'grain'
        elif 'flat' in key: target = 'flat'
        elif 'banding' in key: target = 'banding'
        elif 'extreme' in key: target = 'extreme'

        if target != 'blur': solo['blur_enabled'] = False
        if target != 'grain': solo['grain_enabled'] = False
        if target != 'flat': solo['flat_areas_enabled'] = False
        if target != 'banding': solo['grp_banding'] = False

        all_probs = [k for k in solo.keys() if 'probability' in k]

        group_id = None
        if 'scratches' in key: group_id = 'scratches'
        elif 'debris' in key: group_id = 'debris'
        elif 'micro' in key: group_id = 'micro'
        elif 'stain' in key: group_id = 'stain'
        elif 'speckle' in key: group_id = 'speckle'
        elif 'crease' in key: group_id = 'crease'
        elif 'shift' in key: group_id = 'shift'
        elif 'emulsion' in key: group_id = 'emulsion'
        elif 'mpeg' in key: group_id = 'mpeg'
        elif 'trap' in key: group_id = 'trap'
        elif 'banding' in key: group_id = 'banding'
        elif 'extreme' in key: group_id = 'extreme'

        for prob_key in all_probs:
            if group_id and group_id not in prob_key:
                solo[prob_key] = 0.0
            elif not group_id:

                solo[prob_key] = 0.0

        if group_id == 'scratches': solo['scratches_probability'] = 1.0
        elif group_id == 'debris': solo['debris_probability'] = 1.0
        elif group_id == 'micro': solo['micro_defects_probability'] = 1.0
        elif group_id == 'stain': solo['large_stain_probability'] = 1.0
        elif group_id == 'speckle': solo['fine_speckle_probability'] = 1.0
        elif group_id == 'crease': solo['crease_probability'] = 1.0
        elif group_id == 'shift': solo['emulsion_shift_probability'] = 1.0
        elif group_id == 'emulsion': solo['emulsion_degradation_probability'] = 1.0
        elif group_id == 'mpeg': solo['mpeg_probability'] = 1.0
        elif group_id == 'trap': solo['texture_trap_probability'] = 1.0
        elif group_id == 'banding': solo['banding_probability'] = 1.0

        elif group_id == 'extreme':
            solo['extreme_mode'] = True
            solo['extreme_mode_probability'] = 1.0
            solo['grp_post'] = True

            if 'cast' in key:

                solo['color_cast_probability'] = 1.0

            elif 'strength' in key:

                solo['grp_emul'] = True
                solo['emulsion_degradation_probability'] = 1.0

                solo['grp_grain'] = True
                solo['grain_enabled'] = True

                solo['grain_strength_range'] = (5.0, 5.0)

        if group_id in ['crease', 'shift']: solo['grp_geo'] = True
        elif group_id == 'emulsion': solo['grp_emul'] = True
        elif group_id in ['scratches']: solo['grp_scratches'] = True
        elif group_id in ['debris', 'micro']: solo['grp_debris'] = True
        elif group_id in ['stain', 'speckle']: solo['grp_stains'] = True
        elif group_id == 'mpeg': solo['grp_post'] = True
        elif group_id == 'trap': solo['grp_grain'] = True
        elif group_id == 'banding': solo['grp_banding'] = True

        solo[key] = (real_val, real_val)

        if 'blur' in key:
            solo['blur_enabled'] = True
            solo['grp_post'] = True
        elif 'banding' in key:
            solo['grp_banding'] = True

        self.request_solo_gen.emit(solo)
