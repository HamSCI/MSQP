"""The processing thread: source -> speaker, detector -> log, results -> GUI."""

import queue
import threading
import traceback


class Pipeline(threading.Thread):
    """Runs the source, detector, player and log; the GUI reads `out`.

    Messages on `out`:
      ("spectra", first_frame, dBFS array)   for the waterfall
      ("meteor", Meteor)                     every finished echo, accepted or not
      ("error", text) / ("eof",)             the run has ended
    """

    def __init__(self, source, detector, log, player=None):
        super().__init__(daemon=True)
        self.source, self.detector, self.log, self.player = source, detector, log, player
        self.out = queue.Queue()
        self.halt = threading.Event()

    def run(self):
        try:
            self.source.start()
            if self.player:
                self.player.start()
            while not self.halt.is_set():
                block = self.source.read(timeout=0.5)
                if block is None:
                    continue
                t_first, audio = block
                if self.player:
                    self.player.write(audio)
                spectra, first, meteors = self.detector.process(audio, t_first)
                if len(spectra):
                    self.out.put(("spectra", first, spectra))
                for m in meteors:
                    self.log.add(m)
                    if m.accepted and self.player:
                        self.player.beep(m.audio_hz)
                    self.out.put(("meteor", m))
        except EOFError:
            self.out.put(("eof",))
        except Exception as e:
            traceback.print_exc()
            self.out.put(("error", f"{type(e).__name__}: {e}"))
        finally:
            self.source.stop()
            if self.player:
                self.player.stop()

    def stop(self):
        self.halt.set()
        self.join(timeout=3)
