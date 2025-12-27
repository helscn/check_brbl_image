#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QHeaderView, QStyleFactory
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QThread, Signal, Slot, QMutex, QMutexLocker
from PySide6.QtGui import QPixmap

from ui.MainWindow_ui import Ui_MainWindow
import resources_rc

from library import MonitorDir
import shutil
import json
import re
import sys
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
        self.mutex = QMutex()
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
        self.config={
            "ImagesFolder":"D:\\PCBImages",
            "ThumbnailFolder":"Z:\\PCBImages",
            "SectionFolder":"Z:\\PCBSections",
            "ProcessFolder":"D:\\PCBThickness"
        }
        if os.path.isfile("config.json"):
            try:
                with open("config.json", "r") as f:
                    self.config.update(json.load(f))
            except Exception as e:
                QMessageBox.critical(self, "配置文件错误", f"无法读取配置文件:\n{e}")
        else:
            try:
                with open("config.json", "w") as f:
                    json.dump(self.config, f, indent=4)
            except Exception as e:
                QMessageBox.critical(self, "配置文件错误", f"无法创建配置文件:\n{e}")

        for key,value in self.config.items():
            if key.endswith("Folder"):
                if not os.path.isdir(value):
                    QMessageBox.critical(self, "配置文件错误", f"设置项 {key} 指定的目录不存在:\n{value}")
                    sys.exit(1)
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
        self.mutex.lock()
        for dir,name in self.data:
            checked=self.images[(dir,name)]["checked"]
            if checked==self.status['error'] or checked=="":
                self.mutex.unlock()
                QMessageBox.warning(self, "错误", "有未确认的板厚图片，请先标记所有待处理的板厚图片！")
                return
        
        for dir,name in self.data:
            checked=self.images[(dir,name)]["checked"]
            if checked==self.status['delete']:
                try:
                    shutil.rmtree(os.path.join(self.config["ImagesFolder"], dir, name))
                except Exception as e:
                    self.mutex.unlock()
                    QMessageBox.critical(self, "错误", f"无法删除指定的文件夹:\n{e}")
                    return
            elif checked==self.status['section']:
                try:
                    if not os.path.isdir(os.path.join(self.config["SectionFolder"], dir)):
                        os.mkdir(os.path.join(self.config["SectionFolder"], dir))
                        with open(os.path.join(self.config["SectionFolder"], dir, name+".txt"), "w") as f:
                            f.write("")
                except Exception as e:
                    self.mutex.unlock()
                    QMessageBox.critical(self, "错误", f"无法输出切片板信息至指定路径:\n{e}")
                    return
                
        try:
            dir = self.ui.cmbSelectPN.currentText()
            shutil.move(os.path.join(self.config["ImagesFolder"], dir), os.path.join(self.config["ProcessFolder"], dir))
        except Exception as e:
            self.mutex.unlock()
            QMessageBox.critical(self, "错误", f"无法移动当前型号数据至待处理文件夹:\n{e}")
            return
        self.mutex.unlock()
        QMessageBox.information(self, "成功", f"已将 {dir} 数据移发送至板厚分析待处理！")
    



    def mark_ok(self):
        self.mutex.lock()
        idx = self.currentIndex
        if idx<0 and idx>=len(self.data):
            self.mutex.unlock()
            QMessageBox.warning(self, "错误", "请选择待处理的图片！")
            return
        try:
            dir,name = self.data[idx]
            if self.images[(dir,name)]["status"]!=self.status['ok']:
                self.mutex.unlock()
                QMessageBox.warning(self, "错误", "请等待当前图片缩略图生成完成！")
                return
            self.images[(dir,name)]["checked"] = self.status['ok']
        except Exception as e:
            self.mutex.unlock()
            QMessageBox.critical(self, "错误", f"无法确认当前图片:\n{e}")
            return
        self.mutex.unlock()
        self.update_table()
        self.select_next_unchecked_image()

    def mark_section(self):
        self.mutex.lock()
        idx = self.currentIndex
        if idx<0 and idx>=len(self.data):
            self.mutex.unlock()
            QMessageBox.warning(self, "错误", "请选择待处理的图片！")
            return
        try:
            dir,name = self.data[idx]
            if self.images[(dir,name)]["status"]!=self.status['ok']:
                self.mutex.unlock()
                QMessageBox.warning(self, "错误", "请等待当前图片缩略图生成完成！")
                return
            self.images[(dir,name)]["checked"] = self.status['section']
        except Exception as e:
            self.mutex.unlock()
            QMessageBox.critical(self, "错误", f"无法确认当前图片:\n{e}")
        self.mutex.unlock()
        self.update_table()
        self.select_next_unchecked_image()

    def mark_delete(self):
        self.mutex.lock()
        idx = self.currentIndex
        if idx<0 and idx>=len(self.data):
            self.mutex.unlock()
            QMessageBox.warning(self, "错误", "请选择待处理的图片！")
            return
        try:
            dir,name = self.data[idx]
            if self.images[(dir,name)]["status"]!=self.status['ok']:
                self.mutex.unlock()
                QMessageBox.warning(self, "错误", "请等待当前图片缩略图生成完成！")
                return
            self.images[(dir,name)]["checked"] = self.status['delete']
        except Exception as e:
            self.mutex.unlock()
            QMessageBox.critical(self, "错误", f"无法确认当前图片:\n{e}")
        self.mutex.unlock()
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
        with QMutexLocker(self.mutex):
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法更新当前图片列表数据:\n{e}")

    @Slot()
    def click_table_row(self):
        self.currentIndex = self.ui.tblImages.currentIndex().row()
        dir,name = self.get_current_image()
        self.select_table_row(dir,name)

    def get_current_image(self):
        # 获取当前选中的图片信息
        dir=""
        name=""
        with QMutexLocker(self.mutex):
            try:
                idx = self.currentIndex
                if idx>=0 and idx<len(self.data):
                    dir,name = self.data[idx]
            except Exception as e:
                pass
        return dir,name

    def select_table_row(self,dir,name):
        if not dir: return
        with QMutexLocker(self.mutex):
            try:
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
            except Exception as e:
                pass
        self.show_selected_image()

    def select_next_unchecked_image(self):
        dir,name = self.get_current_image()
        with QMutexLocker(self.mutex):
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
        self.mutex.lock()
        idx = self.currentIndex
        length = len(self.data)
        if idx<0 or idx>length-1:
            self.clear_current_image()
            self.mutex.unlock()
            return
        else:
            try:
                dir,name = self.data[idx]
                info=self.images[(dir,name)]
                status = info["status"]
                checked = info["checked"]
            finally:
                self.mutex.unlock()
            try:
                self.ui.lblTitle.setText("{} {}".format(checked,name))
                self.ui.lblComment.setText("{} / {}".format(idx+1,length))
                if status == self.status["ok"]:
                    imgCS = QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_CS.png")).scaled(
                        self.ui.imgCS.size(), 
                        Qt.KeepAspectRatio,  # 保持宽高比
                        Qt.SmoothTransformation  # 平滑缩放
                    )
                    imgSS = QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_CS.png")).scaled(
                        self.ui.imgSS.size(), 
                        Qt.KeepAspectRatio,  # 保持宽高比
                        Qt.SmoothTransformation  # 平滑缩放
                    )
                    self.ui.imgCS.setPixmap(imgCS)
                    self.ui.imgSS.setPixmap(imgSS)
                else:
                    self.ui.imgCS.setPixmap(QPixmap())
                    self.ui.imgSS.setPixmap(QPixmap())
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法载入缩略图：{e}")


    @Slot(list)
    def dir_updated(self, dirs: list):
        self.ui.cmbSelectPN.currentIndexChanged.disconnect(self.selected_pn_changed)
        dir_changed = True
        with QMutexLocker(self.mutex):
            try:
                current_dir = self.ui.cmbSelectPN.currentText()
                self.ui.cmbSelectPN.clear()
                for dir in dirs:
                    self.ui.cmbSelectPN.addItem(dir)
                    if current_dir == dir:
                        dir_changed=False
                        self.ui.cmbSelectPN.setCurrentText(dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法更新型号列表：{e}")

        self.ui.cmbSelectPN.currentIndexChanged.connect(self.selected_pn_changed)
        if dir_changed:
            self.selected_pn_changed()

    @Slot(str, str)
    def thumbnail_updated(self, dir:str, name:str, status:str):
        # 更新收集的图片信息
        with QMutexLocker(self.mutex):
            current_dir = self.ui.cmbSelectPN.currentText()
            try:
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
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法更新图片信息：{e}")

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
