"""Validate archive resource bounds before any bag image is extracted."""

from pathlib import PurePosixPath
from zipfile import ZipFile


MAX_BAG_PNG_FILES = 100
MAX_BAG_ARCHIVE_ENTRIES = 1000
MAX_BAG_MEMBER_BYTES = 64 * 1024 * 1024
MAX_BAG_UNPACKED_BYTES = 512 * 1024 * 1024


def validate_bag_archive(archive: ZipFile) -> None:
    entries = archive.infolist()
    if len(entries) > MAX_BAG_ARCHIVE_ENTRIES:
        raise ValueError("压缩包内文件和目录过多，最多允许 1000 项，请拆分后上传")
    pngs = [entry for entry in entries if not entry.is_dir()
            and PurePosixPath(entry.filename.replace("\\", "/")).suffix.lower() == ".png"]
    if len(pngs) > MAX_BAG_PNG_FILES:
        raise ValueError("每个压缩包最多允许 100 张 PNG，请拆分后上传")
    if sum(entry.file_size for entry in entries) > MAX_BAG_UNPACKED_BYTES:
        raise ValueError("压缩包解压后总大小不能超过 512MB，请拆分后上传")
    for entry in pngs:
        if entry.flag_bits & 1:
            raise ValueError("不支持加密压缩包，请取消密码后重新上传")
        if entry.file_size > MAX_BAG_MEMBER_BYTES:
            raise ValueError("压缩包内单张 PNG 不能超过 64MB，请缩小图片后上传")
