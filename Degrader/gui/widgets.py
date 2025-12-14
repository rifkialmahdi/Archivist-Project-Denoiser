import math
from PyQt6.QtCore import Qt, QPoint, QRect, QPointF, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QImage, QPixmap, QPainter, QColor, QPen, QPainterPath, QBrush, QFont
from PyQt6.QtWidgets import QWidget, QApplication, QLabel, QHBoxLayout, QVBoxLayout
from PIL import Image

class ComparisonViewer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

        self.pixmap_original = None
        self.pixmap_processed = None
        self.pil_original = None
        self.pil_processed = None

        self.mask_overlay = None

        self.is_magnifier_enabled = False
        self.is_magnifier_frozen = False
        self.split_pos = 0.5

        self.capture_pos_rel = QPointF(0.5, 0.5)
        self.magnifier_offset_rel = QPointF(0.15, -0.15)
        self.magnifier_spacing_rel = 0.05
        self.internal_split = 0.5

        self.visual_capture_pos = QPointF(0.5, 0.5)
        self.visual_magnifier_offset = QPointF(0.15, -0.15)
        self.visual_spacing = 0.05

        self.frozen_magnifier_screen_pos = QPointF(0, 0)

        self.magnifier_radius = 150
        self.capture_radius_rel = 0.1
        self.interp_mode = 1
        self.move_speed_factor = 1.0

        self.pressed_keys = set()
        self.is_dragging_main = False
        self.is_dragging_mag_split = False

        self.update_timer = QTimer(self)
        self.update_timer.setInterval(16)
        self.update_timer.timeout.connect(self._update_physics)
        self.update_timer.start()

        self.display_rect = QRect()
        self.display_scale = 1.0
        self.line_color = QColor(255, 255, 255, 200)

    def set_images(self, pil_original, pil_processed):
        self.pil_original = pil_original
        self.pil_processed = pil_processed
        self.pixmap_original = self._pil_to_pixmap(pil_original)
        self.pixmap_processed = self._pil_to_pixmap(pil_processed)

        self.mask_overlay = None
        self.update()

    def _pil_to_pixmap(self, pil_img):
        if pil_img is None: return None
        if pil_img.mode != "RGBA": pil_img = pil_img.convert("RGBA")
        w, h = pil_img.size
        data = pil_img.tobytes("raw", "RGBA")
        qim = QImage(data, w, h, QImage.Format.Format_RGBA8888)
        return QPixmap.fromImage(qim)

    def set_magnifier_params(self, radius, capture_size, interp):
        self.magnifier_radius = int(radius)
        self.capture_radius_rel = capture_size / 100.0
        self.interp_mode = interp
        self.update()

    def set_move_speed(self, speed):
        self.move_speed_factor = speed

    def toggle_magnifier(self, enabled: bool):
        self.is_magnifier_enabled = enabled
        self.update()

    def toggle_freeze(self, frozen: bool):
        if not self.is_magnifier_enabled:
            self.is_magnifier_frozen = False
            return

        if frozen:
            center = self._get_current_magnifier_screen_center(visual=True)
            if self.width() > 0 and self.height() > 0:
                self.frozen_magnifier_screen_pos = QPointF(center.x()/self.width(), center.y()/self.height())
        else:
            current_mag = QPointF(
                self.frozen_magnifier_screen_pos.x() * self.width(),
                self.frozen_magnifier_screen_pos.y() * self.height()
            )
            current_cap = self._get_capture_screen_pos(visual=True)
            ref_dim = max(self.display_rect.width(), self.display_rect.height())

            if ref_dim > 0:
                diff = current_mag - current_cap
                new_offset = QPointF(diff.x() / ref_dim, diff.y() / ref_dim)
                self.magnifier_offset_rel = new_offset
                self.visual_magnifier_offset = new_offset

        self.is_magnifier_frozen = frozen
        self.update()

    def set_mask_overlay(self, mask):
        self.mask_overlay = mask
        self.update()

    def handle_external_key_press(self, key):
        self.pressed_keys.add(key)

    def handle_external_key_release(self, key):
        self.pressed_keys.discard(key)

    def _update_physics(self):
        if not self.pixmap_original: return

        dt = 0.016
        step = 0.5 * self.move_speed_factor * dt
        if Qt.Key.Key_Shift in self.pressed_keys: step *= 3.0

        dx, dy = 0.0, 0.0
        if Qt.Key.Key_W in self.pressed_keys: dy -= step
        if Qt.Key.Key_S in self.pressed_keys: dy += step
        if Qt.Key.Key_A in self.pressed_keys: dx -= step
        if Qt.Key.Key_D in self.pressed_keys: dx += step

        d_space = 0.0
        if Qt.Key.Key_Q in self.pressed_keys: d_space -= step
        if Qt.Key.Key_E in self.pressed_keys: d_space += step

        need_update = False

        if self.is_magnifier_enabled:
            if dx != 0 or dy != 0:
                if self.is_magnifier_frozen:
                    aspect = 1.0
                    if self.display_rect.height() > 0:
                        aspect = self.display_rect.width() / self.display_rect.height()
                    self.capture_pos_rel += QPointF(dx, dy * aspect)
                    self.capture_pos_rel.setX(max(0.0, min(1.0, self.capture_pos_rel.x())))
                    self.capture_pos_rel.setY(max(0.0, min(1.0, self.capture_pos_rel.y())))
                else:
                    self.magnifier_offset_rel += QPointF(dx, dy)
                need_update = True

            if d_space != 0:
                self.magnifier_spacing_rel = max(0.0, self.magnifier_spacing_rel + d_space)
                need_update = True

        lerp_t = 0.2

        v_cap = self.visual_capture_pos
        t_cap = self.capture_pos_rel
        diff_cap = t_cap - v_cap
        if diff_cap.manhattanLength() > 0.0001:
            self.visual_capture_pos = v_cap + diff_cap * lerp_t
            need_update = True
        else:
            self.visual_capture_pos = t_cap

        v_off = self.visual_magnifier_offset
        t_off = self.magnifier_offset_rel
        diff_off = t_off - v_off
        if diff_off.manhattanLength() > 0.0001:
            self.visual_magnifier_offset = v_off + diff_off * lerp_t
            need_update = True
        else:
            self.visual_magnifier_offset = t_off

        v_sp = self.visual_spacing
        t_sp = self.magnifier_spacing_rel
        if abs(v_sp - t_sp) > 0.0001:
            self.visual_spacing = v_sp + (t_sp - v_sp) * lerp_t
            need_update = True
        else:
            self.visual_spacing = t_sp

        if need_update:
            self.update()

    def mousePressEvent(self, event):
        pos = event.pos()
        if not self.display_rect.contains(pos): return

        if event.button() == Qt.MouseButton.LeftButton:
            self.is_dragging_main = True
            self._handle_main_drag(pos)

        elif event.button() == Qt.MouseButton.RightButton:
            if self.is_magnifier_enabled and self._is_pos_inside_magnifier(pos):
                self.is_dragging_mag_split = True
                self._handle_mag_split_drag(pos)

    def mouseMoveEvent(self, event):
        pos = event.pos()
        if self.is_dragging_main:
            self._handle_main_drag(pos)
        elif self.is_dragging_mag_split:
            self._handle_mag_split_drag(pos)

    def mouseReleaseEvent(self, event):
        self.is_dragging_main = False
        self.is_dragging_mag_split = False

    def _handle_main_drag(self, pos):
        if self.display_rect.width() <= 0: return
        rx = (pos.x() - self.display_rect.x()) / self.display_rect.width()
        ry = (pos.y() - self.display_rect.y()) / self.display_rect.height()
        rx = max(0.0, min(1.0, rx))
        ry = max(0.0, min(1.0, ry))

        if self.is_magnifier_enabled:
            self.capture_pos_rel = QPointF(rx, ry)
            self.visual_capture_pos = self.capture_pos_rel
        else:
            self.split_pos = rx
        self.update()

    def _handle_mag_split_drag(self, pos):
        centers = self._get_magnifier_circles_centers(visual=True)
        if not centers: return

        base_x = centers[0].x() - self.magnifier_radius
        val = (pos.x() - base_x) / (self.magnifier_radius * 2)
        self.internal_split = max(0.0, min(1.0, val))
        self.update()

    def _get_capture_screen_pos(self, visual=True):
        pos = self.visual_capture_pos if visual else self.capture_pos_rel
        cx = self.display_rect.x() + pos.x() * self.display_rect.width()
        cy = self.display_rect.y() + pos.y() * self.display_rect.height()
        return QPointF(cx, cy)

    def _get_current_magnifier_screen_center(self, visual=True):
        if self.is_magnifier_frozen:
            return QPointF(
                self.frozen_magnifier_screen_pos.x() * self.width(),
                self.frozen_magnifier_screen_pos.y() * self.height()
            )

        cap_pos = self._get_capture_screen_pos(visual)
        ref_dim = max(self.display_rect.width(), self.display_rect.height())
        off = self.visual_magnifier_offset if visual else self.magnifier_offset_rel

        return QPointF(cap_pos.x() + off.x() * ref_dim, cap_pos.y() + off.y() * ref_dim)

    def _get_magnifier_circles_centers(self, visual=True):
        center = self._get_current_magnifier_screen_center(visual)
        ref_dim = max(self.display_rect.width(), self.display_rect.height())
        sp = self.visual_spacing if visual else self.magnifier_spacing_rel
        spacing_px = sp * ref_dim

        if spacing_px < 5.0:
            return [center]
        else:
            offset = self.magnifier_radius + spacing_px / 2.0
            return [QPointF(center.x() - offset, center.y()), QPointF(center.x() + offset, center.y())]

    def _is_pos_inside_magnifier(self, pos):
        centers = self._get_magnifier_circles_centers(visual=True)
        r_sq = self.magnifier_radius ** 2
        for c in centers:
            if (pos.x() - c.x())**2 + (pos.y() - c.y())**2 <= r_sq:
                return True
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor(30, 30, 30))

        if not self.pixmap_original or not self.pixmap_processed:
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load Images")
            return

        w_w, h_w = self.width(), self.height()
        w_i, h_i = self.pixmap_original.width(), self.pixmap_original.height()
        scale = min(w_w/w_i, h_w/h_i) * 0.95
        self.display_scale = scale
        dw, dh = int(w_i * scale), int(h_i * scale)
        dx, dy = (w_w - dw)//2, (h_w - dh)//2
        self.display_rect = QRect(dx, dy, dw, dh)

        painter.drawPixmap(self.display_rect, self.pixmap_processed)

        split_x = int(dx + dw * self.split_pos)
        painter.save()
        painter.setClipRect(dx, dy, split_x - dx, dh)
        painter.drawPixmap(self.display_rect, self.pixmap_original)
        painter.restore()

        if self.mask_overlay and not self.mask_overlay.isNull():
            painter.drawPixmap(self.display_rect, self.mask_overlay)

        painter.setPen(QPen(self.line_color, 2))
        painter.drawLine(split_x, dy, split_x, dy + dh)

        if self.is_magnifier_enabled:
            cap_pos = self._get_capture_screen_pos(visual=True)
            ref_dim = min(dw, dh)
            cap_r = (self.capture_radius_rel * ref_dim) / 2.0

            painter.setPen(QPen(QColor(255, 50, 50), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(cap_pos, cap_r, cap_r)

            self._draw_magnifier(painter, cap_r)

    def _draw_magnifier(self, painter, cap_r_screen):
        centers = self._get_magnifier_circles_centers(visual=True)
        r = self.magnifier_radius
        d = r * 2

        src_r_px = cap_r_screen / self.display_scale
        src_cx = self.visual_capture_pos.x() * self.pixmap_original.width()
        src_cy = self.visual_capture_pos.y() * self.pixmap_original.height()

        pix_orig = self._get_patch(self.pil_original, self.pixmap_original, src_cx, src_cy, src_r_px, d)
        pix_proc = self._get_patch(self.pil_processed, self.pixmap_processed, src_cx, src_cy, src_r_px, d)

        if len(centers) == 1:

            c = centers[0]
            rect = QRectF(c.x()-r, c.y()-r, d, d)

            painter.save()
            path = QPainterPath()
            path.addEllipse(c, r, r)
            painter.setClipPath(path)

            painter.fillRect(rect, Qt.GlobalColor.black)
            painter.drawPixmap(rect.toRect(), pix_proc)

            split_w = d * self.internal_split

            painter.setClipRect(QRectF(rect.x(), rect.y(), split_w, d), Qt.ClipOperation.IntersectClip)
            painter.drawPixmap(rect.toRect(), pix_orig)

            painter.setClipPath(path)
            line_x = rect.x() + split_w
            painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
            painter.drawLine(QPointF(line_x, rect.y()), QPointF(line_x, rect.bottom()))

            painter.restore()

            painter.setPen(QPen(Qt.GlobalColor.white, 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(c, r, r)

        else:

            c1, c2 = centers[0], centers[1]
            rect1 = QRectF(c1.x()-r, c1.y()-r, d, d)
            rect2 = QRectF(c2.x()-r, c2.y()-r, d, d)

            painter.save()
            path1 = QPainterPath()
            path1.addEllipse(c1, r, r)
            painter.setClipPath(path1)
            painter.fillRect(rect1, Qt.GlobalColor.black)
            painter.drawPixmap(rect1.toRect(), pix_orig)
            painter.restore()
            painter.setPen(QPen(QColor(100, 200, 255), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(c1, r, r)

            painter.save()
            path2 = QPainterPath()
            path2.addEllipse(c2, r, r)
            painter.setClipPath(path2)
            painter.fillRect(rect2, Qt.GlobalColor.black)
            painter.drawPixmap(rect2.toRect(), pix_proc)
            painter.restore()
            painter.setPen(QPen(QColor(100, 255, 100), 3))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(c2, r, r)

    def _get_patch(self, pil_img, qpix, cx, cy, radius, out_size):
        x = int(cx - radius)
        y = int(cy - radius)
        w = int(radius * 2)

        if self.interp_mode >= 2 and pil_img:
            try:
                crop = pil_img.crop((x, y, x+w, y+w))
                m = Image.Resampling.LANCZOS if self.interp_mode == 3 else Image.Resampling.BICUBIC
                return self._pil_to_pixmap(crop.resize((int(out_size), int(out_size)), resample=m))
            except: pass

        if qpix:
            patch = qpix.copy(x, y, w, w)
            if patch.isNull():
                patch = QPixmap(int(out_size), int(out_size))
                patch.fill(Qt.GlobalColor.black)
            else:
                t = Qt.TransformationMode.SmoothTransformation if self.interp_mode == 1 else Qt.TransformationMode.FastTransformation
                patch = patch.scaled(int(out_size), int(out_size), Qt.AspectRatioMode.IgnoreAspectRatio, t)
            return patch
        return QPixmap()

class RangeSlider(QWidget):
    valueChanged = pyqtSignal(int, int)
    interactionStarted = pyqtSignal()
    interactionEnded = pyqtSignal()
    previewRequested = pyqtSignal(float)

    def __init__(self, min_val=0, max_val=100, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.min_val = int(min_val)
        self.max_val = int(max_val)
        self.low = self.min_val
        self.high = self.max_val
        self.pressed_handle = None
        self.margin = 12
        self.track_color = QColor("#333"); self.active_color = QColor("#4CAF50")
        self.handle_color = QColor("#ffffff"); self.handle_border = QColor("#4CAF50")
        self.is_rmb = False; self.drag_start_x = 0
        self.orig_low = 0; self.orig_high = 0

    def set_range(self, low, high):

        self.low = max(self.min_val, min(self.max_val, int(round(low))))
        self.high = max(self.min_val, min(self.max_val, int(round(high))))
        if self.low > self.high: self.low, self.high = self.high, self.low
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width(); h = self.height(); y = h // 2
        avail = w - 2*self.margin
        span = self.max_val - self.min_val
        if span <= 0: span = 1

        xl = self.margin + int(((self.low - self.min_val)/span)*avail)
        xh = self.margin + int(((self.high - self.min_val)/span)*avail)

        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(self.track_color))
        p.drawRoundedRect(self.margin, y-2, avail, 4, 2, 2)
        p.setBrush(QBrush(self.active_color))
        p.drawRoundedRect(xl, y-2, max(0, xh-xl), 4, 2, 2)

        p.setBrush(QBrush(self.handle_color)); p.setPen(QPen(self.handle_border, 2))
        p.drawEllipse(QPoint(xl, y), 7, 7)
        p.drawEllipse(QPoint(xh, y), 7, 7)

    def mousePressEvent(self, e):
        val = self._get_val(e.pos().x())
        if e.button() == Qt.MouseButton.LeftButton:
            self.interactionStarted.emit()

            d_low = abs(val - self.low)
            d_high = abs(val - self.high)
            if d_low < d_high: self.pressed_handle = 'low'
            else: self.pressed_handle = 'high'

            self._update_drag(val)

        elif e.button() == Qt.MouseButton.RightButton:
            self.is_rmb = True; self.drag_start_x = e.pos().x()
            self.orig_low = self.low; self.orig_high = self.high
            v_int = int(round(val))
            self.low = v_int; self.high = v_int
            self.update()

    def mouseMoveEvent(self, e):
        val = self._get_val(e.pos().x())
        if self.pressed_handle: self._update_drag(val)
        if self.is_rmb:
            v_int = int(round(val))
            self.low = v_int; self.high = v_int
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.pressed_handle = None; self.interactionEnded.emit()
        elif e.button() == Qt.MouseButton.RightButton and self.is_rmb:
            if abs(e.pos().x() - self.drag_start_x) < 3:
                self.low = self.orig_low; self.high = self.orig_high
                self.update()
                self.previewRequested.emit(self._get_val(e.pos().x()))
            else:
                self.valueChanged.emit(self.low, self.high)
            self.is_rmb = False; self.interactionEnded.emit()

    def _get_val(self, x):
        w = self.width(); avail = w - 2*self.margin
        if avail <= 0: return self.min_val
        span = self.max_val - self.min_val
        val = self.min_val + ((x - self.margin) / avail) * span
        return max(self.min_val, min(self.max_val, val))

    def _update_drag(self, val):

        val_int = int(round(val))

        if self.pressed_handle == 'low':
            if val_int > self.high:
                self.low = self.high; self.high = val_int; self.pressed_handle = 'high'
            else: self.low = val_int
        else:
            if val_int < self.low:
                self.high = self.low; self.low = val_int; self.pressed_handle = 'low'
            else: self.high = val_int

        self.update()
        self.valueChanged.emit(self.low, self.high)

    def low_value(self):
        return self.low

    def high_value(self):
        return self.high

class GenerationInfoBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 5)
        self.layout.setSpacing(10)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        lbl = QLabel("Waiting for generation...")
        lbl.setStyleSheet("color: #666; font-style: italic;")
        self.layout.addWidget(lbl)

    def update_data(self, stats):

        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not stats:
            return

        display_stats = {}

        if 'trap_int' in stats and stats['trap_int'] > 0:
            display_stats['Trap'] = {'hit': True, 'val': f"{stats['trap_int']:.2f}"}
        else:
            display_stats['Trap'] = {'hit': False, 'val': '-'}

        if 'crease_dark' in stats:
            display_stats['Crease'] = {'hit': True, 'val': f"Drk:{stats['crease_dark']:.2f}"}
        else:
            display_stats['Crease'] = {'hit': False, 'val': '-'}

        if 'shift_px' in stats:
            display_stats['Shift'] = {'hit': True, 'val': f"{stats['shift_px']}"}
        else:
            display_stats['Shift'] = {'hit': False, 'val': '-'}

        if 'debris_cnt' in stats and stats['debris_cnt'] > 0:
            display_stats['Debris'] = {'hit': True, 'val': f"Cnt:{stats['debris_cnt']}"}
        else:
            display_stats['Debris'] = {'hit': False, 'val': '-'}

        if 'scratch_cnt' in stats and stats['scratch_cnt'] > 0:
            display_stats['Scratches'] = {'hit': True, 'val': f"Cnt:{stats['scratch_cnt']}(L:{stats.get('scratch_len', 0)})"}
        else:
            display_stats['Scratches'] = {'hit': False, 'val': '-'}

        if 'micro_dust' in stats and stats['micro_dust'] > 0:
            display_stats['Micro'] = {'hit': True, 'val': f"Dust:{stats['micro_dust']}"}
        else:
            display_stats['Micro'] = {'hit': False, 'val': '-'}

        if 'stain_str' in stats and stats['stain_str'] > 0:
            display_stats['Stain L'] = {'hit': True, 'val': f"{stats['stain_str']:.2f}"}
        else:
            display_stats['Stain L'] = {'hit': False, 'val': '-'}

        if 'speckle_str' in stats and stats['speckle_str'] > 0:
            display_stats['Stain S'] = {'hit': True, 'val': f"{stats['speckle_str']:.2f}"}
        else:
            display_stats['Stain S'] = {'hit': False, 'val': '-'}

        if 'emul_mix' in stats:
            display_stats['Emulsion'] = {'hit': True, 'val': f"{stats['emul_mix']:.2f}"}
        else:
            display_stats['Emulsion'] = {'hit': False, 'val': '-'}

        if 'grain_str' in stats:
            display_stats['Grain'] = {'hit': True, 'val': f"{stats['grain_str']:.2f}"}
        else:
            display_stats['Grain'] = {'hit': False, 'val': '-'}

        if 'blur_rad' in stats and stats['blur_rad'] > 0:
            display_stats['Blur'] = {'hit': True, 'val': f"{stats['blur_rad']:.2f}"}
        else:
            display_stats['Blur'] = {'hit': False, 'val': '-'}

        if 'band_lvl' in stats:

            display_stats['Banding'] = {'hit': True, 'val': f"Lvl:{stats['band_lvl']}"}
        else:
            display_stats['Banding'] = {'hit': False, 'val': '-'}

        if 'mpeg' in stats and stats['mpeg'] < 100:
            display_stats['MPEG'] = {'hit': True, 'val': f"{stats['mpeg']}"}
        else:
            display_stats['MPEG'] = {'hit': False, 'val': '-'}

        if stats.get('is_extreme', 0):

            m = stats.get('ext_mult', 1.0)
            c = stats.get('ext_cast', 1.0)
            display_stats['Extreme'] = {'hit': True, 'val': f"M:{m} C:{c}"}
        else:
            display_stats['Extreme'] = {'hit': False, 'val': '-'}

        order = ['Trap', 'Crease', 'Shift', 'Debris', 'Scratches', 'Micro',
                 'Stain L', 'Stain S', 'Emulsion', 'Grain', 'Banding', 'Blur', 'MPEG', 'Extreme']

        for key in order:
            if key in display_stats:
                self._add_card(key, display_stats[key])

        self.layout.addStretch()

    def _add_card(self, title, data):

        card = QWidget()
        card.setFixedSize(80, 50)

        is_hit = data['hit']
        val_str = str(data['val'])

        bg_color = "#2d2d2d" if is_hit else "#1e1e1e"
        border_color = "#4CAF50" if is_hit else "#444"
        text_color = "#fff" if is_hit else "#666"

        card.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QLabel {{ border: none; background: transparent; }}
        """)

        l = QVBoxLayout(card)
        l.setContentsMargins(2, 2, 2, 2)
        l.setSpacing(0)

        lbl_title = QLabel(title)
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_title.setStyleSheet(f"font-size: 10px; font-weight: bold; color: {text_color};")

        lbl_val = QLabel(val_str)
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_val.setStyleSheet(f"font-size: 11px; color: {text_color};")

        l.addWidget(lbl_title)
        l.addWidget(lbl_val)

        self.layout.addWidget(card)

