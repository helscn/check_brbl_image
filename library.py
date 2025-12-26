from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt, Signal, Slot, QObject
from threading import Lock
import os
import time
import re

class MonitorDir(QObject):
    # 定义线程间通信信号
    dir_updated = Signal(list)
    thumbnail_updated = Signal(str, str, str)      # dir, name, status(ok,error,delete)
    error_occurred = Signal(str)
    
    def __init__(self, monitor_path, thumbnail_path, interval=5):
        super().__init__()
        self.monitor_path = monitor_path
        self.thumbnail_path = thumbnail_path
        self.dirs = []
        self.images = {}
        self.interval = interval
        self.lock = Lock()
        self._stop = False
        
    @Slot()
    def start_monitor(self):
        """线程主函数"""
        folder_regex = re.compile(r"^([A-Z0-9\-]+)_(\d+)_(\d{14})_(\d*)_.*$",re.IGNORECASE)
        self.dirs = []
        for entry in os.scandir(self.monitor_path):
            if entry.is_dir():
                self.dirs.append(entry.name)
        self.dirs.sort()
        self.dir_updated.emit(self.dirs)

        for dir in self.dirs:
            for entry in os.scandir(os.path.join(self.monitor_path, dir)):
                if entry.is_dir():
                    name = entry.name
                    match = folder_regex.match(name)
                    if match:
                        self.thumbnail_updated.emit(dir, name, "new")

        while not self._stop:
            # 判断监控文件夹是否有新型号
            current_dirs = []
            for entry in os.scandir(self.monitor_path):
                if entry.is_dir():
                    current_dirs.append(entry.name)
            current_dirs.sort()
            if current_dirs != self.dirs:
                self.dirs = current_dirs
                self.dir_updated.emit(current_dirs)

            # 删除不存在的图片文件夹数据
            with self.lock:
                to_be_deleted = []
                for dir,name in self.images.keys():
                    if self._stop: return
                    if not os.path.isdir(os.path.join(self.monitor_path, dir, name)):
                        to_be_deleted.append((dir, name))
                for dir, name in to_be_deleted:
                    del self.images[(dir, name)]
                    self.thumbnail_updated.emit(dir, name, "delete")
                    
            # 创建图片文件
            for dir in self.dirs:
                for entry in os.scandir(os.path.join(self.monitor_path, dir)):
                    if self._stop: return
                    if entry.is_dir():
                        name = entry.name
                        match = folder_regex.match(name)
                        if match:
                            mtime = entry.stat().st_mtime
                            if ((dir, name) not in self.images) or ((dir, name) in self.images and mtime>self.images[(dir,name)]):
                                info = self.get_images(entry.path)
                                self.images[(dir, name)] = mtime
                                if info is None:
                                    self.thumbnail_updated.emit(dir, name, "error")
                                else:
                                    try:
                                        if not info['Cali']:
                                            self.error_occurred.emit(f"{dir}/{name} 测量数据未做标定！")
                                        if len(info["H_C"])>0 and len(info["H_S"])>0:
                                            if not os.path.isdir(os.path.join(self.thumbnail_path, dir)):
                                                os.mkdir(os.path.join(self.thumbnail_path, dir))
                                            if self._stop: return
                                            cs_image = self.merge_images(info["H_C"])
                                            cs_image.save(os.path.join(self.thumbnail_path, dir, name+"_CS.png"),"PNG")
                                            if self._stop: return
                                            ss_image = self.merge_images(info["H_S"])
                                            ss_image.save(os.path.join(self.thumbnail_path, dir, name+"_SS.png"),"PNG")
                                            self.thumbnail_updated.emit(dir, name, "ok")
                                        else:
                                            self.thumbnail_updated.emit(dir, name, "error")
                                    except Exception as e:
                                        self.thumbnail_updated.emit(dir, name, "error")
                                        self.error_occurred.emit(f"{dir}/{name} 创建缩略图时出错：{e}")

            if self.interval == 0: return
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