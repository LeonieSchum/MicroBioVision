"""
pellet_sorter_gui.py (Optimierte PySide6-Version)
=================================================
Exakte 1:1 Portierung des Tkinter-Designs auf PySide6, damit es
problemlos im QMdiSubWindow läuft.

Überarbeitete Analyse-Logik (v2):
  - Leere / zu helle Bilder (ohne Pellets) werden aussortiert
  - Luftblasen-Artefakte (breite schwarze Balken) werden erkannt
  - Zusammengeklumpte / überlappende Pellets (Riesenblobs) werden aussortiert
  - Nur Bilder mit ausreichend vielen, einzeln vorliegenden Pellets werden behalten
"""

import os
import shutil
from pathlib import Path
import threading
import queue
import copy
from dataclasses import dataclass

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QProgressBar, QTreeWidget,
                               QTreeWidgetItem, QFileDialog, QMessageBox, QFrame, QLineEdit)
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtCore import Qt, Signal, Slot

import numpy as np
import cv2

# ═══════════════════════════════════════════════════════════════
#  ANALYSE-LOGIK & DATENSTRUKTUREN
# ═══════════════════════════════════════════════════════════════

@dataclass
class Thresholds:
    # Helligkeit
    max_mean_brightness:   float = 186.0
    min_dark_fraction:     float = 0.02

    # Luftblasen-Erkennung: breite schwarze Balken
    max_dark_band_frac:    float = 0.12
    dark_band_threshold:   int   = 50

    # Schalenrand-Erkennung: großer Randblob = Petrischale / Gefäßrand im Bild
    max_edge_blob_frac:    float = 0.15

    # Pellet-Grössen-Filter
    min_pellet_area_rel:   float = 0.001
    max_pellet_area_rel:   float = 0.02

    # Pellet-Anzahl
    min_valid_pellets:     int   = 1
    max_giant_blobs:       int   = 0 

    scale_factor:          int   = 8


@dataclass
class AnalysisResult:
    filepath:        str
    filename:        str
    keep:            bool
    reject_reason:   str
    mean_brightness: float
    dark_fraction:   float
    dark_band_frac:  float
    valid_pellets:   int
    giant_blobs:     int


def analyze_image(image_path: str, thr: Thresholds) -> AnalysisResult:
    img = cv2.imread(str(image_path))
    if img is None:
        return AnalysisResult(image_path, os.path.basename(image_path),
                              False, "Datei nicht lesbar", 0, 0, 0, 0, 0)

    h, w = img.shape[:2]
    s = thr.scale_factor
    small = cv2.resize(img, (w // s, h // s), interpolation=cv2.INTER_AREA)
    gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    img_area = gray.shape[0] * gray.shape[1]

    # ── 1. Helligkeit ────────────────────────────────────────────
    mean_bright = float(gray.mean())

    if mean_bright > thr.max_mean_brightness:
        return AnalysisResult(image_path, os.path.basename(image_path),
                              False, f"Bild zu hell / leer (Helligkeit={mean_bright:.0f})",
                              mean_bright, 0.0, 0.0, 0, 0)

    # ── 2. Luftblasen-Erkennung: breite dunkle Horizontalstreifen ─
    row_means = gray.mean(axis=1)
    dark_rows = (row_means < thr.dark_band_threshold).astype(np.int32)
    max_run, cur_run = 0, 0
    for v in dark_rows:
        if v:
            cur_run += 1
            max_run = max(max_run, cur_run)
        else:
            cur_run = 0
    dark_band_frac = max_run / gray.shape[0]

    if dark_band_frac > thr.max_dark_band_frac:
        return AnalysisResult(image_path, os.path.basename(image_path),
                              False,
                              f"Luftblase / schwarzer Balken erkannt "
                              f"(Bandanteil={dark_band_frac:.2f})",
                              mean_bright, 0.0, dark_band_frac, 0, 0)

    # ── 3. Otsu-Schwellwert → Dunkelanteil ───────────────────────
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    dark_frac = float((thresh > 0).mean())

    # ── 4. Konturen finden: Erosion trennt berührende Pellets ────
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = img_area * thr.min_pellet_area_rel
    max_area = img_area * thr.max_pellet_area_rel
    ih, iw = gray.shape

    valid_pellets, giant_blobs = [], []
    max_edge_blob_area = 0
    for c in contours:
        a = cv2.contourArea(c)
        x, y, bw, bh = cv2.boundingRect(c)
        touches_edge = (x <= 1 or y <= 1 or x + bw >= iw - 1 or y + bh >= ih - 1)
        if touches_edge:
            max_edge_blob_area = max(max_edge_blob_area, a)
            continue
        if a > max_area:
            giant_blobs.append(c)
        elif a > min_area:
            valid_pellets.append(c)

    # ── 5. Entscheidung ────────────────────────────────────────────
    keep, reason = True, ""
    edge_blob_frac = max_edge_blob_area / img_area

    if edge_blob_frac > thr.max_edge_blob_frac:
        keep  = False
        reason = (f"Schalenrand / Gefäßrand im Bild "
                  f"(Randblob={edge_blob_frac:.2f})")
    elif len(giant_blobs) > thr.max_giant_blobs:
        keep  = False
        reason = (f"Zusammengeklumpte / überlappende Pellets "
                  f"({len(giant_blobs)} Klumpen-Blob/s)")
    elif len(valid_pellets) < thr.min_valid_pellets:
        keep  = False
        reason = f"Zu wenige einzelne Pellets erkannt ({len(valid_pellets)})"


    return AnalysisResult(
        image_path, os.path.basename(image_path),
        keep, reason,
        mean_bright, dark_frac, dark_band_frac,
        len(valid_pellets), len(giant_blobs)
    )


def make_preview_qpixmap(image_path: str, thr: Thresholds, max_px: int = 480) -> QPixmap:
    img = cv2.imread(str(image_path))
    if img is None:
        return QPixmap()

    h, w = img.shape[:2]
    s = thr.scale_factor
    small = cv2.resize(img, (w // s, h // s), interpolation=cv2.INTER_AREA)
    gray  = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    img_area = small.shape[0] * small.shape[1]

    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    eroded = cv2.erode(thresh, kernel, iterations=2)
    contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    vis = small.copy()
    ih2, iw2 = gray.shape
    for c in contours:
        a = cv2.contourArea(c)
        x, y, bw, bh = cv2.boundingRect(c)
        if x <= 1 or y <= 1 or x + bw >= iw2 - 1 or y + bh >= ih2 - 1:
            color = (128, 128, 128)  # grau = Randblob, ignoriert
        elif a > img_area * thr.max_pellet_area_rel:
            color = (0, 0, 220)    # rot  = Klumpen/Riesenblob
        elif a > img_area * thr.min_pellet_area_rel:
            color = (0, 200, 0)    # grün = gültiges Einzel-Pellet
        else:
            color = (0, 180, 220)  # gelb = zu klein (Rauschen)
        cv2.drawContours(vis, [c], -1, color, 2)

    vis_rgb = cv2.cvtColor(vis, cv2.COLOR_BGR2RGB)
    qh, qw, qch = vis_rgb.shape
    qimg  = QImage(vis_rgb.data, qw, qh, qch * qw, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(qimg)
    return pixmap.scaled(max_px, max_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)


# ═══════════════════════════════════════════════════════════════
#  DESIGN-TOKENS
# ═══════════════════════════════════════════════════════════════
C_BG      = "#1e1e2e"
C_PANEL   = "#2a2a3e"
C_ACCENT  = "#7c9eff"
C_GREEN   = "#4caf82"
C_RED     = "#e05c6a"
C_TEXT    = "#e8e8f0"
C_SUBTEXT = "#9090b0"
C_BORDER  = "#3a3a55"

EXTS = {".bmp", ".tif", ".tiff", ".png", ".jpg", ".jpeg", ".webp"}


class PelletSorterApp(QWidget):
    result_ready      = Signal(object)
    analysis_finished = Signal()
    preview_ready     = Signal(object, int)

    def __init__(self):
        super().__init__()
        self.thr         = Thresholds()
        self.results     = []
        self.current_idx = 0
        self.input_dir   = ""
        self.output_dir  = ""
        self.setStyleSheet(f"background-color: {C_BG}; color: {C_TEXT};")

        self._preview_queue  = queue.Queue(maxsize=1)
        self._preview_worker = threading.Thread(
            target=self._preview_worker_loop, daemon=True)
        self._preview_worker.start()

        self.result_ready.connect(self._add_result_to_ui)
        self.analysis_finished.connect(self._on_analysis_complete)
        self.preview_ready.connect(self._apply_preview)

        self._init_ui()

    def _init_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(20, 10, 20, 10)

        # ── LINKS ──────────────────────────────────────────────────
        left_panel = QFrame()
        left_panel.setFixedWidth(295)
        left_panel.setStyleSheet(
            f"background-color: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 4px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(14, 10, 14, 10)

        left_layout.addWidget(self._create_section_label("ORDNER"))

        inp_row = QHBoxLayout()
        inp_row.addWidget(QLabel("Eingabe:"))
        self.txt_input = QLineEdit()
        self.txt_input.setStyleSheet(f"background-color: {C_BG}; border: none; padding: 3px;")
        self.txt_input.setReadOnly(True)
        inp_row.addWidget(self.txt_input)
        btn_inp_browse = QPushButton("...")
        btn_inp_browse.setFixedWidth(25)
        btn_inp_browse.setStyleSheet(f"background-color: {C_BORDER}; border: none; padding: 3px;")
        btn_inp_browse.clicked.connect(self._choose_input)
        inp_row.addWidget(btn_inp_browse)
        left_layout.addLayout(inp_row)

        left_layout.addWidget(self._create_section_label("FILTER-PARAMETER"))

        left_layout.addWidget(QLabel("Min. Pellets"))
        row1 = QHBoxLayout()
        self.sld_pellets = QSlider(Qt.Horizontal)
        self.sld_pellets.setRange(1, 20)
        self.sld_pellets.setValue(int(self.thr.min_valid_pellets))
        self.lbl_val_pellets = QLabel(str(self.sld_pellets.value()))
        self.lbl_val_pellets.setStyleSheet(f"color: {C_ACCENT}; font-family: Consolas;")
        self.sld_pellets.valueChanged.connect(lambda v: self.lbl_val_pellets.setText(str(v)))
        row1.addWidget(self.sld_pellets)
        row1.addWidget(self.lbl_val_pellets)
        left_layout.addLayout(row1)

        left_layout.addWidget(QLabel("Max. Pellet-Größe %"))
        row2 = QHBoxLayout()
        self.sld_dark = QSlider(Qt.Horizontal)
        self.sld_dark.setRange(2, 20)
        self.sld_dark.setValue(int(self.thr.max_pellet_area_rel * 100))
        self.lbl_val_dark = QLabel(str(self.sld_dark.value()))
        self.lbl_val_dark.setStyleSheet(f"color: {C_ACCENT}; font-family: Consolas;")
        self.sld_dark.valueChanged.connect(lambda v: self.lbl_val_dark.setText(str(v)))
        row2.addWidget(self.sld_dark)
        row2.addWidget(self.lbl_val_dark)
        left_layout.addLayout(row2)

        left_layout.addWidget(QLabel("Max. Helligkeit"))
        row3 = QHBoxLayout()
        self.sld_bright = QSlider(Qt.Horizontal)
        self.sld_bright.setRange(150, 255)
        self.sld_bright.setValue(int(self.thr.max_mean_brightness))
        self.lbl_val_bright = QLabel(str(self.sld_bright.value()))
        self.lbl_val_bright.setStyleSheet(f"color: {C_ACCENT}; font-family: Consolas;")
        self.sld_bright.valueChanged.connect(lambda v: self.lbl_val_bright.setText(str(v)))
        row3.addWidget(self.sld_bright)
        row3.addWidget(self.lbl_val_bright)
        left_layout.addLayout(row3)

        self.btn_analyze = QPushButton("  Bilder analysieren")
        self.btn_analyze.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_analyze.setStyleSheet(
            f"background-color: {C_ACCENT}; color: white; border: none; padding: 6px; border-radius: 2px;")
        self.btn_analyze.clicked.connect(self._start_analysis)
        left_layout.addWidget(self.btn_analyze)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(
            f"QProgressBar {{ background-color: {C_BG}; border: none; height: 8px; }}"
            f"QProgressBar::chunk {{ background-color: {C_ACCENT}; }}")
        left_layout.addWidget(self.progress)

        left_layout.addWidget(self._create_section_label("ERGEBNIS"))
        self.lbl_summary = QLabel("noch keine Analyse")
        self.lbl_summary.setStyleSheet("border: none;")
        left_layout.addWidget(self.lbl_summary)

        left_layout.addWidget(self._create_section_label("SPEICHERN"))
        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Ausgabe:"))
        self.txt_output = QLineEdit()
        self.txt_output.setStyleSheet(f"background-color: {C_BG}; border: none; padding: 3px;")
        self.txt_output.setReadOnly(True)
        out_row.addWidget(self.txt_output)
        btn_out_browse = QPushButton("...")
        btn_out_browse.setFixedWidth(25)
        btn_out_browse.setStyleSheet(f"background-color: {C_BORDER}; border: none; padding: 3px;")
        btn_out_browse.clicked.connect(self._choose_output)
        out_row.addWidget(btn_out_browse)
        left_layout.addLayout(out_row)

        self.btn_save = QPushButton("  Gute Bilder speichern")
        self.btn_save.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.btn_save.setStyleSheet(
            f"background-color: {C_GREEN}; color: white; border: none; padding: 6px; border-radius: 2px;")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_good)
        left_layout.addWidget(self.btn_save)

        left_layout.addStretch()

        # ── RECHTS ─────────────────────────────────────────────────
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(12, 0, 0, 0)

        nav_panel = QFrame()
        nav_panel.setStyleSheet(
            f"background-color: {C_PANEL}; border: 1px solid {C_BORDER}; border-radius: 4px;")
        nav_layout = QHBoxLayout(nav_panel)
        nav_layout.setContentsMargins(10, 5, 10, 5)

        self.btn_prev = QPushButton(" < ")
        self.btn_prev.setStyleSheet(f"background-color: {C_BORDER}; border: none; padding: 4px 10px;")
        self.btn_prev.clicked.connect(self._prev_image)
        nav_layout.addWidget(self.btn_prev)

        self.lbl_nav = QLabel("- / -")
        self.lbl_nav.setStyleSheet(f"color: {C_SUBTEXT}; border: none;")
        nav_layout.addWidget(self.lbl_nav)

        self.btn_next = QPushButton(" > ")
        self.btn_next.setStyleSheet(f"background-color: {C_BORDER}; border: none; padding: 4px 10px;")
        self.btn_next.clicked.connect(self._next_image)
        nav_layout.addWidget(self.btn_next)

        self.lbl_filename = QLabel("Noch keine Bilder analysiert")
        self.lbl_filename.setStyleSheet("border: none; margin-left: 10px;")
        nav_layout.addWidget(self.lbl_filename)
        nav_layout.addStretch()

        self.lbl_verdict = QLabel("")
        self.lbl_verdict.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.lbl_verdict.setStyleSheet("border: none;")
        nav_layout.addWidget(self.lbl_verdict)
        right_layout.addWidget(nav_panel)

        self.lbl_canvas = QLabel("Vorschau erscheint nach der Analyse")
        self.lbl_canvas.setAlignment(Qt.AlignCenter)
        self.lbl_canvas.setMinimumSize(480, 320)
        self.lbl_canvas.setStyleSheet(
            "background-color: #111122; color: #9090b0; border: 1px solid #3a3a55;")
        right_layout.addWidget(self.lbl_canvas)

        self.lbl_metrics = QLabel("")
        self.lbl_metrics.setStyleSheet(f"color: {C_SUBTEXT}; font-family: Consolas;")
        right_layout.addWidget(self.lbl_metrics)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(["", "Dateiname", "Pellets", "Klumpen", "Ablehnungsgrund"])
        self.tree.setColumnWidth(0, 40)
        self.tree.setColumnWidth(1, 220)
        self.tree.setColumnWidth(2, 60)
        self.tree.setColumnWidth(3, 65)
        self.tree.setColumnWidth(4, 360)
        self.tree.setStyleSheet(
            f"QTreeWidget {{ background-color: {C_BG}; color: {C_TEXT}; border: 1px solid {C_BORDER}; }}"
            f"QHeaderView::section {{ background-color: {C_PANEL}; color: {C_SUBTEXT}; border: none; height: 22px; }}"
            f"QTreeWidget::item:selected {{ background-color: {C_ACCENT}; color: white; }}"
        )
        self.tree.itemSelectionChanged.connect(self._on_tree_select)
        right_layout.addWidget(self.tree)

        main_layout.addWidget(left_panel)
        main_layout.addLayout(right_layout)

    def _create_section_label(self, text):
        lbl = QLabel(f"<b>{text}</b>")
        lbl.setStyleSheet(
            f"color: {C_SUBTEXT}; font-size: 10px; border: none; margin-top: 10px; margin-bottom: 2px;")
        return lbl

    # ── Worker & Slots ──────────────────────────────────────────

    def _preview_worker_loop(self):
        while True:
            item = self._preview_queue.get()
            if item is None:
                break
            filepath, idx, thr_snap = item
            try:
                pixmap = make_preview_qpixmap(filepath, thr_snap)
                self.preview_ready.emit(pixmap, idx)
            except Exception:
                pass

    def _choose_input(self):
        d = QFileDialog.getExistingDirectory(self, "Eingabeordner mit Bildern wählen")
        if d:
            self.input_dir = d
            self.txt_input.setText(d)

    def _choose_output(self):
        d = QFileDialog.getExistingDirectory(self, "Ausgabeordner für gute Bilder wählen")
        if d:
            self.output_dir = d
            self.txt_output.setText(d)

    def _start_analysis(self):
        if not self.input_dir or not os.path.isdir(self.input_dir):
            QMessageBox.warning(self, "Kein Ordner",
                                "Bitte zuerst einen gültigen Eingabeordner wählen.")
            return

        images = sorted([str(p) for p in Path(self.input_dir).iterdir()
                         if p.suffix.lower() in EXTS])
        if not images:
            QMessageBox.information(self, "Keine Bilder",
                                    "Im Ordner wurden keine passenden Bilder gefunden.")
            return

        self.thr.min_valid_pellets   = self.sld_pellets.value()
        self.thr.max_pellet_area_rel = self.sld_dark.value() / 100.0
        self.thr.max_mean_brightness = float(self.sld_bright.value())

        self.btn_analyze.setEnabled(False)
        self.btn_save.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setMaximum(len(images))
        self.results.clear()
        self.tree.clear()
        self.lbl_summary.setText("Analyse läuft...")

        threading.Thread(target=self._run_analysis_worker, args=(images,), daemon=True).start()

    def _run_analysis_worker(self, images):
        thr_snap = copy.copy(self.thr)
        for path in images:
            try:
                r = analyze_image(path, thr_snap)
            except Exception as e:
                r = AnalysisResult(path, os.path.basename(path),
                                   False, f"Fehler: {e}", 0, 0, 0, 0, 0)
            self.result_ready.emit(r)
        self.analysis_finished.emit()

    @Slot(object)
    def _add_result_to_ui(self, r):
        self.results.append(r)
        self.progress.setValue(len(self.results))

        item = QTreeWidgetItem(self.tree)
        item.setText(0, "OK" if r.keep else "XX")
        item.setText(1, r.filename)
        item.setText(2, str(r.valid_pellets))
        item.setText(3, str(r.giant_blobs))
        item.setText(4, "" if r.keep else r.reject_reason)

        fg = Qt.green if r.keep else Qt.red
        item.setForeground(0, fg)
        item.setForeground(1, fg)

    @Slot()
    def _on_analysis_complete(self):
        self.btn_analyze.setEnabled(True)
        n_good = sum(1 for r in self.results if r.keep)
        n_bad  = len(self.results) - n_good

        self.lbl_summary.setText(
            f"Gesamt:       {len(self.results)}\n"
            f"Behalten:    {n_good}\n"
            f"Aussortiert: {n_bad}"
        )

        if n_good > 0:
            self.btn_save.setEnabled(True)

        self.current_idx = 0
        if self.results:
            self.tree.setCurrentItem(self.tree.topLevelItem(0))
            self._show_current()

    def _show_current(self):
        if not self.results:
            return
        r = self.results[self.current_idx]

        self.lbl_nav.setText(f"{self.current_idx + 1} / {len(self.results)}")
        self.lbl_filename.setText(r.filename)

        if r.keep:
            self.lbl_verdict.setText("BEHALTEN")
            self.lbl_verdict.setStyleSheet(f"color: {C_GREEN}; border: none;")
        else:
            self.lbl_verdict.setText("AUSSORTIERT")
            self.lbl_verdict.setStyleSheet(f"color: {C_RED}; border: none;")

        self.lbl_metrics.setText(
            f"Helligkeit: {r.mean_brightness:.0f}  |  "
            f"Dunkel: {r.dark_fraction * 100:.1f}%  |  "
            f"Balken: {r.dark_band_frac:.3f}  |  "
            f"Pellets: {r.valid_pellets}  |  "
            f"Klumpen: {r.giant_blobs}"
        )

        self.lbl_canvas.setText("Lädt Vorschau ...")
        while not self._preview_queue.empty():
            try:
                self._preview_queue.get_nowait()
            except queue.Empty:
                break
        self._preview_queue.put((r.filepath, self.current_idx, copy.copy(self.thr)))

    @Slot(object, int)
    def _apply_preview(self, pixmap, idx):
        if idx == self.current_idx and not pixmap.isNull():
            self.lbl_canvas.setPixmap(pixmap)

    def _prev_image(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.tree.setCurrentItem(self.tree.topLevelItem(self.current_idx))

    def _next_image(self):
        if self.current_idx < len(self.results) - 1:
            self.current_idx += 1
            self.tree.setCurrentItem(self.tree.topLevelItem(self.current_idx))

    def _on_tree_select(self):
        selected = self.tree.currentIndex()
        if selected.isValid():
            new_idx = selected.row()
            if new_idx != self.current_idx:
                self.current_idx = new_idx
                self._show_current()

    def _save_good(self):
        if not self.output_dir:
            self._choose_output()
            if not self.output_dir:
                return

        good = [r for r in self.results if r.keep]
        os.makedirs(self.output_dir, exist_ok=True)
        n = 0
        for r in good:
            try:
                shutil.move(r.filepath, os.path.join(self.output_dir, r.filename))
                n += 1
            except Exception:
                pass
        QMessageBox.information(self, "Gespeichert", f"{n} Bild(er) wurden verschoben.")
        
if __name__ == "__main__":
        import sys
        from PySide6.QtWidgets import QApplication

        app = QApplication(sys.argv)

        window = PelletSorterApp()
        window.resize(1200, 800)
        window.show()

        sys.exit(app.exec())