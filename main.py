import base64
import io
import json
import os
import sys

import pyperclip
import requests
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import Qt, pyqtSignal
from pynotifier import Notification
from system_hotkey import SystemHotkey

global api
global hotkey_1
global hotkey_2


class Snipper(QtWidgets.QWidget):

    def __init__(self, parent=None, flags=Qt.WindowFlags()):
        super().__init__(parent=parent, flags=flags)

        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.CrossCursor))

        self.start, self.end = QtCore.QPoint(), QtCore.QPoint()

        self.setWindowTitle("TextShot")
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Dialog
        )
        self.setWindowState(self.windowState() | Qt.WindowFullScreen)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.window().hide()

        return super().keyPressEvent(event)

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 100))
        painter.drawRect(0, 0, self.width(), self.height())

        if self.start == self.end:
            return super().paintEvent(event)

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 3))
        painter.setBrush(painter.background())
        painter.drawRect(QtCore.QRect(self.start, self.end))
        return super().paintEvent(event)

    def mousePressEvent(self, event):
        self.start = self.end = event.pos()
        self.update()
        return super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.end = event.pos()
        self.update()
        return super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start == self.end:
            return super().mouseReleaseEvent(event)
        self.hide()
        QtWidgets.QApplication.processEvents()
        shot = self.screen.copy(QtCore.QRect(self.start, self.end))
        processImage(shot)
        self.start, self.end = None, None


class TrayIcon(QtWidgets.QSystemTrayIcon):
    qthotkey = pyqtSignal()

    def __init__(self, MainWindow, parent=None):
        super(TrayIcon, self).__init__(parent)
        self.ui = MainWindow
        self.createMenu()
        self.snipper = Snipper
        self.qthotkey.connect(self.showWindow)
        self.syshk = SystemHotkey()
        self.syshk.register((hotkey_1, hotkey_2), callback=lambda x: self.send_key_event())

    def send_key_event(self):
        self.qthotkey.emit()

    def createMenu(self):
        self.menu = QtWidgets.QMenu()
        self.showAction = QtWidgets.QAction('截图识别（Alt + R）', self, triggered=self.showWindow)
        self.quitAction = QtWidgets.QAction('退出', self, triggered=self.quit)

        self.menu.addAction(self.showAction)
        self.menu.addAction(self.quitAction)
        self.setContextMenu(self.menu)
        self.setIcon(QtGui.QIcon('./res/icon.ico'))
        self.icon = self.MessageIcon()
        self.activated.connect(self.onIconClicked)

    def quit(self):
        QtWidgets.qApp.quit()

    def onIconClicked(self, reason):
        if reason == 2 or reason == 3:
            self.showWindow()

    def showWindow(self):
        snipper.screen = QtWidgets.QApplication.primaryScreen().grabWindow(0)
        palette = QtGui.QPalette()
        palette.setBrush(snipper.backgroundRole(), QtGui.QBrush(snipper.screen))
        snipper.setPalette(palette)
        self.ui.show()
        self.ui.activateWindow()


def processImage(img):
    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QBuffer.ReadWrite)
    img.save(buffer, "PNG")
    imgpath = 'tmp/tmp.PNG'
    with open(imgpath, 'wb') as f:
        f.write(io.BytesIO(buffer.data()).read())
    buffer.close()
    f.close()
    try:
        result = getrec(imgpath)
    except RuntimeError as error:
        print(f"ERROR: An error occurred when trying to process the image: {error}")
        notify(f"识别图像时发生错误： {error}")
        return

    if result:
        pyperclip.copy(result)
        print(f'INFO: Copied "{result}" to the clipboard')
        notify(f'已复制："{result}" 到剪贴板')
    else:
        print(f"INFO: Unable to read text from image, did not copy")
        notify(f"未能从此截图中识别到文字")


def getrec(img):
    headers = {'Pragma': 'no-cache', 'Cache-Control': 'no-cache',
               'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/74.0.3729.157 Safari/537.36',
               'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8', 'Content-Type': 'application/json'}
    try:
        with open(img, 'rb') as f:
            img_base64 = str(base64.b64encode(f.read()).decode('utf-8'))
        post_dict = {"images": [img_base64]}
        r = requests.post(api, headers=headers, json=post_dict)
        res = json.loads(r.text)
        if res['status'] == '000':
            text = ''
            for result_list in res['results']:
                for result in result_list:
                    text += result['text'] + '\n'
            ret = text
        else:
            ret = ''
    except:
        ret = ''
    return ret


def notify(msg):
    Notification(title="截图识别", description=msg,
                 icon_path="res/icon.ico",
                 duration=2).send()


def config():
    try:
        with open('config.json') as f:
            data = json.load(f)
            global api
            global hotkey_1
            global hotkey_2
            api = data['url']
            hotkey_1 = data['hot-key'][0]
            hotkey_2 = data['hot-key'][1]
        return True
    except:
        return False


if __name__ == "__main__":
    if not os.path.exists('tmp'):
        os.mkdir('tmp')
    if not os.path.exists('res/icon.ico'):
        notify('缺少必要文件，程序即将退出')
        sys.exit()
    if not config():
        notify('读取配置文件出错，请检查后重试')
        sys.exit()
    QtCore.QCoreApplication.setAttribute(Qt.AA_DisableHighDpiScaling)
    app = QtWidgets.QApplication(sys.argv)
    window = QtWidgets.QMainWindow()
    snipper = Snipper(window)
    icon = TrayIcon(snipper)
    icon.show()
    sys.exit(app.exec_())
