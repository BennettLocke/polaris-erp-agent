"""
图片处理核心模块
黑框检测、裁切、OCR识别
基于 OpenCV + RapidOCR
"""
import os
import cv2
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# 可选依赖检查
try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_AVAILABLE = True
except ImportError:
    try:
        from rapidocr import RapidOCR
        RAPIDOCR_AVAILABLE = True
    except ImportError:
        RAPIDOCR_AVAILABLE = False


@dataclass
class Frame:
    """检测到的外框"""
    x: int
    y: int
    w: int
    h: int
    confidence: float = 1.0


class ImageProcessor:
    """
    图片处理器
    支持：黑框检测、裁切、OCR识别
    """

    def __init__(self):
        self.ocr_engine = None
        if RAPIDOCR_AVAILABLE:
            self.ocr_engine = RapidOCR()

    def detect_black_frames(self, image_path: str) -> list[Frame]:
        """
        检测黑色外框

        规则（order-flow）：
        - 黑色实线矩形外框包住设计稿
        - 1个外框 = 单订单，按框裁切1张
        - N个外框 = N个订单，按框逐一裁切
        - 无外框 = 单订单，整图上传不裁切

        Returns:
            Frame 列表
        """
        img = self._load_image(image_path)
        if img is None:
            return []

        # 转灰度
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 边缘检测
        edges = cv2.Canny(gray, 50, 150)

        # 膨胀连接边缘
        kernel = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # 轮廓检测
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        frames = []
        img_h, img_w = img.shape[:2]

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)

            # 过滤太小的框（小于图片5%）
            if w < img_w * 0.05 or h < img_h * 0.05:
                continue

            # 过滤太大的框（接近整图）
            if w > img_w * 0.95 and h > img_h * 0.95:
                continue

            # 计算置信度（基于框的完整性）
            area_ratio = (w * h) / (img_w * img_h)
            confidence = min(area_ratio * 5, 1.0)

            frames.append(Frame(x=x, y=y, w=w, h=h, confidence=confidence))

        # 按面积排序（从大到小）
        frames.sort(key=lambda f: f.w * f.h, reverse=True)

        # 无检测到外框 → 返回整图
        if not frames:
            frames.append(Frame(x=0, y=0, w=img_w, h=img_h, confidence=1.0))

        return frames

    def crop_frame(self, image_path: str, frame: Frame) -> Optional[np.ndarray]:
        """
        裁切图片

        Args:
            image_path: 图片路径
            frame: Frame 对象

        Returns:
            裁切后的图片数组
        """
        img = self._load_image(image_path)
        if img is None:
            return None

        x, y, w, h = frame.x, frame.y, frame.w, frame.h
        # 扩大一点边框，避免裁到内容
        margin = 5
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img.shape[1], x + w + margin)
        y2 = min(img.shape[0], y + h + margin)

        cropped = img[y1:y2, x1:x2]
        return cropped

    def ocr_recognize(self, image, top_ratio: float = 1.0) -> tuple[list, str]:
        """
        RapidOCR 识别

        Args:
            image: 图片数组（numpy.ndarray）
            top_ratio: 只识别顶部区域的比例，1.0 表示整图

        Returns:
            (results, full_text)
            results: [[bbox, text, score], ...]
            full_text: 拼接的所有文字
        """
        if self.ocr_engine is None:
            return [], "[OCR未安装]"

        try:
            if image is not None and 0 < top_ratio < 1:
                h = image.shape[0]
                crop_h = max(1, int(h * top_ratio))
                image = image[:crop_h, :]

            output = self.ocr_engine(image)
            if isinstance(output, tuple):
                results = output[0]
                if results is None:
                    return [], ""
                full_text = "\n".join([line[1] for line in results])
                return results, full_text

            txts = getattr(output, "txts", None)
            if txts is None:
                return [], ""

            boxes = getattr(output, "boxes", None)
            scores = getattr(output, "scores", None)
            boxes = boxes if boxes is not None else []
            scores = scores if scores is not None else []
            results = [
                [box, text, score]
                for box, text, score in zip(boxes, txts, scores)
            ]
            full_text = "\n".join([str(text) for text in txts])
            return results, full_text
        except Exception as e:
            return [], f"[OCR错误: {e}]"

    def _load_image(self, image_path: str) -> Optional[np.ndarray]:
        """加载图片"""
        if not os.path.exists(image_path):
            return None
        return cv2.imread(image_path)


def crop_and_save(image_path: str, frames: list[Frame], output_dir: str) -> list[str]:
    """
    裁切多张图片并保存

    Returns:
        裁切后的图片路径列表
    """
    processor = ImageProcessor()
    output_paths = []

    os.makedirs(output_dir, exist_ok=True)

    for i, frame in enumerate(frames):
        cropped = processor.crop_frame(image_path, frame)
        if cropped is not None:
            output_path = os.path.join(output_dir, f"crop_{i}.jpg")
            cv2.imwrite(output_path, cropped)
            output_paths.append(output_path)

    return output_paths
