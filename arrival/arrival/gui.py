from decoder import ocr_image
from galaxy import Galaxy
import numpy as np
import random
import sys
import time
import traceback
from PySide2.QtWidgets import (QApplication, QDialog, QLineEdit, QLabel, QPushButton, QVBoxLayout,
    QGraphicsScene, QGraphicsView, QInputDialog)
from PySide2.QtCore import QObject, Qt, QRunnable, QThreadPool, Signal, Slot
from PySide2.QtQuick import QQuickView
from PySide2.QtGui import QPixmap
from PIL.ImageQt import ImageQt
from PIL import Image


WorldSize = (480, 420)
WorldScale = 1
API_HOST = 'https://api.pegovka.space/'


import yaml
from pathlib import Path
with open(Path(__file__).parent / '../../.env') as fp:
    obj = yaml.safe_load(fp)
    API_KEY = obj['api_key']


class WorkerSignals(QObject):
    finished = Signal()
    error = Signal(tuple)
    result = Signal(object)
    progress = Signal(object)


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.cancelled = False
        self.mouse_click = None
        self.redraw = None
        self.set_state = None
        self.ocr = None
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.kwargs['progress_callback'] = self.signals.progress

    @Slot()
    def run(self):
        try:
            result = self.fn(self, *self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            if self.signals:
                self.signals.result.emit(result)
        finally:
            if self.signals:
                self.signals.finished.emit()


def render_frame(data, scale):
    if len(data) != 1: print('layers', len(data))
    canvas = np.zeros((*WorldSize[::-1], 4), dtype=np.float)

    canvas = Image.fromarray(canvas, mode='RGBA')
    palette = np.array([
        [0.0, 0.0, 0.2],
        [0.0, 0.0, 0.4],
        [0.0, 0.0, 0.6],
        [0.0, 0.0, 1.0],
        [0.2, 0.5, 0.8],
        [0.0, 0.5, 1.0],
        [0.4, 0.5, 0.8],
        [0.6, 0.5, 0.8],
        [0.8, 0.5, 0.8],
    ], dtype=np.float)

    WorldCenter = (WorldSize[0] // 2, WorldSize[1] // 2)
    offset = np.array(WorldCenter, dtype=np.uint32)
    for i, pts in enumerate(reversed(data)):
        if not pts: continue
        pts = np.array(pts, dtype=np.int32)
        pts += offset
        layer = np.zeros((*WorldSize[::-1], 3), dtype=np.float)
        layer[pts[:,1], pts[:,0], :] = palette[i]

        layer = Image.fromarray((layer * 255).astype(np.uint8), mode='HSV').convert('RGBA')
        mask = np.zeros(WorldSize[::-1], dtype=np.float)
        mask[pts[:,1], pts[:,0]] = 1
        mask = Image.fromarray((mask * 255).astype(np.uint8), mode='L')
        canvas.paste(layer, mask=mask)

    CanvasSize = (WorldSize[0] * scale, WorldSize[1] * scale)
    im = canvas.convert('RGB').resize(CanvasSize, Image.NEAREST)
    return im


last_frame_data = None


def execute_this_fn(worker, *args, **kwargs):
    progress_signal = kwargs['progress_callback']

    galaxy = Galaxy(target='release', api_host=API_HOST, api_key=API_KEY)

    def galaxy_eval(mouse):
        global last_frame_data
        if mouse[0] < -100:
            mouse = (mouse[0] + WorldSize[0], mouse[1])
        galaxy.eval_step(mouse)
        frame_data = galaxy.frame
        if frame_data:
            galaxy.frame = None
            last_frame_data = frame_data
            im = render_frame(frame_data, scale=WorldScale)
            progress_signal.emit(im)

    boot_sequence = [
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
        (8, 4),
        (2, -8),
        (3, 6),
        (0, -14),
        (-4, 10),
        (9, -3),
        (-4, 10),
        (1, 4),
    ]
    for mouse in boot_sequence:
        galaxy_eval(mouse)

    while not worker.cancelled:
        if worker.set_state:
            state = worker.set_state
            worker.set_state = None
            if state:
                galaxy.state = state

        if worker.ocr:
            worker.ocr = None
            im = render_frame(last_frame_data, scale=1)
            for symbol, box in ocr_image(im):
                print('  ', repr(symbol), repr(box))

        if worker.redraw:
            worker.redraw = None
            if last_frame_data:
                im = render_frame(last_frame_data, scale=WorldScale)
                progress_signal.emit(im)

        mouse = worker.mouse_click
        if not mouse:
            time.sleep(0.1)
            continue

        worker.mouse_click = None
        print('mouse', mouse)
        galaxy_eval(mouse)


def progress_fn(im):
    qim = ImageQt(im)
    pix = QPixmap.fromImage(qim)

    _Scene.clear()
    _Scene.setSceneRect(0, 0, qim.width(), qim.height())
    item = _Scene.addPixmap(pix)


def print_output(s):
    print('worker output:', s)


def thread_complete():
    print('worker complete')


_Scene = None

class AppView (QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Arrival")

        self.gscene = QGraphicsScene()
        self.setScene(self.gscene)
        CanvasSize = (WorldSize[0] * WorldScale, WorldSize[1] * WorldScale)
        self.gscene.setSceneRect(0, 0, *CanvasSize)
        global _Scene
        _Scene = self.gscene

        worker = Worker(execute_this_fn)
        worker.signals.result.connect(print_output)
        worker.signals.finished.connect(thread_complete)
        worker.signals.progress.connect(progress_fn)
        self.worker = worker

        self.threadpool = QThreadPool()
        self.threadpool.start(worker)

    def mousePressEvent(self, event):
        p = self.mapToScene(event.pos())
        WorldCenter = (WorldSize[0] // 2, WorldSize[1] // 2)
        mouse = (p.x() // WorldScale - WorldCenter[0], p.y() // WorldScale - WorldCenter[1])
        self.worker.mouse_click = mouse

    def keyPressEvent(self, event):
        ctrl = (event.modifiers() == Qt.ControlModifier) or (event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier))
        if ctrl:
            if event.key() == 45:
                self.zoom_out()
            elif (event.key() == 43) or (event.key() == 61):
                self.zoom_in()
            elif event.key() == 71:
                self.input_state()
            elif event.key() == 73:
                self.ocr()
            else:
                print('keyboard:', event.key(), file=sys.stderr)

    def zoom_in(self):
        global WorldScale
        WorldScale += 1
        if WorldScale > 14:
            WorldScale = int(WorldScale * 1.1)
        self.worker.redraw = True

    def zoom_out(self):
        global WorldScale
        if WorldScale > 14:
            WorldScale = int(WorldScale / 1.1)
        WorldScale = max(1, WorldScale - 1)
        self.worker.redraw = True

    def input_state(self):
        text, ok = QInputDialog().getText(self, "Enter state", "State:", QLineEdit.Normal, '[2, [1, -1], 0, []]')
        if ok and text:
            self.worker.set_state = eval(text)
            self.worker.mouse_click = (-1000, -1000)

    def ocr(self):
        self.worker.ocr = True


def galaxy_gui(argv=[]):
    app = QApplication(argv)
    view = AppView()
    CanvasSize = (WorldSize[0] * WorldScale, WorldSize[1] * WorldScale)
    view.resize(*CanvasSize)
    view.show()
    r = app.exec_()
    view.worker.cancelled = True
    return r


if __name__ == '__main__':
    sys.setrecursionlimit(100000)
    res = galaxy_gui(sys.argv)
    sys.exit(res)
