#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QFileDialog, QHeaderView, QStyleFactory
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, Signal, Slot
from PySide6.QtGui import QPixmap

from ui.MainWindow_ui import Ui_MainWindow
import resources_rc

from library import MonitorDir
from threading import Lock
import shutil
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
        self.lock = Lock()
        self.dirs = []      # 监控目录中的所有型号文件夹清单
        self.images = {}    # 保存的图片信息数据，{(dir,name)} = {"status": status, "checked": checked}
        self.data = []      # 当前型号的图片清单 [(dir,name)]
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
            "ImagesFolder":"E:/PCBImages",
            "ThumbnailFolder":"E:/PCBThumbnails",
            "SectionFolder":"E:/PCBSections",
            "ProcessFolder":"E:/PCBThickness"
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
        self.ui.cmbSelectPN.currentIndexChanged.connect(self.selected_pn_changed)
        self.ui.btnMoveTodo.clicked.connect(self.move_todo)
        self.ui.btnMarkOK.clicked.connect(self.mark_ok)
        self.ui.btnMarkSection.clicked.connect(self.mark_section)
        self.ui.btnMarkDelete.clicked.connect(self.mark_delete)
        self.ui.tblImages.clicked.connect(self.click_table_row)
        

    def closeEvent(self, event):
        self.worker.stop()
        self.thread.quit()
        if not self.thread.wait(3000):  # 等待3秒
            self.thread.terminate()  # 最后手段
            self.thread.wait()
        event.accept()


    def move_todo(self):
        self.lock.acquire()
        for dir,name in self.data:
            checked=self.images[(dir,name)]["checked"]
            if checked==self.status['error'] or checked=="":
                self.lock.release()
                QMessageBox.warning(self, "错误", "有未确认的板厚图片，请先标记所有待处理的板厚图片！")
                return
        
        for dir,name in self.data:
            checked=self.images[(dir,name)]["checked"]
            if checked==self.status['delete']:
                try:
                    shutil.rmtree(os.path.join(self.config["ImagesFolder"], dir, name))
                except Exception as e:
                    self.lock.release()
                    QMessageBox.critical(self, "错误", f"无法删除指定的文件夹:\n{e}")
                    return
            elif checked==self.status['section']:
                try:
                    if not os.path.isdir(os.path.join(self.config["SectionFolder"], dir)):
                        os.mkdir(os.path.join(self.config["SectionFolder"], dir))
                        with open(os.path.join(self.config["SectionFolder"], dir, name+".txt"), "w") as f:
                            f.write("")
                except Exception as e:
                    self.lock.release()
                    QMessageBox.critical(self, "错误", f"无法输出切片板信息至指定路径:\n{e}")
                    return
                
        try:
            dir = self.ui.cmbSelectPN.currentText()
            shutil.move(os.path.join(self.config["ImagesFolder"], dir), os.path.join(self.config["ProcessFolder"], dir))
        except Exception as e:
            self.lock.release()
            QMessageBox.critical(self, "错误", f"无法移动当前型号数据至待处理文件夹:\n{e}")
            return
        self.lock.release()
        QMessageBox.information(self, "成功", f"已将 {dir} 数据移发送至板厚分析待处理！")
    



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

    @Slot()
    def selected_pn_changed(self):
        self.currentIndex = -1
        self.update_table()
        self.clear_current_image()

    def update_table(self):
        # 根据当前选择的型号更新表格数据
        folder_regex = re.compile(r"^([A-Z0-9\-]+)_(\d+)_(\d{14})_(\d*)_.*$",re.IGNORECASE)
        select_dir = self.ui.cmbSelectPN.currentText()
        with self.lock:
            self.data = [(dir,name) for dir,name in self.images.keys() if dir == select_dir]
            self.data.sort(key=lambda x: x[1])
            tableData=[]
            for i,info in enumerate(self.data):
                dir,name = info
                match = folder_regex.match(name)
                if match:
                    matrix = match.group(4)
                else:
                    matrix = ""
                image = self.images[(dir,name)]
                tableData.append([matrix,image["status"],image['checked']])
        
        self.tableModel=ImagesTableModel(tableData,self.TableHeaders)
        self.ui.tblImages.setModel(self.tableModel)

    @Slot()
    def click_table_row(self):
        self.currentIndex = self.ui.tblImages.currentIndex().row()
        dir,name = self.get_current_image()
        self.select_table_row(dir,name)

    def get_current_image(self):
        # 获取当前选中的图片信息
        with self.lock:
            idx = self.currentIndex
            if idx>=0 and idx<len(self.data):
                dir,name = self.data[idx]
            else:
                dir=""
                name=""
        return dir,name

    def select_table_row(self,dir,name):
        if not dir: return
        with self.lock:
            if (dir,name) in self.data:
                idx = self.data.index((dir,name))
                target_index = self.tableModel.index(idx,0)
                self.ui.tblImages.setCurrentIndex(target_index)
                self.ui.tblImages.selectRow(idx)
            else:
                idx = -1
                self.ui.tblImages.clearFocusr()
                self.ui.tblImages.clearSelection()
            self.currentIndex = idx
        self.show_selected_image()

    def select_next_unchecked_image(self):
        dir,name = self.get_current_image()
        with self.lock:
            idx=self.currentIndex
            length = len(self.data)
            unchecked = False
            if idx<0 or length==0 or idx>=length:
                unchecked = True
            else:
                for i,info in enumerate(self.data):
                    dir,name = info
                    if not self.images[(dir,name)]["checked"]:
                        self.currentIndex = idx
                        unchecked = True
                        break
        if unchecked:
            self.select_table_row(dir,name)
        else:
            QMessageBox.information(self, "提示", "所有图片已确认，可将数据发送至板厚分析电脑。")
            self.clear_current_image()

    def clear_current_image(self):
        self.ui.lblTitle.setText("板厚图片")
        self.ui.lblComment.setText("")
        self.ui.imgCS.setPixmap(QPixmap())
        self.ui.imgSS.setPixmap(QPixmap())

    def show_selected_image(self):
        self.lock.acquire()
        idx = self.currentIndex
        length = len(self.data)

        if idx<0 or idx>length-1:
            self.clear_current_image()
            self.lock.release()
            return
        else:
            dir,name = self.data[idx]
            info=self.images[(dir,name)]
            status = info["status"]
            checked = info["checked"]
            self.lock.release()
            self.ui.lblTitle.setText("{} {}".format(checked,name))
            self.ui.lblComment.setText("{} / {}".format(idx+1,length))
            if status == self.status["ok"]:
                self.ui.imgCS.setPixmap(QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_CS.png")))
                self.ui.imgSS.setPixmap(QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_SS.png")))
            else:
                self.ui.imgCS.setPixmap(QPixmap())
                self.ui.imgSS.setPixmap(QPixmap())


    @Slot(list)
    def dir_updated(self, dirs: list):
        self.ui.cmbSelectPN.currentIndexChanged.disconnect(self.selected_pn_changed)
        with self.lock:
            current_dir = self.ui.cmbSelectPN.currentText()
            self.ui.cmbSelectPN.clear()
            dir_changed=True
            for dir in dirs:
                self.ui.cmbSelectPN.addItem(dir)
                if current_dir == dir:
                    dir_changed=False
                    self.ui.cmbSelectPN.setCurrentText(dir)

        self.ui.cmbSelectPN.currentIndexChanged.connect(self.selected_pn_changed)
        if dir_changed:
            self.selected_pn_changed()



    @Slot(str, str)
    def thumbnail_updated(self, dir:str, name:str, status:str):
        # 更新收集的图片信息
        with self.lock:
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

        # 如果更新的数据为当前选择的型号，则更新表格
        if self.ui.cmbSelectPN.currentText() == dir:
            self.update_table()

        current_dir,current_name = self.get_current_image()
        if current_dir == dir:
            self.show_selected_image()
            self.select_table_row(current_dir,current_name)


    @Slot(str)
    def error_occurred(self, error:str):
        QMessageBox.critical(self, "错误", error)



if __name__ == '__main__':
    app = QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))
    win = MainWindow()
    win.show()
    app.exec()
