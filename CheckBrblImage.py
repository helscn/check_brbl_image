#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QHeaderView, QStyleFactory
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, Signal, Slot
from PySide6.QtGui import QPixmap
from ui.MainWindow_ui import Ui_MainWindow
import resources_rc

from library import MonitorDir
import json
import os
import re



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
        self.dirs = []
        self.images = {}
        self.data = []
        self.currentIndex = -1
        self.status = {
            "ok": "✅",
            "section": "⭕",
            "error":"⚠️",
            "delete": "❌"
        }
        
        self.setWindowTitle("波若波罗板厚测量确认")
        self.init_table()
        self.init_thread()
        self.init_signal()


    def load_config(self):
        config={
            "ImagesFolder":"E:/Images/",
            "ThumbnailFolder":"E:/Thumbnails/"
        }
        if os.path.isfile("config.json"):
            try:
                with open("config.json", "r") as f:
                    self.config = self.config.update(json.load(f))
            except Exception as e:
                QMessageBox.critical(self, "配置文件错误", f"无法读取配置文件:\n{e}")
        self.config = config

    def init_table(self):
        self.TableHeaders=['二维码',' 板厚图片 ',' 确认结果 ']
        self.tableModel=ImagesTableModel([],self.TableHeaders)
        self.ui.tblImages.setModel(self.tableModel)
        header = self.ui.tblImages.horizontalHeader()
        header.setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents)

    def init_thread(self):
        self.thread = QThread()
        self.worker = MonitorDir(self.config["ImagesFolder"], self.config["ThumbnailFolder"])
        self.worker.moveToThread(self.thread)
        self.worker.dir_updated.connect(self.dir_updated)
        self.worker.thumbnail_updated.connect(self.thumbnail_updated)
        self.worker.error_occurred.connect(self.error_occurred)
        self.thread.started.connect(self.worker.start_monitor)
        self.thread.start()
        
    def init_signal(self):
        self.ui.cmbSelectPN.currentIndexChanged.connect(self.update_table)
        self.ui.btnMoveTodo.clicked.connect(self.move_todo)
        self.ui.btnMarkOK.clicked.connect(self.mark_ok)
        self.ui.btnMarkSection.clicked.connect(self.mark_section)
        self.ui.btnMarkDelete.clicked.connect(self.mark_delete)
        self.ui.tblImages.clicked.connect(self.show_current_row)
        

    def closeEvent(self, event):
        self.worker.stop()
        self.thread.quit()
        if not self.thread.wait(3000):  # 等待3秒
            self.thread.terminate()  # 最后手段
            self.thread.wait()
        event.accept()
    def move_todo(self):
        pass

    def mark_ok(self):
        idx = self.currentIndex
        if idx>=0 and idx<len(self.data):
            dir,name = self.data[idx]
            self.images[(dir,name)]["checked"] = self.status['ok']
            self.update_table()
            self.select_next_unchecked_image()

    def mark_section(self):
        idx = self.currentIndex
        if idx>=0 and idx<len(self.data):
            dir,name = self.data[idx]
            self.images[(dir,name)]["checked"] = self.status['section']
            self.update_table()
            self.select_next_unchecked_image()

    def mark_delete(self):
        idx = self.currentIndex
        if idx>=0 and idx<len(self.data):
            dir,name = self.data[idx]
            self.images[(dir,name)]["checked"] = self.status['delete']
            self.update_table()
            self.select_next_unchecked_image()

    
    def update_table(self):
        folder_regex = re.compile(r"^([A-Z0-9\-]+)_(\d+)_(\d{14})_(\d*)_.*$",re.IGNORECASE)
        current_index = self.currentIndex
        if current_index>0 and current_index<len(self.data):
            current_dir, current_name=self.data[current_index]
        else:
            current_dir = self.ui.cmbSelectPN.currentText()
            current_name = ""

        self.data = [(dir,name) for dir,name in self.images.keys() if dir == current_dir]
        self.data.sort(key=lambda x: x[1])
        tableData=[]
        update = True
        for i,info in enumerate(self.data):
            dir,name = info
            match = folder_regex.match(name)
            if match:
                matrix = match.group(4)
            else:
                matrix = ""
            image = self.images[(dir,name)]
            tableData.append([matrix,image["status"],image['checked']])
            if name == current_name:
                current_index = i
                update = False
        
        self.tableModel=ImagesTableModel(tableData,self.TableHeaders)
        self.ui.tblImages.setModel(self.tableModel)
        
        if update:
            self.currentIndex = current_index
            self.select_table_row(current_index)
        

    def show_current_row(self):
        self.currentIndex = self.ui.tblImages.currentIndex().row()
        self.ui.tblImages.selectRow(self.currentIndex)
        self.show_selected_image(self.currentIndex)

    
    def select_table_row(self,idx:int):
        if idx<0 or idx>=len(self.data): return
        target_index = self.tableModel.index(idx,0)
        self.ui.tblImages.setCurrentIndex(target_index)
        self.show_current_row()

    def select_next_unchecked_image(self):
        if self.currentIndex<0 or len(self.data)==0 or self.currentIndex>=len(self.data):
            return
        idx=self.currentIndex
        idx += 1
        while idx<=len(self.data):
            if idx==len(self.data):
                idx = 0
            if idx==self.currentIndex:
                QMessageBox.information(self, "提示", "所有图片已确认，可将数据发送至板厚分析电脑。")
                return
            dir,name = self.data[idx]
            if not self.images[(dir,name)]["checked"]:
                self.currentIndex = idx
                self.select_table_row(idx)
                break
            idx += 1


    def show_selected_image(self,idx:int=-1):
        if idx>=0:
            self.currentIndex = idx
        else:
            idx = self.currentIndex
        if idx<0 or idx>len(self.data)-1:
            self.ui.imgCS.setPixmap(QPixmap())
            self.ui.imgSS.setPixmap(QPixmap())
            self.ui.lblTitle.setText("板厚图片")
            self.ui.lblComment.setText("")
        else:
            dir,name = self.data[idx]
            self.ui.lblTitle.setText("{} {}".format(self.images[(dir,name)]['checked'],name))
            self.ui.lblComment.setText("{} / {}".format(idx+1,len(self.data)))
            if self.images[(dir,name)]["status"] == self.status["ok"]:
                self.ui.imgCS.setPixmap(QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_CS.png")))
                self.ui.imgSS.setPixmap(QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_SS.png")))
            else:
                self.ui.imgCS.setPixmap(QPixmap())
                self.ui.imgSS.setPixmap(QPixmap())


    @Slot(list)
    def dir_updated(self, dirs: list):
        current_dir = self.ui.cmbSelectPN.currentText()
        self.ui.cmbSelectPN.clear()
        for dir in dirs:
            self.ui.cmbSelectPN.addItem(dir)
            if current_dir == dir:
                self.ui.cmbSelectPN.setCurrentText(dir)


    @Slot(str, str)
    def thumbnail_updated(self, dir:str, name:str, status:str):
        if status == "ok":
            if (dir,name) in self.images:
                self.images[(dir,name)]["status"] = self.status[status]
            else:
                self.images[(dir,name)] = {"status": self.status[status], "checked": ""}
        elif status == "error":
            if (dir,name) in self.images:
                self.images[(dir,name)]["status"] = self.status[status]
            else:
                self.images[(dir,name)] = {"status": self.status[status], "checked": ""}
        elif status == "delete":
            if (dir,name) in self.images:
                del self.images[(dir,name)]
        elif status == "new":
            self.images[(dir,name)] = {"status": "", "checked": ""}
        if self.ui.cmbSelectPN.currentText() == dir:
            if self.currentIndex >= 0 and self.currentIndex < len(self.data):
                name = self.data[self.currentIndex][1]
            else:
                name = ""
            self.update_table()
            self.currentIndex = -1
            for i in range(len(self.data)):
                if self.data[i][1] == name:
                    self.currentIndex = i
                    break
            if self.currentIndex >= 0:
                self.select_table_row(self.currentIndex)
            else:
                self.show_selected_image()


    @Slot(str)
    def error_occurred(self, error:str):
        QMessageBox.critical(self, "错误", error)



if __name__ == '__main__':
    app = QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))
    win = MainWindow()
    win.show()
    app.exec()
