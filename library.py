from PySide6.QtGui import QImage, QPainter
from PySide6.QtCore import Qt,QThread, Signal, Slot, QObject
import os
import time

class MonitorDir(QObject):
    # 定义线程间通信信号
    dir_updated = Signal(list)
    thumbnail_updated = Signal(str,str)
    dir_deleted = Signal(str)
    image_deleted = Signal(str)
    
    def __init__(self, monitor_path, thumbnail_path):
        super().__init__()
        self.monitor_path = monitor_path
        self.thumbnail_path = thumbnail_path
        self.dirs = []
        self.images = {}
        self._stop = False
        
    @Slot()
    def start_monitor(self):
        """线程主函数"""
        while not self._stop:
            # 扫描目录逻辑
            print(f"正在扫描目录 {self.monitor_path}...")
            current_dirs = []
            for entry in os.scandir(self.monitor_path):
                if entry.is_dir():
                    current_dirs.append(entry.name)
            current_dirs.sort()
            if current_dirs != self.dirs:
                print("目录已更新", current_dirs)
                self.dirs = current_dirs
                self.dir_updated.emit(current_dirs)
            time.sleep(1)  # 每1秒扫描一次目录

    
    @Slot()
    def stop(self):
        """停止线程"""
        print("正在停止线程...")
        self._stop = True



def merge_brbl_tif(image_paths, crop_left_right=60, crop_top_bottom=540, scale_percent=0.05):
    """
    水平拼接多张TIF图片，拼接前进行裁剪和缩放
    
    参数：
    image_paths: TIF图片路径列表（按拼接顺序）
    crop_left_right: 左右各裁剪的像素数（默认40）
    crop_top_bottom: 上下裁剪的像素数（默认500），奇数图片裁剪上方，偶数图片裁剪下方
    scale_percent: 缩放比例（默认0.05即5%）
    """
    if not image_paths:
        raise ValueError("图片列表不能为空")
    
    # 原始图片尺寸
    original_width = None
    original_height = None
    
    processed_images = []
    
    for idx, img_path in enumerate(image_paths):
        if not os.path.exists(img_path):
            raise ValueError(f"警告：图片文件不存在 {img_path}")
            
        # 使用QImage打开TIF图片
        img = QImage(img_path)
        original_height = original_height or img.height()
        original_width = original_width or img.width()
        if img.isNull():
            raise ValueError(f"无法加载图片 {img_path}")
        if original_height != img.height():
            raise ValueError(f"图片 {os.path.basename(img_path)} 尺寸与其它图片不一致！")
        elif original_width != img.width():
            raise ValueError(f"图片 {os.path.basename(img_path)} 尺寸与其它图片不一致！")
        
        # 上下裁剪处理
        if idx % 2 == 0:
            # 裁剪上方crop_top_bottom像素
            top = crop_top_bottom
            bottom = original_height
        else:  # 偶数序号
            top = 0
            bottom = original_height - crop_top_bottom
        
        left = crop_left_right
        right = original_width - crop_left_right
        crop_width = right - left
        crop_height = bottom - top
        img = img.copy(left, top, crop_width, crop_height)
        if img.isNull():
            raise ValueError(f"裁剪图片 {os.path.basename(img_path)} 失败")
        
        # 缩小图片（使用高质量的抗锯齿滤波）
        new_width = int(crop_width * scale_percent)
        new_height = int(crop_height * scale_percent)
        img = img.scaled(
            new_width, 
            new_height, 
            Qt.IgnoreAspectRatio, 
            Qt.SmoothTransformation
        )
        if img.isNull():
            raise ValueError(f"缩放图片 {os.path.basename(img_path)} 失败")
            
        processed_images.append(img)

    
    # 获取处理后的图片尺寸
    proc_width = processed_images[0].width()
    proc_height = processed_images[0].height()
    
    # 验证所有处理后的图片尺寸是否相同
    for i, img in enumerate(processed_images[1:], 1):
        if img.width() != proc_width or img.height() != proc_height:
            print(f"警告：图片 {i+1} 处理后的尺寸 {img.width()}x{img.height()} 与第一张图片尺寸 ({proc_width}, {proc_height}) 不同")
            # 统一调整尺寸
            img = img.scaled(proc_width, proc_height, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            processed_images[i] = img
    
    # 计算总宽度
    n_images = len(processed_images)
    total_width = proc_width * n_images
    
    # 创建新图像（根据第一张图片的模式）
    first_img = processed_images[0]
    
    # 判断并创建适当格式的图像
    if first_img.format() == QImage.Format_Grayscale8:
        merged_image = QImage(total_width, proc_height, QImage.Format_Grayscale8)
    elif first_img.format() == QImage.Format_Grayscale16:
        merged_image = QImage(total_width, proc_height, QImage.Format_Grayscale16)
    elif first_img.format() == QImage.Format_RGB32:
        merged_image = QImage(total_width, proc_height, QImage.Format_RGB32)
    elif first_img.format() == QImage.Format_ARGB32:
        merged_image = QImage(total_width, proc_height, QImage.Format_ARGB32)
    elif first_img.format() == QImage.Format_RGBA8888:
        merged_image = QImage(total_width, proc_height, QImage.Format_RGBA8888)
    else:
        # 默认格式，大多数情况下TIF是灰度图
        merged_image = QImage(total_width, proc_height, QImage.Format_Grayscale8)
    
    # 填充背景色为黑色
    merged_image.fill(Qt.black)
    
    # 使用QPainter依次粘贴每张图片
    painter = QPainter(merged_image)
    current_x = 0
    for i, img in enumerate(processed_images):
        painter.drawImage(current_x, 0, img)
        current_x += proc_width
    painter.end()

    return merged_image


def get_images(folder_path):
    """
    获取指定文件夹下的所有TIF图片路径
    """
    images={
        "H_C":[],
        "H_S":[],
        "L_C":[],
        "L_S":[],
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
            AL=os.path.join(folder_path, "L","C1",f"AL{i}.tif")
            BL=os.path.join(folder_path, "L","C2",f"BL{i}.tif")
            CL=os.path.join(folder_path, "L","C3",f"CL{i}.tif")
            DL=os.path.join(folder_path, "L","C4",f"DL{i}.tif")
            images[f"H_C"].append(AH)
            if os.path.isfile(BH):
                images[f"H_C"].append(BH)
            else:
                raise ValueError(f"图片文件不存在 {BH}")
            if os.path.isfile(CH):
                images[f"H_S"].append(CH)
            else:
                raise ValueError(f"图片文件不存在 {CH}")
            if os.path.isfile(DH):
                images[f"H_S"].append(DH)
            else:
                raise ValueError(f"图片文件不存在 {DH}")
            
            if os.path.isfile(AL):
                images[f"L_C"].append(AL)
            else:
                raise ValueError(f"图片文件不存在 {AL}")
            if os.path.isfile(BL):
                images[f"L_C"].append(BL)
            else:
                raise ValueError(f"图片文件不存在 {BL}")
            if os.path.isfile(CL):
                images[f"L_S"].append(CL)
            else:
                raise ValueError(f"图片文件不存在 {CL}")
            if os.path.isfile(DL):
                images[f"L_S"].append(DL)
            else:
                raise ValueError(f"图片文件不存在 {DL}")
            
            i+=1
            AH=os.path.join(folder_path, "H","C1",f"AH{i}.tif")

    return images
            



# 使用示例
if __name__ == "__main__":
    # 图片列表
    images = get_images("PCBImages\\Q24115670A1_000014847971\\Q24115670A1_000014847971_20251212024619_1484797143_3.9mm_NG")

    # 使用基础版本
    result = merge_brbl_tif(
        image_paths=images["H_C"],
        crop_left_right=60,
        crop_top_bottom=540,
        scale_percent=0.05
    )
    
    if result:
        print("图片拼接完成！")
    
    result.save("C3C4.png","PNG") # type: ignore
