"""Isolated, bounded GLB2 inspection and product-model OSS storage.

This checks structure and byte ranges, not decoder output or visual correctness.
No database, renderer, external-resource fetching, or OSS connection on import.
"""

import base64
import binascii
import hashlib
import json
import math
import re
import struct
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote_to_bytes

from scripts.oss_uploader import OSSUploader
from src.core.config import get_config

MAX_MODEL_BYTES = 50 * 1024 * 1024
MAX_DECODED_MODEL_BYTES = 256 * 1024 * 1024
# Matches three r186 GLTFLoader built-ins and the preview's MeshoptDecoder.
# Draco and BasisU/KTX2 need unconfigured loaders; third-party plugins are excluded.
SUPPORTED_REQUIRED_EXTENSIONS = frozenset({
    "KHR_lights_punctual",
    "KHR_materials_anisotropy",
    "KHR_materials_clearcoat",
    "KHR_materials_dispersion",
    "KHR_materials_emissive_strength",
    "KHR_materials_ior",
    "KHR_materials_iridescence",
    "KHR_materials_sheen",
    "KHR_materials_specular",
    "KHR_materials_transmission",
    "KHR_materials_unlit",
    "KHR_materials_volume",
    "KHR_mesh_quantization",
    "KHR_meshopt_compression",
    "KHR_texture_transform",
    "EXT_materials_bump",
    "EXT_meshopt_compression",
    "EXT_mesh_gpu_instancing",
    "EXT_texture_avif",
    "EXT_texture_webp",
})
_MESHOPT_EXTENSIONS = frozenset({"EXT_meshopt_compression", "KHR_meshopt_compression"})
_COMPONENTS = {5120: (1, "b"), 5121: (1, "B"), 5122: (2, "h"),
               5123: (2, "H"), 5125: (4, "I"), 5126: (4, "f")}
_TYPES = {"SCALAR": (1, 1), "VEC2": (2, 1), "VEC3": (3, 1), "VEC4": (4, 1),
          "MAT2": (2, 2), "MAT3": (3, 3), "MAT4": (4, 4)}
_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/avif"}


def _require(condition, message="模型数据结构或引用无效"):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=0):
    _require(type(value) is int and value >= minimum, "模型数据整数或范围无效")
    return value


def _object(value):
    _require(isinstance(value, dict))
    return value


def _array(doc, key):
    value = doc.get(key, [])
    _require(isinstance(value, list))
    for item in value:
        _object(item)
    return value


def _ref(items, index):
    _integer(index)
    _require(index < len(items), "模型数据索引越界")
    return items[index]


def _data_uri(uri, mimes):
    _require(isinstance(uri, str) and uri.startswith("data:"), "模型不允许引用外部文件")
    header, sep, payload = uri[5:].partition(",")
    parts = header.split(";")
    _require(sep and parts[0] in mimes and parts[1:] in ([], ["base64"]), "模型内嵌资源格式无效")
    _require(not re.search(r"%(?![0-9a-fA-F]{2})", payload), "模型内嵌资源编码无效")
    try:
        encoded = unquote_to_bytes(payload)
        data = base64.b64decode(encoded, validate=True) if len(parts) == 2 else encoded
    except (ValueError, binascii.Error):
        raise ValueError("模型内嵌资源编码无效") from None
    _require(bool(data), "模型内嵌资源为空")
    return data


def _json_pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "模型 JSON 包含重复字段")
        result[key] = value
    return result


def _scan_json(doc):
    # Also inspect extension payloads, so unsupported optional extensions cannot fetch files.
    pending = [(doc, 0)]
    while pending:
        item, depth = pending.pop()
        _require(depth <= 64, "模型 JSON 嵌套过深")
        if isinstance(item, dict):
            for key, value in item.items():
                if key.lower() in {"uri", "url"}:
                    _data_uri(value, _IMAGE_MIMES | {"application/octet-stream", "application/gltf-buffer"})
                pending.append((value, depth + 1))
        elif isinstance(item, list):
            pending.extend((value, depth + 1) for value in item)
        elif isinstance(item, float):
            _require(math.isfinite(item), "模型 JSON 数值无效")


def _parse_glb(data):
    _require(len(data) >= 20, "GLB 文件头不完整")
    magic, version, length = struct.unpack_from("<4sII", data)
    _require(magic == b"glTF" and version == 2, "仅支持 GLB 2.0 模型")
    _require(length == len(data), "GLB 文件长度不匹配")
    chunks = []
    offset = 12
    while offset < len(data):
        _require(offset + 8 <= len(data), "GLB 分块头不完整")
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        _require(size > 0 and size % 4 == 0 and size <= len(data) - offset, "GLB 分块长度无效")
        chunks.append((kind, data[offset:offset + size]))
        offset += size
    _require([kind for kind, _ in chunks] in ([0x4E4F534A], [0x4E4F534A, 0x004E4942]),
             "GLB 分块顺序或类型无效")
    try:
        doc = json.loads(chunks[0][1].decode("utf-8"), object_pairs_hook=_json_pairs,
                         parse_constant=lambda _: (_require(False, "模型 JSON 数值无效")))
    except (UnicodeError, ValueError, RecursionError):
        raise ValueError("模型 JSON 无效或嵌套过深") from None
    _object(doc)
    _scan_json(doc)
    asset = _object(doc.get("asset"))
    _require(asset.get("version") == "2.0" and asset.get("minVersion", "2.0") == "2.0",
             "仅支持 glTF 2.0 数据")
    return doc, chunks[1][1] if len(chunks) == 2 else None


def _extensions(doc):
    used = doc.get("extensionsUsed", [])
    required = doc.get("extensionsRequired", [])
    for names in (used, required):
        _require(isinstance(names, list) and all(isinstance(n, str) for n in names))
        _require(len(names) == len(set(names)))
    _require(set(required) <= set(used), "模型必需扩展未声明")
    _require(set(required) <= SUPPORTED_REQUIRED_EXTENSIONS, "模型包含不支持的必需扩展")


def _meshopt_name(item):
    extensions = _object(item.get("extensions", {}))
    names = _MESHOPT_EXTENSIONS.intersection(extensions)
    _require(len(names) <= 1, "模型不能在同一对象中混用两种 Meshopt 扩展")
    return next(iter(names), None)


def _buffers_and_views(doc, binary):
    buffers = _array(doc, "buffers")
    contents = []
    consumed_bin = False
    total_length = 0
    for index, buffer in enumerate(buffers):
        meshopt_name = _meshopt_name(buffer)
        length = _integer(buffer.get("byteLength"), 1)
        total_length += length
        _require(total_length <= MAX_MODEL_BYTES, "模型缓冲区过大")
        if "uri" in buffer:
            data = _data_uri(buffer["uri"], {"application/octet-stream", "application/gltf-buffer"})
            _require(len(data) == length, "模型内嵌缓冲区长度不匹配")
        else:
            fallback = _object(buffer["extensions"][meshopt_name]) if meshopt_name else {}
            if "fallback" in fallback:
                _require(type(fallback["fallback"]) is bool)
            # Meshopt's fallback tag is optional for URI-less placeholder buffers.
            if fallback.get("fallback") is True or index != 0 or binary is None:
                required = set(doc.get("extensionsRequired", []))
                _require(meshopt_name in required if meshopt_name else bool(required & _MESHOPT_EXTENSIONS),
                         "模型缺少内嵌二进制缓冲区")
                data = None
            else:
                _require(index == 0 and binary is not None, "模型缺少内嵌二进制缓冲区")
                _require(length <= len(binary) <= length + 3, "GLB 二进制缓冲区长度不匹配")
                _require(not any(binary[length:]), "GLB 二进制填充无效")
                data = binary[:length]
                consumed_bin = True
        contents.append(data)
    _require(binary is None or consumed_bin, "GLB 存在未引用的二进制分块")
    views = _array(doc, "bufferViews")
    decoded_bytes = 0
    for view in views:
        data = _ref(contents, view.get("buffer"))
        offset = _integer(view.get("byteOffset", 0))
        size = _integer(view.get("byteLength"), 1)
        _require(offset + size <= buffers[view["buffer"]]["byteLength"], "模型缓冲视图越界")
        if "byteStride" in view:
            stride = _integer(view["byteStride"], 4)
            _require(stride <= 252 and stride % 4 == 0, "模型缓冲视图步长无效")
        if "target" in view:
            _require(view["target"] in (34962, 34963))
        extensions = _object(view.get("extensions", {}))
        meshopt_name = _meshopt_name(view)
        _require(data is not None or meshopt_name in doc.get("extensionsRequired", []),
                 "模型占位缓冲区缺少压缩数据")
        if meshopt_name:
            _require(meshopt_name in doc.get("extensionsUsed", []))
            ext = _object(extensions[meshopt_name])
            source = _ref(contents, ext.get("buffer"))
            _require(source is not None, "Meshopt 压缩数据不能引用占位缓冲区")
            start = _integer(ext.get("byteOffset", 0))
            compressed = _integer(ext.get("byteLength"), 1)
            count = _integer(ext.get("count"), 1)
            stride = _integer(ext.get("byteStride"), 1)
            mode, filt = ext.get("mode"), ext.get("filter", "NONE")
            _require(start + compressed <= len(source), "Meshopt 压缩缓冲区越界")
            _require(size == count * stride and size <= MAX_MODEL_BYTES, "Meshopt 解压长度无效")
            # Overlapping views still allocate independent decoder output buffers.
            decoded_bytes += size
            _require(decoded_bytes <= MAX_DECODED_MODEL_BYTES, "模型压缩数据解码总量过大")
            _require(view.get("byteStride", stride) == stride)
            _require(mode in ("ATTRIBUTES", "TRIANGLES", "INDICES"))
            _require(filt in ("NONE", "OCTAHEDRAL", "QUATERNION", "EXPONENTIAL")
                     or (meshopt_name == "KHR_meshopt_compression" and filt == "COLOR"))
            if mode == "ATTRIBUTES":
                _require(stride % 4 == 0 and stride <= 256)
            else:
                _require(stride in (2, 4) and filt == "NONE")
                _require(mode != "TRIANGLES" or count % 3 == 0)
            _require(filt != "OCTAHEDRAL" or stride in (4, 8))
            _require(filt != "QUATERNION" or stride == 8)
            _require(filt != "EXPONENTIAL" or stride % 4 == 0)
            _require(filt != "COLOR" or stride in (4, 8))
    return contents, views


def _accessors(doc, contents, views):
    accessors = _array(doc, "accessors")
    total_size = 0
    for accessor in accessors:
        component = accessor.get("componentType")
        kind = accessor.get("type")
        _require(type(component) is int and component in _COMPONENTS)
        _require(isinstance(kind, str) and kind in _TYPES)
        unit = _COMPONENTS[component][0]
        rows, columns = _TYPES[kind]
        column_size = rows * unit
        element = ((column_size + 3) // 4 * 4 if columns > 1 else column_size) * columns
        count = _integer(accessor.get("count"), 1)
        total_size += count * element
        _require(total_size <= MAX_MODEL_BYTES, "模型访问器数据量过大")
        offset = _integer(accessor.get("byteOffset", 0))
        _require(offset % unit == 0, "模型访问器未对齐")
        if "bufferView" in accessor:
            view = _ref(views, accessor["bufferView"])
            stride = view.get("byteStride", element)
            _require(stride >= element and stride % unit == 0)
            _require((view.get("byteOffset", 0) + offset) % unit == 0)
            _require(offset + (count - 1) * stride + element <= view["byteLength"], "模型访问器越界")
        else:
            _require(offset == 0)
        if "normalized" in accessor:
            _require(type(accessor["normalized"]) is bool)
            _require(not accessor["normalized"] or component in (5120, 5121, 5122, 5123))
        for bound in ("min", "max"):
            if bound in accessor:
                values = accessor[bound]
                _require(isinstance(values, list) and len(values) == rows * columns)
                _require(all(type(v) in (int, float) and math.isfinite(v) for v in values))
        if "min" in accessor and "max" in accessor:
            _require(all(a <= b for a, b in zip(accessor["min"], accessor["max"])), "模型访问器边界无效")
        if "sparse" in accessor:
            sparse = _object(accessor["sparse"])
            amount = _integer(sparse.get("count"), 1)
            _require(amount <= count)
            indices = _object(sparse.get("indices"))
            index_type = indices.get("componentType")
            _require(type(index_type) is int and index_type in (5121, 5123, 5125))
            for entry, width in ((indices, _COMPONENTS[index_type][0]),
                                 (_object(sparse.get("values")), element)):
                view = _ref(views, entry.get("bufferView"))
                start = _integer(entry.get("byteOffset", 0))
                alignment = _COMPONENTS[index_type][0] if entry is indices else unit
                _require("byteStride" not in view and "target" not in view)
                _require(start % alignment == 0 and (view.get("byteOffset", 0) + start) % alignment == 0)
                _require(start + amount * width <= view["byteLength"], "模型稀疏访问器越界")
            view = views[indices["bufferView"]]
            if _meshopt_name(view) is None:
                data = contents[view["buffer"]]
                start = view.get("byteOffset", 0) + indices.get("byteOffset", 0)
                width, fmt = _COMPONENTS[index_type]
                previous = -1
                for position in range(start, start + amount * width, width):
                    index = struct.unpack_from("<" + fmt, data, position)[0]
                    _require(previous < index < count, "模型稀疏索引无效")
                    previous = index
    return accessors


def _scalar_values(entry, count, component, contents, views):
    view = views[entry["bufferView"]]
    if _meshopt_name(view) is not None:
        return None
    data = contents[view["buffer"]]
    unit, fmt = _COMPONENTS[component]
    start = view.get("byteOffset", 0) + entry.get("byteOffset", 0)
    stride = view.get("byteStride", unit)
    if stride == unit:
        values = struct.iter_unpack("<" + fmt, memoryview(data)[start:start + count * unit])
    else:
        values = (struct.unpack_from("<" + fmt, data, start + i * stride) for i in range(count))
    return (value[0] for value in values)


def _index_maximum(accessor, contents, views):
    """Merge sparse overrides while checking indices without a large allocation."""
    component, count = accessor["componentType"], accessor["count"]
    values = (_scalar_values(accessor, count, component, contents, views)
              if "bufferView" in accessor else (0 for _ in range(count)))
    if values is None:
        return 0  # Compressed value validation belongs to the renderer's decoder.
    if "sparse" not in accessor:
        return max(values)
    sparse = accessor["sparse"]
    indices = _scalar_values(sparse["indices"], sparse["count"],
                             sparse["indices"]["componentType"], contents, views)
    patches = _scalar_values(sparse["values"], sparse["count"], component, contents, views)
    if indices is None or patches is None:
        return 0
    override_index = next(indices, None)
    maximum = 0
    for index, value in enumerate(values):
        if index == override_index:
            value = next(patches)
            override_index = next(indices, None)
        maximum = max(maximum, value)
    return maximum


def _geometry_and_metadata(doc, contents, accessors, views):
    materials = _array(doc, "materials")
    result = []
    for index, material in enumerate(materials):
        name = material.get("name", "")
        _require(isinstance(name, str), "模型材质名称无效")
        result.append({"index": index, "name": name})
    meshes = _array(doc, "meshes")
    _require(bool(meshes), "模型中没有网格")
    index_maxima = {}
    for mesh in meshes:
        primitives = _array(mesh, "primitives")
        _require(bool(primitives), "模型网格为空")
        for primitive in primitives:
            attributes = _object(primitive.get("attributes"))
            _require("POSITION" in attributes, "模型缺少顶点位置")
            position = _ref(accessors, attributes["POSITION"])
            _require(position["type"] == "VEC3")
            for attribute in attributes.values():
                _require(_ref(accessors, attribute)["count"] == position["count"])
            mode = primitive.get("mode", 4)
            _require(type(mode) is int and 0 <= mode <= 6)
            if "indices" in primitive:
                indices = _ref(accessors, primitive["indices"])
                _require(indices["type"] == "SCALAR" and indices["componentType"] in (5121, 5123, 5125))
                _require(not indices.get("normalized", False))
                index_id = primitive["indices"]
                if index_id not in index_maxima:
                    index_maxima[index_id] = _index_maximum(indices, contents, views)
                _require(index_maxima[index_id] < position["count"], "模型顶点索引越界")
                _require(index_maxima[index_id] < (1 << (_COMPONENTS[indices["componentType"]][0] * 8)) - 1,
                         "模型顶点索引包含保留值")
            if "material" in primitive:
                _ref(materials, primitive["material"])
            for target in _array(primitive, "targets"):
                for attribute in target.values():
                    _require(_ref(accessors, attribute)["count"] == position["count"])
    for image in _array(doc, "images"):
        _require(("uri" in image) != ("bufferView" in image), "模型图片必须内嵌且仅有一个来源")
        if "uri" in image:
            _data_uri(image["uri"], _IMAGE_MIMES)
        else:
            _ref(views, image["bufferView"])
            _require(image.get("mimeType") in _IMAGE_MIMES, "模型图片类型无效")
    textures, samplers = _array(doc, "textures"), _array(doc, "samplers")
    images = doc.get("images", [])
    for texture in textures:
        if "source" in texture:
            _ref(images, texture["source"])
        if "sampler" in texture:
            _ref(samplers, texture["sampler"])
        extensions = _object(texture.get("extensions", {}))
        for name in ("EXT_texture_webp", "EXT_texture_avif"):
            if name in extensions:
                _ref(images, _object(extensions[name]).get("source"))
    pending = list(materials)
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            for key, value in item.items():
                if key.endswith("Texture"):
                    _ref(textures, _object(value).get("index"))
                pending.append(value)
        elif isinstance(item, list):
            pending.extend(item)
    nodes = _array(doc, "nodes")
    skins = _array(doc, "skins")
    for skin in skins:
        joints = skin.get("joints")
        _require(isinstance(joints, list) and bool(joints), "模型骨架关节为空或无效")
        for joint in joints:
            _ref(nodes, joint)
        _require(len(set(joints)) == len(joints), "模型骨架关节重复")
        if "skeleton" in skin:
            _ref(nodes, skin["skeleton"])
        if "inverseBindMatrices" in skin:
            matrices = _ref(accessors, skin["inverseBindMatrices"])
            _require(matrices["type"] == "MAT4" and matrices["componentType"] == 5126 and matrices["count"] >= len(joints), "模型骨架绑定矩阵无效")
    parents = [0] * len(nodes)
    for node in nodes:
        if "mesh" in node:
            _ref(meshes, node["mesh"])
        if "skin" in node:
            _ref(skins, node["skin"])
            _require("mesh" in node, "模型骨架缺少网格")
        children = node.get("children", [])
        _require(isinstance(children, list))
        for child in children:
            _ref(nodes, child)
            parents[child] += 1
            _require(parents[child] == 1, "模型节点存在重复父节点")
    roots = [index for index, count in enumerate(parents) if count == 0]
    visited = 0
    while roots:
        index = roots.pop()
        visited += 1
        roots.extend(nodes[index].get("children", []))
    _require(visited == len(nodes), "模型节点存在循环引用")
    for scene in _array(doc, "scenes"):
        _require(isinstance(scene.get("nodes", []), list))
        for node in scene.get("nodes", []):
            _ref(nodes, node)
    if "scene" in doc:
        _ref(doc.get("scenes", []), doc["scene"])
    animations = _array(doc, "animations")
    for animation in animations:
        samplers, channels = _array(animation, "samplers"), _array(animation, "channels")
        _require(bool(samplers) and bool(channels), "模型动画为空")
        for sampler in samplers:
            source = _ref(accessors, sampler.get("input"))
            _require(source["type"] == "SCALAR" and source["componentType"] == 5126)
            _ref(accessors, sampler.get("output"))
            _require(sampler.get("interpolation", "LINEAR") in ("LINEAR", "STEP", "CUBICSPLINE"))
        for channel in channels:
            _ref(samplers, channel.get("sampler"))
            target = _object(channel.get("target"))
            _ref(nodes, target.get("node"))
            _require(target.get("path") in ("translation", "rotation", "scale", "weights"))
    return len(animations), result


def validate_model_bytes(data: bytes, max_bytes: int = MAX_MODEL_BYTES) -> dict:
    """Return byte_size, sha256, animation_count and indexed material names."""
    _integer(max_bytes, 1)
    _require(isinstance(data, (bytes, bytearray, memoryview)), "模型必须为二进制数据")
    _require(0 < len(data) <= min(max_bytes, MAX_MODEL_BYTES), "模型为空或超过大小限制（最大 50MB）")
    data = bytes(data)
    try:
        doc, binary = _parse_glb(data)
        _extensions(doc)
        contents, views = _buffers_and_views(doc, binary)
        accessors = _accessors(doc, contents, views)
        animation_count, materials = _geometry_and_metadata(doc, contents, accessors, views)
    except (TypeError, KeyError, IndexError, OverflowError, RecursionError, struct.error):
        raise ValueError("模型数据结构或范围无效") from None
    return {"byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "animation_count": animation_count, "materials": materials}


def _read_model_file(path, max_bytes):
    _integer(max_bytes, 1)
    limit = min(max_bytes, MAX_MODEL_BYTES)
    try:
        with Path(path).open("rb") as handle:
            _require(handle.seek(0, 2) <= limit, "模型超过大小限制（最大 50MB）")
            handle.seek(0)
            data = handle.read(limit + 1)
    except (OSError, TypeError, ValueError):
        raise ValueError("无法读取模型文件") from None
    _require(len(data) <= limit, "模型超过大小限制（最大 50MB）")
    return data


def validate_model_file(path, max_bytes: int = MAX_MODEL_BYTES) -> dict:
    """Validate content only; never derive a public filename from a temp path."""
    return validate_model_bytes(_read_model_file(path, max_bytes), max_bytes=max_bytes)


def normalize_model_filename(original_filename: str) -> str:
    """Retain Unicode basename, removing paths, controls and unsafe filename characters."""
    _require(isinstance(original_filename, str), "模型文件名无效")
    name = unicodedata.normalize("NFC", original_filename.replace("\\", "/").rsplit("/", 1)[-1])
    name = "".join(c for c in name if not unicodedata.category(c).startswith("C") and c not in '<>:"|?*')
    name = name.strip().rstrip(". ")
    _require(name.lower().endswith(".glb") and bool(name[:-4].strip(". ")), "模型文件名必须以 .glb 结尾")
    stem = name[:-4]
    while len(stem.encode("utf-8")) > 240:
        stem = stem[:-1]
    return stem + ".glb"


def upload_model_file(path, original_filename: str) -> dict:
    """Upload the exact validated bytes; return only the OSS {url, path} result.

    Call normalize_model_filename separately for persisted display metadata.
    """
    normalize_model_filename(original_filename)
    data = _read_model_file(path, MAX_MODEL_BYTES)
    validate_model_bytes(data)
    key = f"product_models/{datetime.now():%Y%m%d}/{uuid.uuid4().hex}.glb"
    uploader = None
    try:
        uploader = OSSUploader(get_config().oss_config)
        result = uploader.upload_bytes(data, remote_path=key, content_type="model/gltf-binary")
        if not isinstance(result, dict) or result.get("error") or result.get("path") != key or not result.get("url"):
            raise ValueError("模型上传失败")
    except Exception:
        # A failed/unknown PUT response can still have stored the object remotely.
        # Only our generated key is eligible, never a path from the response.
        if uploader is not None:
            try:
                uploader.delete_product_model(key)
            except Exception:
                pass
        raise ValueError("模型上传失败，请稍后重试") from None
    return {"url": result["url"], "path": result["path"]}


def cleanup_model_object(path: str) -> bool:
    """Reject invalid keys before reading configuration or touching the network."""
    OSSUploader.validate_product_model_path(path)
    try:
        return OSSUploader(get_config().oss_config).delete_product_model(path)
    except Exception:
        return False
