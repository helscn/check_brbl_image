#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QHeaderView, QStyleFactory
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtCore import QThread, Signal, Slot, QObject
from ui.MainWindow_ui import Ui_MainWindow
import resources_rc

from library import MonitorDir
import json
import os

class ImagesTableModel(QAbstractTableModel):
    def __init__(self, data, headers):
        super().__init__()
        self._data=data
        self._headers=headers
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            row = index.row()
            col = index.column()
            if 0 <= row < len(self._data) and 0 <= col < len(self._data[row]):
                return self._data[row][col]
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if 0 <= section < len(self._headers):
                    return self._headers[section]
            else:  # 垂直表头，显示行号
                return str(section + 1)
        return None


class MainWindow(QMainWindow):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.load_config()
        self.dirs=[]
        self.images={}
        
        self.init_ui()
        self.init_thread()
        self.init_signal()


    def load_config(self):
        config={
            "ImagesFolder":"D:/Images/",
            "ThumbnailFolder":"D:/Thumbnails/"
        }
        if os.path.isfile("config.json"):
            try:
                with open("config.json", "r") as f:
                    self.config = self.config.update(json.load(f))
            except Exception as e:
                QMessageBox.critical(self, "配置文件错误", f"无法读取配置文件:\n{e}")
        self.config = config

    def init_ui(self):
        # 设置表格表头
        self.setWindowTitle("波若波罗板厚测量确认")
        self.TableHeaders=['二维码',' 板厚图片 ',' 确认结果 ']
        data=[]
        for i in range(36):
            data.append(["3075513802","✅","⭕"])
            data.append(["3075513802","✅","❌"])
        tableModel=ImagesTableModel(data,self.TableHeaders)
        self.ui.tblImages.setModel(tableModel)
        header = self.ui.tblImages.horizontalHeader()
        header.setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)

    def init_thread(self):
        self.thread = QThread()
        self.worker = MonitorDir(self.config["ImagesFolder"], self.config["ThumbnailFolder"])
        self.worker.moveToThread(self.thread)
        self.worker.dir_updated.connect(self.dir_updated)
        self.thread.started.connect(self.worker.start_monitor)
        self.thread.start()
        
    def init_signal(self):
        self.ui.btnLoadImages.clicked.connect(self.load_images)
        self.ui.btnMoveTodo.clicked.connect(self.move_todo)
        self.ui.btnPrevious.clicked.connect(self.previous_image)
        self.ui.btnNext.clicked.connect(self.next_image)
        self.ui.btnMarkOK.clicked.connect(self.mark_ok)
        self.ui.btnMarkSection.clicked.connect(self.mark_section)
        self.ui.btnMarkDelete.clicked.connect(self.mark_delete)

    def closeEvent(self, event):
        print("Closing application...")
        self.worker.stop()
        self.thread.quit()
        if not self.thread.wait(3000):  # 等待3秒
            print("Thread didn't finish gracefully, terminating...")
            self.thread.terminate()  # 最后手段
            self.thread.wait()
        event.accept()
    def load_images(self):
        pass

    def move_todo(self):
        pass

    def previous_image(self):
        pass

    def next_image(self):
        pass

    def mark_ok(self):
        pass

    def mark_section(self):
        pass

    def mark_delete(self):
        pass

    @Slot(list)
    def dir_updated(self, dirs: list):
        print("接收目录更新")
        current_dir = self.ui.cmbSelectPN.currentText()
        self.ui.cmbSelectPN.clear()
        for dir in dirs:
            self.ui.cmbSelectPN.addItem(dir)
            if current_dir == dir:
                self.ui.cmbSelectPN.setCurrentText(dir)


    @Slot(str, str)
    def thumbnail_updated(self, dir:str, name:str):
        pass



if __name__ == '__main__':
    app = QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))
    win = MainWindow()
    win.show()
    app.exec()
