from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt, Signal, Slot, QObject
import os
import re
import time
import threading


# 测量数据文件夹命名：型号_工单_测量时间(14位)_二维码_板厚
# 例：Q16132123A6_000030902370_20261120050334_3090237031_2.7mm
# 未读取到二维码时二维码字段为空，形如 ..._20261120050744__2.7mm
FOLDER_PATTERN = r"^(?P<model>[A-Za-z0-9\-]+)_(?P<order>\d+)_(?P<time>\d{14})_(?P<qr>\d*)_(?P<rest>.*)$"
FOLDER_REGEX = re.compile(FOLDER_PATTERN)

# 人工指定的二维码格式：10 位数字
QR_PATTERN = r"\d{10}"
QR_REGEX = re.compile(QR_PATTERN)


def parse_folder_name(name):
    """解析测量数据文件夹名，返回字段字典；格式不符返回 None。
    字段：model(型号)、order(工单)、time(测量时间)、qr(二维码，可能为空串)、rest(板厚等剩余部分)"""
    match = FOLDER_REGEX.match(name)
    return match.groupdict() if match else None


def make_folder_name(model, order, tm, qr, rest):
    """按 型号_工单_测量时间_二维码_板厚 重新拼装文件夹名"""
    return f"{model}_{order}_{tm}_{qr}_{rest}"


def is_valid_qr(qr):
    """二维码字段是否有效（10 位数字）"""
    return bool(QR_REGEX.fullmatch(qr or ""))


class MonitorDir(QObject):
    # 定义线程间通信信号
    dir_updated = Signal(list)
    thumbnail_updated = Signal(str, str, str)      # dir, name, status(ok,error,delete,new)
    error_occurred = Signal(str)

    def __init__(self, monitor_path, thumbnail_path, interval=5):
        super().__init__()
        self.monitor_path = monitor_path
        self.thumbnail_path = thumbnail_path
        self.dirs = []
        self.images = {}            # (dir, name) -> 文件夹修改时间，仅在工作线程内读写
        self.interval = interval
        self._stop = False
        # 主线程（改名等外部修改）与工作线程之间共享的状态锁
        self._state_lock = threading.RLock()
        self._claimed = set()       # 主线程正在外部修改的 (dir, name)，工作线程需跳过

    # ───────────── 供主线程安全修改工作线程状态 ─────────────

    def claim(self, dir_name, name):
        """声明某条测量数据正被主线程修改，工作线程本轮跳过它"""
        with self._state_lock:
            self._claimed.add((dir_name, name))

    def release(self, dir_name, name):
        with self._state_lock:
            self._claimed.discard((dir_name, name))

    def _is_claimed(self, key):
        with self._state_lock:
            return key in self._claimed

    def apply_rename(self, dir_name, old_name, new_name):
        """把测量数据文件夹改名为 new_name，并同步改名缩略图文件。

        同时把内部的 mtime 记录迁移到新名字上，避免改名后被监控线程
        当成新数据重新生成缩略图（既慢又可能出现旧的幽灵记录）。
        """
        with self._state_lock:
            old_path = os.path.join(self.monitor_path, dir_name, old_name)
            new_path = os.path.join(self.monitor_path, dir_name, new_name)
            if not os.path.isdir(old_path):
                raise FileNotFoundError(f"测量数据文件夹不存在：\n{old_path}")
            if os.path.exists(new_path):
                raise FileExistsError(f"目标文件夹已存在：\n{new_path}")
            os.rename(old_path, new_path)

            thumb_dir = os.path.join(self.thumbnail_path, dir_name)
            for suffix in ("_CS.png", "_SS.png"):
                old_thumb = os.path.join(thumb_dir, old_name + suffix)
                new_thumb = os.path.join(thumb_dir, new_name + suffix)
                if os.path.isfile(old_thumb):
                    try:
                        os.replace(old_thumb, new_thumb)
                    except OSError:
                        # 缩略图改名失败不影响主流程，最坏情况是重新生成一次
                        pass

            self.images.pop((dir_name, old_name), None)
            try:
                self.images[(dir_name, new_name)] = os.stat(new_path).st_mtime
            except OSError:
                self.images[(dir_name, new_name)] = time.time()

    # ───────────── 工作线程 ─────────────

    @Slot()
    def start_monitor(self):
        """线程主函数"""

        # 搜索已存在的子文件夹
        self.dirs = []
        try:
            for entry in os.scandir(self.monitor_path):
                if entry.is_dir():
                    self.dirs.append(entry.name)
            self.dirs.sort()
            self.dir_updated.emit(self.dirs)
        except:
            pass

        # 搜索子文件夹中的测量图片
        try:
            for dir in self.dirs:
                for entry in os.scandir(os.path.join(self.monitor_path, dir)):
                    if entry.is_dir() and FOLDER_REGEX.match(entry.name):
                        self.thumbnail_updated.emit(dir, entry.name, "new")
        except:
            pass

        # 监控文件夹内图片文件变化
        while not self._stop:
            # 判断监控文件夹是否有新型号
            current_dirs = []
            try:
                for entry in os.scandir(self.monitor_path):
                    if entry.is_dir():
                        current_dirs.append(entry.name)
                current_dirs.sort()
                if current_dirs != self.dirs:
                    self.dirs = current_dirs
                    self.dir_updated.emit(current_dirs)
            except Exception as e:
                pass

            # 删除不存在的图片文件夹数据
            to_be_deleted = []
            try:
                with self._state_lock:
                    pending = list(self.images.keys())
                for dir, name in pending:
                    if self._stop: return
                    if not os.path.isdir(os.path.join(self.monitor_path, dir, name)):
                        to_be_deleted.append((dir, name))
                for dir, name in to_be_deleted:
                    with self._state_lock:
                        self.images.pop((dir, name), None)
                    self.thumbnail_updated.emit(dir, name, "delete")
            except Exception as e:
                pass

            # 创建图片文件
            created_images_count = 0
            try:
                for dir in list(self.dirs):
                    if created_images_count>=3: break        # 一次最多处理3个图片文件夹
                    try:
                        entries = list(os.scandir(os.path.join(self.monitor_path, dir)))
                    except OSError:
                        continue
                    for entry in entries:
                        if self._stop: return
                        if not entry.is_dir():
                            continue
                        name = entry.name
                        if not FOLDER_REGEX.match(name):
                            continue
                        key = (dir, name)
                        if self._is_claimed(key):
                            continue
                        try:
                            mtime = entry.stat().st_mtime
                        except OSError:
                            continue
                        with self._state_lock:
                            known = self.images.get(key)
                        if known is not None and mtime <= known:
                            continue

                        # 读图/拼图是耗时操作，不持锁，避免拖住主线程改名
                        info = self.get_images(entry.path)
                        if self._is_claimed(key):
                            continue        # 期间被主线程改名/删除，丢弃本次结果
                        if info is None:
                            with self._state_lock:
                                self.images[key] = mtime
                            self.thumbnail_updated.emit(dir, name, "error")
                            continue

                        if not info['Cali']:
                            self.error_occurred.emit(f"{dir}/{name} 测量数据未做标定！")

                        if not (info["H_C"] and info["H_S"]):
                            with self._state_lock:
                                self.images[key] = mtime
                            self.thumbnail_updated.emit(dir, name, "error")
                            continue

                        try:
                            cs_image = self.merge_images(info["H_C"])
                            ss_image = self.merge_images(info["H_S"])
                        except Exception as e:
                            with self._state_lock:
                                self.images[key] = mtime
                            self.thumbnail_updated.emit(dir, name, "error")
                            self.error_occurred.emit(f"{dir}/{name} 创建缩略图时出错：{e}")
                            continue

                        # 落盘前在锁内再确认一次，避免与主线程改名交错产生孤儿缩略图
                        save_error = None
                        with self._state_lock:
                            if key in self._claimed:
                                continue
                            self.images[key] = mtime
                            try:
                                thumbnail_dir = os.path.join(self.thumbnail_path, dir)
                                os.makedirs(thumbnail_dir, exist_ok=True)
                                cs_image.save(os.path.join(thumbnail_dir, name+"_CS.png"), "PNG")
                                ss_image.save(os.path.join(thumbnail_dir, name+"_SS.png"), "PNG")
                            except Exception as e:
                                save_error = e

                        if save_error is not None:
                            self.thumbnail_updated.emit(dir, name, "error")
                            self.error_occurred.emit(f"{dir}/{name} 保存缩略图时出错：{save_error}")
                            continue

                        self.thumbnail_updated.emit(dir, name, "ok")
                        created_images_count += 1
                        break
            except Exception as e:
                pass

            if self.interval == 0: return
            if created_images_count==0:
                # 没有创建图片时才休眠
                for i in range(self.interval):
                    if self._stop: return
                    time.sleep(1)

    @Slot()
    def stop(self):
        """停止线程"""
        self._stop = True


    def get_images(self, folder_path):
        """
        获取指定文件夹下的所有TIF图片路径
        """
        images={
            "H_C":[],
            "H_S":[],
            "Cali":False    # 是否存在标定文件夹
        }

        if os.path.isdir(os.path.join(folder_path, "Cali")):
            images["Cali"]=True
        else:
            # 不存在Cali标定文件夹则等待3秒再判断
            time.sleep(3)
            if os.path.isdir(os.path.join(folder_path, "Cali")):
                images["Cali"]=True
        if os.path.isdir(os.path.join(folder_path, "H")):
            i=1
            AH=os.path.join(folder_path, "H","C1",f"AH{i}.tif")
            while os.path.isfile(AH):
                BH=os.path.join(folder_path, "H","C2",f"BH{i}.tif")
                CH=os.path.join(folder_path, "H","C3",f"CH{i}.tif")
                DH=os.path.join(folder_path, "H","C4",f"DH{i}.tif")
                images[f"H_C"].append(AH)
                if os.path.isfile(BH):
                    images[f"H_C"].append(BH)
                else:
                    return None
                if os.path.isfile(CH):
                    images[f"H_S"].append(CH)
                else:
                    return None
                if os.path.isfile(DH):
                    images[f"H_S"].append(DH)
                else:
                    return None
                
                i+=1
                AH=os.path.join(folder_path, "H","C1",f"AH{i}.tif")

        return images

    def merge_images(self, image_paths, overlay=65, top_ignore=520, scale=0.05, crop_threshold=0.8):
        if not image_paths:
            raise ValueError("图片列表不能为空")
        
        odd_top_crop = int(round(top_ignore * scale))
        even_top_crop = 0
        overlay_crop=int(round(overlay * scale))
        
        processed_images = []
        for idx, img_path in enumerate(image_paths):
            img = QImage(img_path)
            img_format = img.format()
            if img.isNull():
                raise ValueError(f"无法加载图片 {img_path}")
            
            # 缩放图片
            img = img.scaled(
                int(img.width() * scale), 
                int(img.height() * scale), 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )

            # 获取图片裁剪尺寸
            if idx == 0:
                crop_width = img.width() - overlay_crop * 2
                count=0
                while True:
                    if odd_top_crop > img.height()//2:
                        raise ValueError(f"图片 {img_path} 没有找到顶部裁切位置")
                    for i in range(crop_width):
                        if img.pixelColor(i+overlay_crop,odd_top_crop).red() > 10:
                            count+=1
                    if count/crop_width > crop_threshold:
                        break
                    odd_top_crop += 1
                    count = 0
            elif idx == 1:
                crop_width = img.width() - overlay_crop * 2
                count=0
                while True:
                    if even_top_crop > img.height()//2:
                        raise ValueError(f"图片 {img_path} 没有找到顶部裁切位置")
                    for i in range(crop_width):
                        if img.pixelColor(i+overlay_crop,even_top_crop).red() > 10:
                            count+=1
                    if count/crop_width > crop_threshold:
                        break
                    even_top_crop += 1
                    count = 0

            crop_width = img.width() - overlay_crop * 2
            crop_heigth = img.height() - odd_top_crop
            if idx % 2 == 0:
                img = img.copy(overlay_crop, odd_top_crop, crop_width, crop_heigth)
            else:
                img = img.copy(overlay_crop, even_top_crop, crop_width, crop_heigth)
            
            processed_images.append(img)

        # 获取处理后的图片尺寸
        proc_width = processed_images[0].width()
        proc_height = processed_images[0].height()
        total_width = proc_width * len(processed_images)
        
        # 拼接图片
        merged_image = QImage(total_width, proc_height,img_format)
        merged_image.fill(Qt.black)
        painter = QPainter(merged_image)
        current_x = 0
        for i, img in enumerate(processed_images):
            painter.drawImage(current_x, 0, img)
            current_x += proc_width
        painter.end()

        return merged_image


if __name__ == "__main__":
    ex = MonitorDir("E:/Images","E:/Thumbnails",interval=0)
    ex.start_monitor()
