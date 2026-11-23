#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

from PySide6.QtWidgets import (QApplication, QMainWindow, QMessageBox, QHeaderView,
                               QStyleFactory, QInputDialog)
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QObject, QThread, Signal, Slot, QMutex, QMutexLocker
from PySide6.QtGui import QPixmap, QColor, QBrush

from ui.MainWindow_ui import Ui_MainWindow
import resources_rc

from library import MonitorDir, parse_folder_name, make_folder_name, is_valid_qr
from collections import Counter
import shutil
import json
import sys
import os
import time



class ImagesTableModel(QAbstractTableModel):
    """左侧测量记录表格。二维码单元格在“为空 / 重复 / 人工指定过”时显示红色背景。"""
    QR_COLUMN = 0
    RED_BACKGROUND = QColor(211, 47, 47)
    RED_FOREGROUND = QColor(255, 255, 255)

    def __init__(self, data, headers, red_rows=None, red_tips=None):
        super().__init__()
        self._data=data
        self._headers=headers
        self._red_rows=set(red_rows or ())
        self._red_tips=dict(red_tips or {})

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._headers)

    def set_rows(self, rows, red_rows=None, red_tips=None):
        """刷新表格数据。行数不变时只发 dataChanged，避免整表重置导致
        滚动条位置和当前选中行被清掉。"""
        red_rows = set(red_rows or ())
        red_tips = dict(red_tips or {})
        if len(rows) == len(self._data):
            self._data = rows
            self._red_rows = red_rows
            self._red_tips = red_tips
            if rows:
                top = self.index(0, 0)
                bottom = self.index(len(rows) - 1, len(self._headers) - 1)
                self.dataChanged.emit(top, bottom,
                                      [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])
            return
        self.beginResetModel()
        self._data = rows
        self._red_rows = red_rows
        self._red_tips = red_tips
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        col = index.column()
        is_red = (col == self.QR_COLUMN and row in self._red_rows)
        if role == Qt.DisplayRole:
            if 0 <= row < len(self._data) and 0 <= col < len(self._data[row]):
                return self._data[row][col]
        elif role == Qt.TextAlignmentRole:
            return Qt.AlignCenter
        elif role == Qt.BackgroundRole:
            if is_red:
                return QBrush(self.RED_BACKGROUND)
        elif role == Qt.ForegroundRole:
            if is_red:
                return QBrush(self.RED_FOREGROUND)
        elif role == Qt.ToolTipRole:
            if is_red:
                return self._red_tips.get(row, "请核对二维码")
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if 0 <= section < len(self._headers):
                    return self._headers[section]
            else:  # 垂直表头，显示行号
                return str(section + 1)
        return None


class MoveWorker(QObject):
    """在后台线程逐个子文件夹执行 I/O，不阻塞主界面。
    遇到被锁的文件跳过该子文件夹，汇总报告，让用户下次重试。"""
    finished = Signal(str, list, list)  # dir_name, succeeded_names, failed_info[(name, err), ...]

    def __init__(self, config, dir_name, subfolder_actions, parent=None):
        """
        config            : 配置字典
        dir_name          : 当前型号目录名
        subfolder_actions : [(name, action), ...]
            action: "ok" / "delete"（"section" 为已废弃的切片板标记）
        """
        super().__init__(parent)
        self.config = config
        self.dir_name = dir_name
        self.subfolder_actions = subfolder_actions

    @Slot()
    def run(self):
        succeeded = []
        failed = []

        for name, action in self.subfolder_actions:
            if action == "delete":
                path = os.path.join(self.config["ImagesFolder"], self.dir_name, name)
                try:
                    self._robust_rmtree(path)
                    succeeded.append(name)
                except Exception as e:
                    failed.append((name, f"删除失败（文件可能被其他程序占用）:\n{e}"))

            elif action == "section":
                # 已废弃：切片板功能已删除，保留分支仅为兼容旧标记数据
                src = os.path.join(self.config["ImagesFolder"], self.dir_name, name)
                dst = os.path.join(self.config["ProcessFolder"], self.dir_name, name)
                try:
                    os.makedirs(os.path.join(self.config["ProcessFolder"], self.dir_name), exist_ok=True)
                    shutil.move(src, dst)
                    succeeded.append(name)
                except Exception as e:
                    failed.append((name, f"移动失败（文件可能被其他程序占用）:\n{e}"))

            else:  # "ok"
                src = os.path.join(self.config["ImagesFolder"], self.dir_name, name)
                dst = os.path.join(self.config["ProcessFolder"], self.dir_name, name)
                try:
                    os.makedirs(os.path.join(self.config["ProcessFolder"], self.dir_name), exist_ok=True)
                    shutil.move(src, dst)
                    succeeded.append(name)
                except Exception as e:
                    failed.append((name, f"移动失败（文件可能被其他程序占用）:\n{e}"))

        # 全部尝试完毕，通知主线程
        self.finished.emit(self.dir_name, succeeded, failed)

    def _robust_rmtree(self, path, max_retries=3, retry_delay=1.0):
        """遇到 PermissionError 时短暂等待重试（应对 Windows 文件锁短暂释放）"""
        for attempt in range(max_retries):
            try:
                shutil.rmtree(path)
                return
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
            except OSError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise


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

        # 只校验程序实际使用的目录；配置文件中遗留的其它 *Folder 项不再参与检查
        required_folders = ("ImagesFolder", "ThumbnailFolder", "ProcessFolder")
        for key in required_folders:
            value = self.config.get(key)
            if not value or not os.path.isdir(value):
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
        self.ui.btnMarkDelete.clicked.connect(self.mark_delete)
        self.ui.tblImages.clicked.connect(self.click_table_row)
        self.ui.tblImages.doubleClicked.connect(self.table_double_clicked)
        

    def closeEvent(self, event):
        self.worker.stop()
        self.thread.quit()
        if not self.thread.wait(3000):  # 等待3秒
            self.thread.terminate()  # 最后手段
            self.thread.wait()
        # 如果后台移动线程仍在运行，也安全终止
        if hasattr(self, 'move_thread') and self.move_thread is not None:
            if self.move_thread.isRunning():
                self.move_thread.quit()
                if not self.move_thread.wait(2000):
                    self.move_thread.terminate()
                    self.move_thread.wait()
        event.accept()


    def move_todo(self):
        """将当前型号已标记的子文件夹逐个发送至待处理文件夹（后台 I/O，不阻塞 UI）"""
        # 注意：监控线程会随时删除 self.images 中的条目，这里统一用 .get 取值，
        # 避免 KeyError 让本函数提前退出、界面按钮被禁用后无法恢复。

        # ── 防呆：二维码为空且未人工指定、也未标记删除的数据不允许发送 ──
        missing_qr = []
        for dir, name in self.data:
            info = self.images.get((dir, name))
            if info is None:
                continue
            parsed = parse_folder_name(name)
            if parsed is None or parsed["qr"] or info.get("manual"):
                continue
            if info.get("checked") == self.status['delete']:
                continue        # 已标记删除的异常图片，不算缺失
            missing_qr.append(name)

        if missing_qr:
            lines = "\n".join(f"  · {n}" for n in missing_qr[:10])
            if len(missing_qr) > 10:
                lines += f"\n  …（共 {len(missing_qr)} 块）"
            QMessageBox.warning(
                self, "二维码缺失",
                f"有 {len(missing_qr)} 块测量数据未读取到二维码，无法发送到板厚分析。\n\n"
                f"请手动指定二维码（双击左侧表格中的二维码单元格），\n"
                f"或删除异常数据后重新测量。\n\n{lines}")
            return

        # ── 快速验证（主线程，毫秒级） ──
        for dir, name in self.data:
            info = self.images.get((dir, name))
            if info is None:
                continue
            checked = info.get("checked", "")
            if checked == self.status['error'] or checked == "":
                QMessageBox.warning(self, "错误", "有未确认的板厚图片，请先标记所有待处理的板厚图片！")
                return

        # ── 收集待处理的子文件夹清单 ──
        dir = self.ui.cmbSelectPN.currentText()
        subfolder_actions = []
        for d, name in self.data:
            info = self.images.get((d, name))
            if info is None:
                continue
            checked = info.get("checked", "")
            if checked == self.status['delete']:
                subfolder_actions.append((name, "delete"))
            elif checked == self.status['section']:
                subfolder_actions.append((name, "section"))
            else:
                subfolder_actions.append((name, "ok"))

        if not subfolder_actions:
            return

        # ── 锁住界面按钮，启动后台线程 ──
        self.ui.btnMoveTodo.setEnabled(False)
        self.ui.btnMoveTodo.setText("正在处理…")
        self.ui.btnMarkOK.setEnabled(False)
        self.ui.btnMarkDelete.setEnabled(False)

        self._moving_dir = dir
        self.move_thread = QThread(self)
        self.move_worker = MoveWorker(self.config, dir, subfolder_actions)
        self.move_worker.moveToThread(self.move_thread)
        self.move_worker.finished.connect(self._move_finished)
        self.move_thread.started.connect(self.move_worker.run)
        # 必须等线程真正结束后再释放引用，否则 QThread 在 run() 尚未返回时被销毁
        self.move_thread.finished.connect(self._move_thread_finished)
        self.move_thread.finished.connect(self.move_thread.deleteLater)
        self.move_thread.start()

    def _move_finished(self, dir_name, succeeded, failed):
        """后台处理完毕━━更新界面并显示汇总"""
        # 从 self.images 中移除已处理的子文件夹
        for name in succeeded:
            key = (dir_name, name)
            if key in self.images:
                del self.images[key]

        # 更新当前数据（只保留失败项）
        failed_names = {f[0] for f in failed}
        self.data = [(d, n) for d, n in self.data if n in failed_names]
        self.currentIndex = -1
        self.update_table()
        self.clear_current_image()

        # 如果全部成功，删除空的型号目录
        if not failed:
            pn_path = os.path.join(self.config["ImagesFolder"], dir_name)
            try:
                if os.path.isdir(pn_path) and not os.listdir(pn_path):
                    os.rmdir(pn_path)
            except Exception:
                pass  # 删不掉也无所谓

        # 恢复按钮
        self.ui.btnMoveTodo.setEnabled(True)
        self.ui.btnMoveTodo.setText("发送到板厚分析")
        self.ui.btnMarkOK.setEnabled(True)
        self.ui.btnMarkDelete.setEnabled(True)

        # 让后台线程退出事件循环，finished 信号会回收线程对象
        if self.move_thread is not None:
            self.move_thread.quit()

        # 汇总弹窗
        total = len(succeeded) + len(failed)
        if not failed:
            QMessageBox.information(self, "完成",
                f"{dir_name}\n\n已成功处理全部 {total} 个子文件夹，数据已发送至待处理文件夹。")
        else:
            failed_lines = "\n".join([f"  ⚠ {name}: {err.splitlines()[0]}" for name, err in failed])
            QMessageBox.warning(self, "部分完成",
                f"{dir_name}\n\n"
                f"✅ 成功处理 {len(succeeded)} / {total} 个子文件夹\n"
                f"❌ {len(failed)} 个文件夹处理失败：\n\n{failed_lines}\n\n"
                f"请关闭占用该文件夹的程序（拍照软件、资源管理器等），\n"
                f"然后重新点击「发送到板厚分析」重试。")

    @Slot()
    def _move_thread_finished(self):
        """后台移动线程真正退出后才释放引用，避免销毁仍在运行的 QThread"""
        self.move_thread = None
        self.move_worker = None


    def mark_ok(self):
        self.mutex.lock()
        idx = self.currentIndex
        if idx<0 or idx>=len(self.data):
            self.mutex.unlock()
            QMessageBox.warning(self, "错误", "请选择待处理的图片！")
            return
        try:
            dir,name = self.data[idx]
            info = self.images.get((dir,name))
            if info is None or info.get("status")!=self.status['ok']:
                self.mutex.unlock()
                QMessageBox.warning(self, "错误", "请等待当前图片缩略图生成完成！")
                return
            info["checked"] = self.status['ok']
        except Exception as e:
            self.mutex.unlock()
            QMessageBox.critical(self, "错误", f"无法确认当前图片:\n{e}")
            return
        self.mutex.unlock()
        self.update_table()
        self.select_next_unchecked_image()

    def mark_delete(self):
        self.mutex.lock()
        idx = self.currentIndex
        if idx<0 or idx>=len(self.data):
            self.mutex.unlock()
            QMessageBox.warning(self, "错误", "请选择待处理的图片！")
            return
        try:
            dir,name = self.data[idx]
            info = self.images.get((dir,name))
            if info is None or info.get("status")!=self.status['ok']:
                self.mutex.unlock()
                QMessageBox.warning(self, "错误", "请等待当前图片缩略图生成完成！")
                return
            info["checked"] = self.status['delete']
        except Exception as e:
            self.mutex.unlock()
            QMessageBox.critical(self, "错误", f"无法确认当前图片:\n{e}")
            return
        self.mutex.unlock()
        self.update_table()
        self.select_next_unchecked_image()

    @Slot()
    def selected_pn_changed(self):
        self.currentIndex = -1
        self.update_table()
        self.clear_current_image()

    def update_table(self):
        # 根据当前选择的型号更新表格数据、二维码标红状态与底部统计
        # 已标记删除(❌)的记录视为已排除的异常数据：不标红、不参与重复判定、不计入统计
        select_dir = self.ui.cmbSelectPN.currentText()
        rows = []
        red_rows = set()
        red_tips = {}
        measured = valid = missing = 0
        with QMutexLocker(self.mutex):
            try:
                self.data = [(dir,name) for dir,name in list(self.images.keys()) if dir == select_dir]
                self.data.sort(key=lambda x: x[1])
                infos = [self.images.get(key, {}) for key in self.data]
                qrs = []
                for _d, name in self.data:
                    parsed = parse_folder_name(name)
                    qrs.append(parsed["qr"] if parsed else "")

                # 只有未标记删除的记录参与标红与统计
                alive = {i for i, info in enumerate(infos)
                         if info.get("checked") != self.status['delete']}
                qr_counts = Counter(qrs[i] for i in alive if qrs[i])

                for i, info in enumerate(infos):
                    qr = qrs[i]
                    rows.append([qr, info.get("status",""), info.get("checked","")])
                    if i not in alive:
                        continue        # 已标记删除，不再提示
                    if not qr:
                        red_rows.add(i)
                        red_tips[i] = "未读取到二维码：双击本单元格可手动指定"
                    elif not is_valid_qr(qr):
                        red_rows.add(i)
                        red_tips[i] = ("二维码格式异常（应为 10 位数字）：不支持手动修改，"
                                       "请核对该板数据或标记删除后重测")
                    elif qr_counts[qr] > 1:
                        red_rows.add(i)
                        red_tips[i] = f"二维码重复：当前型号下有 {qr_counts[qr]} 块相同二维码"
                    elif info.get("manual"):
                        red_rows.add(i)
                        red_tips[i] = "二维码为人工指定，请核对后再确认"

                measured = len(alive)
                valid = sum(1 for i in alive if qrs[i] and qr_counts[qrs[i]] == 1)
                missing = sum(1 for i in alive if not qrs[i])
            except Exception as e:
                QMessageBox.critical(self, "错误", f"无法更新当前图片列表数据:\n{e}")
                return

        self.tableModel.set_rows(rows, red_rows, red_tips)
        self.ui.statusbar.showMessage(
            f"已测量 {measured} 块，其中有效数据 {valid} 块，未读取到二维码 {missing} 块。")

    @Slot()
    def click_table_row(self):
        self.currentIndex = self.ui.tblImages.currentIndex().row()
        dir,name = self.get_current_image()
        self.select_table_row(dir,name)

    @Slot(QModelIndex)
    def table_double_clicked(self, index):
        """双击二维码单元格：仅当该记录二维码为空时，允许人工指定二维码"""
        if not index.isValid() or index.column() != ImagesTableModel.QR_COLUMN:
            return
        row = index.row()
        with QMutexLocker(self.mutex):
            if row < 0 or row >= len(self.data):
                return
            dir_name, name = self.data[row]
            info = self.images.get((dir_name, name))
            if info is None:
                return
        parsed = parse_folder_name(name)
        if parsed is None:
            return
        if parsed["qr"]:
            # 二维码已存在：不允许在此修改（格式异常的历史数据同样不允许）
            if not is_valid_qr(parsed["qr"]):
                QMessageBox.information(
                    self, "无法修改",
                    "该记录的二维码格式异常（不是 10 位数字），不支持手动修改。\n"
                    "请核对该板数据；若确认是异常测量数据，请点击\n"
                    "「删除当前异常图片」后重新测量。")
            return
        self.ask_manual_qr(dir_name, name, parsed)

    def collect_qr_codes(self, dir_name, exclude_name=None):
        """收集当前型号下已存在的有效二维码，用于人工输入时的重复校验"""
        codes = set()
        with QMutexLocker(self.mutex):
            for d, n in list(self.images.keys()):
                if d != dir_name or n == exclude_name:
                    continue
                parsed = parse_folder_name(n)
                if parsed and parsed["qr"]:
                    codes.add(parsed["qr"])
        return codes

    def ask_manual_qr(self, dir_name, name, parsed):
        """弹窗让用户输入 10 位二维码，格式或重复校验通过后改名数据文件夹"""
        existing = self.collect_qr_codes(dir_name, exclude_name=name)
        value = ""
        while True:
            text, ok = QInputDialog.getText(
                self, "手动指定二维码",
                f"测量数据：\n{name}\n\n"
                f"该记录未读取到二维码，请输入 10 位二维码\n"
                f"（不能与当前型号下已有二维码重复）：",
                text=value)
            if not ok:
                return
            qr = text.strip()
            if not is_valid_qr(qr):
                QMessageBox.warning(self, "格式错误", "二维码必须是 10 位数字，请重新输入！")
                value = qr
                continue
            if qr in existing:
                QMessageBox.warning(self, "二维码重复",
                                    f"二维码 {qr} 已被当前型号下的其它测量数据使用，\n请重新输入！")
                value = qr
                continue
            break

        self.apply_manual_qr(dir_name, name, parsed, qr)

    def apply_manual_qr(self, dir_name, name, parsed, qr):
        """把人工指定的二维码写入文件夹名（同时改名缩略图），并保持该单元格红色标记"""
        new_name = make_folder_name(parsed["model"], parsed["order"],
                                    parsed["time"], qr, parsed["rest"])
        if new_name == name:
            return

        # 先冻结监控线程对该条目的处理，改名后再迁移主线程状态
        self.worker.claim(dir_name, name)
        try:
            self.worker.apply_rename(dir_name, name, new_name)
        except FileExistsError as e:
            QMessageBox.warning(self, "无法修改",
                                f"{e}\n\n请改用其它二维码后再试。")
            return
        except Exception as e:
            QMessageBox.critical(self, "错误", f"重命名测量数据文件夹失败：\n{e}")
            return
        finally:
            self.worker.release(dir_name, name)

        with QMutexLocker(self.mutex):
            info = self.images.pop((dir_name, name), None)
            if info is None:
                info = {"status": "", "checked": ""}
            info["manual"] = True          # 人工指定过的记录保持红色提醒
            self.images[(dir_name, new_name)] = info

        self.update_table()
        self.select_table_row(dir_name, new_name)

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
                    self.ui.tblImages.clearFocus()
                    self.ui.tblImages.clearSelection()
                self.currentIndex = idx
            except Exception as e:
                pass
        self.show_selected_image()

    def select_next_unchecked_image(self):
        """自动跳到第一块未确认的图片；全部确认完毕则提示并清空预览"""
        target = None
        total = 0
        with QMutexLocker(self.mutex):
            total = len(self.data)
            for d, n in self.data:
                info = self.images.get((d, n))
                if info is not None and not info.get("checked"):
                    target = (d, n)
                    break
        if target is not None:
            self.select_table_row(*target)
            return
        if total > 0:
            QMessageBox.information(self, "提示", "所有图片已确认，可将数据发送至板厚分析电脑。")
        self.currentIndex = -1
        self.ui.tblImages.clearSelection()
        self.clear_current_image()

    def clear_current_image(self):
        self.ui.lblTitle.setText("板厚图片")
        self.ui.lblComment.setText("")
        self.ui.imgCS.setPixmap(QPixmap())
        self.ui.imgSS.setPixmap(QPixmap())

    def show_selected_image(self):
        self.mutex.lock()
        try:
            idx = self.currentIndex
            length = len(self.data)
            if idx<0 or idx>length-1:
                self.clear_current_image()
                return
            dir,name = self.data[idx]
            info = self.images.get((dir,name)) or {}
            status = info.get("status","")
            checked = info.get("checked","")
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
                imgSS = QPixmap(os.path.join(self.config["ThumbnailFolder"], dir, name+"_SS.png")).scaled(
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

    @Slot(str, str, str)
    def thumbnail_updated(self, dir:str, name:str, status:str):
        # 更新收集的图片信息
        with QMutexLocker(self.mutex):
            current_dir = self.ui.cmbSelectPN.currentText()
            try:
                if status in ("ok", "error"):
                    if (dir, name) not in self.images:
                        # 文件夹可能刚被人工改名或删除，丢弃这条过期信号，
                        # 否则会生成一条指向已不存在文件夹的幽灵记录
                        if not os.path.isdir(os.path.join(self.config["ImagesFolder"], dir, name)):
                            return
                        self.images[(dir, name)] = {"status": "", "checked": "", "manual": False}
                    self.images[(dir, name)]["status"] = self.status[status]
                elif status == "delete":
                    self.images.pop((dir, name), None)
                elif status == "new":
                    info = self.images.get((dir, name))
                    if info is None:
                        self.images[(dir, name)] = {"status": "", "checked": "", "manual": False}
                    else:
                        info["status"] = ""
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



def install_excepthook():
    """打包为 --noconsole 后 stderr 不可见，槽函数里的未捕获异常会静默丢失。
    这里把异常写入同目录 error.log，便于排查“点了按钮没反应”的问题。"""
    import traceback
    import datetime

    def hook(exc_type, exc_value, exc_tb):
        try:
            text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
            with open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "error.log"),
                      "a", encoding="utf-8") as f:
                f.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{text}\n")
        except Exception:
            pass
        if sys.stderr is not None:
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = hook


if __name__ == '__main__':
    install_excepthook()
    app = QApplication([])
    app.setStyle(QStyleFactory.create("Fusion"))
    win = MainWindow()
    win.show()
    app.exec()
