"""The window: input, channel and audio choices; waterfall; daily meteor counts."""

import os
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt5")
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets

from .config import AUDIO_OFFSET_HZ, F_HI, F_LO, PILOT_MHZ, THRESHOLD_DB
from .detector import MeteorDetector
from .engine import Pipeline
from .output import BINS_PER_DAY, MeteorLog
from .sources import SdrSource, SoundcardSource, WavSource, list_audio_devices, list_sdrs

N_ROWS = 600          # waterfall height in rows
MARK_COLOR = "#00e5ff"

pg.setConfigOptions(imageAxisOrder="row-major", antialias=True)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, out_dir):
        super().__init__()
        self.setWindowTitle("RT Meteor Counter")
        self.resize(1300, 850)
        self.pipeline = self.detector = self.log = self.player = None
        self.marks = []           # (spectrum number, audio Hz) of accepted meteors
        self.ref_db = None        # typical noise level, sets the waterfall's default levels

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QHBoxLayout(central)
        layout.addWidget(self._controls(out_dir), 0)
        right = QtWidgets.QVBoxLayout()
        layout.addLayout(right, 1)
        right.addWidget(self._waterfall(), 3)
        right.addLayout(self._sliders())
        right.addWidget(self._counts_plot(), 1)
        self.status = self.statusBar()

        self.poll = QtCore.QTimer(self, interval=50, timeout=self._poll)
        self.poll.start()
        self.house = QtCore.QTimer(self, interval=5000, timeout=self._housekeeping)
        self.house.start()
        self._refresh_devices()

    # ------------------------------------------------------------ layout

    def _controls(self, out_dir):
        box = QtWidgets.QWidget()
        box.setMaximumWidth(330)
        v = QtWidgets.QVBoxLayout(box)

        g = QtWidgets.QGroupBox("Receiver")
        f = QtWidgets.QFormLayout(g)
        self.input_combo = QtWidgets.QComboBox()
        refresh = QtWidgets.QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_devices)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.input_combo, 1)
        row.addWidget(refresh)
        f.addRow("Input", row)
        self.channel_combo = QtWidgets.QComboBox()
        for ch, mhz in PILOT_MHZ.items():
            dial = mhz - AUDIO_OFFSET_HZ / 1e6
            self.channel_combo.addItem(f"Ch {ch}: pilot {mhz:.6f}, dial {dial:.6f} MHz USB", ch)
        f.addRow("TV channel", self.channel_combo)
        self.gain = QtWidgets.QDoubleSpinBox(minimum=0, maximum=60, value=30, suffix=" dB")
        f.addRow("SDR gain", self.gain)
        self.ppm = QtWidgets.QDoubleSpinBox(minimum=-100, maximum=100, decimals=1, suffix=" ppm")
        self.ppm.setToolTip("Frequency correction for the SDR's crystal. At 54 MHz, 1 ppm is 54 Hz.")
        f.addRow("SDR correction", self.ppm)
        v.addWidget(g)

        g = QtWidgets.QGroupBox("Audio")
        f = QtWidgets.QFormLayout(g)
        self.output_combo = QtWidgets.QComboBox()
        f.addRow("Output", self.output_combo)
        self.volume = QtWidgets.QSlider(QtCore.Qt.Horizontal, minimum=0, maximum=100, value=50)
        self.volume.valueChanged.connect(self._audio_settings)
        f.addRow("Volume", self.volume)
        self.beep = QtWidgets.QCheckBox("Beep at each meteor", checked=True)
        self.beep.toggled.connect(self._audio_settings)
        f.addRow(self.beep)
        self.beep_volume = QtWidgets.QSlider(QtCore.Qt.Horizontal, minimum=0, maximum=100, value=30)
        self.beep_volume.valueChanged.connect(self._audio_settings)
        f.addRow("Beep volume", self.beep_volume)
        v.addWidget(g)

        g = QtWidgets.QGroupBox("Detection")
        f = QtWidgets.QFormLayout(g)
        self.threshold = QtWidgets.QDoubleSpinBox(minimum=6, maximum=30, value=THRESHOLD_DB,
                                                  decimals=1, suffix=" dB")
        self.threshold.setToolTip("How far an echo must rise above its own frequency bin's "
                                  "noise floor. Each bin's floor adapts separately, so steady "
                                  "carriers are allowed for.")
        self.threshold.valueChanged.connect(self._detect_settings)
        f.addRow("Threshold", self.threshold)
        self.log_rejects = QtWidgets.QCheckBox("Log rejected echoes", checked=True)
        f.addRow(self.log_rejects)
        self.out_edit = QtWidgets.QLineEdit(str(out_dir))
        browse = QtWidgets.QPushButton("...")
        browse.setMaximumWidth(30)
        browse.clicked.connect(self._browse)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.out_edit, 1)
        row.addWidget(browse)
        f.addRow("Output folder", row)
        v.addWidget(g)

        self.start_btn = QtWidgets.QPushButton("Start")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start_stop)
        v.addWidget(self.start_btn)

        g = QtWidgets.QGroupBox("Meteors")
        f = QtWidgets.QFormLayout(g)
        self.today_label = QtWidgets.QLabel("-")
        self.last_label = QtWidgets.QLabel("-")
        self.last_label.setWordWrap(True)
        f.addRow("Today (UTC)", self.today_label)
        f.addRow("Last", self.last_label)
        v.addWidget(g)
        v.addStretch(1)
        self.run_widgets = [self.input_combo, refresh, self.channel_combo, self.gain, self.ppm,
                            self.output_combo, self.log_rejects, self.out_edit, browse]
        return box

    def _waterfall(self):
        self.wf_plot = pg.PlotWidget()
        self.wf_plot.setLabel("bottom", "Audio frequency", "Hz")
        self.wf_plot.setLabel("left", "Seconds ago")
        self.wf_plot.invertY(True)
        self.wf_plot.setMouseEnabled(x=False, y=False)
        self.img = pg.ImageItem()
        self.img.setColorMap(pg.colormap.get("inferno"))
        self.wf_plot.addItem(self.img)
        self.mark_item = pg.ScatterPlotItem(symbol="o", size=16, pen=pg.mkPen(MARK_COLOR, width=2),
                                            brush=None)
        self.wf_plot.addItem(self.mark_item)
        self.wf_plot.setXRange(F_LO, F_HI, padding=0)
        return self.wf_plot

    def _sliders(self):
        row = QtWidgets.QHBoxLayout()
        self.speed = self._slider(row, "Speed", 1, 16, 12)
        self.sens = self._slider(row, "Sensitivity", 0, 100, 50)
        self.contrast = self._slider(row, "Contrast", 0, 100, 50)
        self.speed.valueChanged.connect(self._reset_waterfall)
        self.sens.valueChanged.connect(self._levels)
        self.contrast.valueChanged.connect(self._levels)
        return row

    def _slider(self, row, name, lo, hi, val):
        row.addWidget(QtWidgets.QLabel(name))
        s = QtWidgets.QSlider(QtCore.Qt.Horizontal, minimum=lo, maximum=hi, value=val)
        row.addWidget(s, 1)
        return s

    def _counts_plot(self):
        self.counts_plot = pg.PlotWidget()
        self.counts_plot.setLabel("bottom", "UTC hour")
        self.counts_plot.setLabel("left", "Meteors / 15 min")
        self.counts_plot.setXRange(0, 24, padding=0)
        self.counts_plot.getAxis("bottom").setTicks([[(h, str(h)) for h in range(0, 25, 2)]])
        self.counts_plot.setMouseEnabled(x=False, y=False)
        self.bars = pg.BarGraphItem(x0=np.arange(BINS_PER_DAY) / 4, width=0.25 * 0.85,
                                    height=np.zeros(BINS_PER_DAY), brush="#2a78d6", pen=None)
        self.counts_plot.addItem(self.bars)
        return self.counts_plot

    # ------------------------------------------------------------ devices

    def _refresh_devices(self):
        self.input_combo.clear()
        for label, args in list_sdrs():
            self.input_combo.addItem(label, ("sdr", args))
        try:
            for name, i in list_audio_devices("input"):
                self.input_combo.addItem(f"Sound card: {name}", ("sound", i))
        except Exception as e:
            self.status.showMessage(f"Sound card list failed: {e}")
        self.input_combo.addItem("WAV file...", ("wav", None))
        self.output_combo.clear()
        self.output_combo.addItem("(none)", None)
        try:
            for name, i in list_audio_devices("output"):
                self.output_combo.addItem(name, i)
            self.output_combo.setCurrentIndex(1 if self.output_combo.count() > 1 else 0)
        except Exception:
            pass
        if not any(self.input_combo.itemData(i)[0] == "sdr" for i in range(self.input_combo.count())):
            self.status.showMessage("No SDR found. Plug it in and press Refresh; see README "
                                    "for drivers.", 10000)

    def _browse(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Output folder", self.out_edit.text())
        if d:
            self.out_edit.setText(d)

    # ------------------------------------------------------------ run

    def _start_stop(self):
        if self.pipeline:
            self._stop()
        else:
            self._start()

    def _start(self):
        kind, data = self.input_combo.currentData()
        ch = self.channel_combo.currentData()
        dial = PILOT_MHZ[ch] * 1e6 - AUDIO_OFFSET_HZ
        if kind == "sdr":
            source = SdrSource(data, dial, self.gain.value(), self.ppm.value())
        elif kind == "sound":
            source = SoundcardSource(data)
        else:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Recording", "", "WAV (*.wav)")
            if not path:
                return
            source = WavSource(path, realtime=True)

        self.detector = MeteorDetector(threshold_db=self.threshold.value())
        out_index = self.output_combo.currentData()
        self.player = None
        if out_index is not None:
            from .audio_out import AudioPlayer
            self.player = AudioPlayer(out_index)
            self._audio_settings()
        self.log = MeteorLog(Path(self.out_edit.text()), ch, dial, self.log_rejects.isChecked())
        self.marks.clear()
        self.ref_db = None
        self._reset_waterfall()
        self.pipeline = Pipeline(source, self.detector, self.log, self.player)
        self.pipeline.start()
        for w in self.run_widgets:
            w.setEnabled(False)
        self.start_btn.setText("Stop")
        self.status.showMessage(f"Running: {source.description}, channel {ch}. "
                                f"Detection starts after a 15 s warm-up.")
        self._update_counts()

    def _stop(self, message="Stopped."):
        if self.pipeline:
            self.pipeline.stop()
            self.pipeline = None
        if self.log:
            self.log.close()   # saves today's count plot
        for w in self.run_widgets:
            w.setEnabled(True)
        self.start_btn.setText("Start")
        self.status.showMessage(message)

    def _audio_settings(self):
        if self.player:
            self.player.volume = self.volume.value() / 100
            self.player.beep_volume = self.beep_volume.value() / 100
            self.player.beep_on = self.beep.isChecked()

    def _detect_settings(self):
        if self.detector:
            self.detector.threshold_db = self.threshold.value()

    def closeEvent(self, event):
        self._stop()
        event.accept()

    # ------------------------------------------------------------ waterfall

    def _frames_per_row(self):
        return 17 - self.speed.value()

    def _reset_waterfall(self):
        nb = len(self.detector.freqs) if self.detector else 129
        self.wf = np.full((N_ROWS, nb), -150.0, np.float32)
        self.acc = np.zeros(nb)
        self.acc_n = 0
        self.top_frame = 0
        frame_s = self.detector.frame_s if self.detector else 0.016
        bin_hz = self.detector.bin_hz if self.detector else 7.8125
        lo = self.detector.freqs[0] if self.detector else F_LO
        height = N_ROWS * self._frames_per_row() * frame_s
        self.img.setImage(self.wf, autoLevels=False)
        self.img.setRect(QtCore.QRectF(lo - bin_hz / 2, 0, nb * bin_hz, height))
        self.wf_plot.setYRange(0, height, padding=0)
        self._levels()

    def _levels(self):
        ref = self.ref_db if self.ref_db is not None else -60.0
        black = ref - 3 + (50 - self.sens.value()) * 0.4
        span = 60 - 0.5 * self.contrast.value()
        self.img.setLevels([black, black + span])

    def _add_spectra(self, first, spectra):
        fpr = self._frames_per_row()
        rows = []
        for k, s in enumerate(spectra):
            self.acc += 10 ** (s / 10)
            self.acc_n += 1
            if self.acc_n == fpr:
                rows.append(10 * np.log10(self.acc / fpr))
                self.acc[:] = 0
                self.acc_n = 0
                self.top_frame = first + k + 1
        if not rows:
            return
        if self.ref_db is None:
            self.ref_db = float(np.median(rows[0]))
            self._levels()
        rows = np.array(rows[::-1], np.float32)
        n = min(len(rows), N_ROWS)
        self.wf[n:] = self.wf[:-n]
        self.wf[:n] = rows[:n]
        self.img.setImage(self.wf, autoLevels=False)

    def _draw_marks(self):
        if not self.detector:
            return
        height = N_ROWS * self._frames_per_row() * self.detector.frame_s
        ages = [((self.top_frame - fr) * self.detector.frame_s, hz) for fr, hz in self.marks]
        ages = [(a, hz) for a, hz in ages if 0 <= a <= height]
        self.mark_item.setData([hz for _, hz in ages], [a for a, _ in ages])

    # ------------------------------------------------------------ updates

    def _poll(self):
        if not self.pipeline:
            return
        q = self.pipeline.out
        changed = False
        for _ in range(500):
            try:
                msg = q.get_nowait()
            except Exception:
                break
            if msg[0] == "spectra":
                self._add_spectra(msg[1], msg[2])
                changed = True
            elif msg[0] == "meteor":
                m = msg[1]
                if m.accepted:
                    self.marks.append((m.frame, m.audio_hz))
                    self.marks = self.marks[-500:]
                    self.last_label.setText(
                        f"{m.utc:%H:%M:%S} UTC, {m.audio_hz:.1f} Hz,\n"
                        f"{m.peak_snr_db:.1f} dB, tau {m.tau_ms:.0f} ms")
                    self._update_counts()
            elif msg[0] == "eof":
                self._stop("End of file.")
                return
            elif msg[0] == "error":
                self._stop(f"Stopped: {msg[1]}")
                QtWidgets.QMessageBox.warning(self, "RT Meteor Counter", msg[1])
                return
        if changed:
            self._draw_marks()

    def _update_counts(self):
        if not self.log:
            return
        today = datetime.now(timezone.utc).date()
        counts = self.log.day_counts(today)
        self.bars.setOpts(height=counts)
        self.counts_plot.setTitle(f"Underdense meteors per 15 minutes, {today:%Y-%m-%d} UTC")
        self.today_label.setText(str(int(counts.sum())))

    def _housekeeping(self):
        if self.log:
            self.log.roll_over()   # saves yesterday's plot just after midnight UTC
            self._update_counts()
        if self.pipeline:
            src = self.pipeline.source
            note = f"  Overflows: {src.overflows}" if getattr(src, "overflows", 0) else ""
            if self.detector and self.detector.n_samples:
                pct = 100 * self.detector.blanker.n_blanked / self.detector.n_samples
                note += f"  Impulse blanking: {pct:.2f}% of samples"
            if note:
                self.status.showMessage(note.strip())


def run(out_dir):
    app = QtWidgets.QApplication([])
    w = MainWindow(out_dir)
    w.show()
    app.exec_()
