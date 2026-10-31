import base64
import copy
import hashlib
import importlib
import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def service():
    return importlib.import_module("src.services.business.product_models")


def document():
    return {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": 36}],
        "bufferViews": [{"buffer": 0, "byteLength": 36}],
        "accessors": [{"bufferView": 0, "componentType": 5126,
                       "count": 3, "type": "VEC3"}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
    }


def chunk(kind, payload):
    return struct.pack("<II", len(payload), kind) + payload


def glb(doc=None, binary=b"\0" * 36, json_bytes=None):
    payload = json_bytes if json_bytes is not None else json.dumps(
        document() if doc is None else doc, ensure_ascii=False).encode()
    payload += b" " * (-len(payload) % 4)
    body = chunk(0x4E4F534A, payload)
    if binary is not None:
        body += chunk(0x004E4942, binary + b"\0" * (-len(binary) % 4))
    return struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body


def reject(data):
    with pytest.raises(ValueError, match=r"[\u4e00-\u9fff]"):
        service().validate_model_bytes(data)


def test_metadata_and_file_are_independent_of_temp_name(tmp_path):
    doc = document()
    doc["materials"] = [{"name": "茶盒"}, {}]
    data = glb(doc)
    path = tmp_path / "temporary.upload"
    path.write_bytes(data)
    expected = {"byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "animation_count": 0,
                "materials": [{"index": 0, "name": "茶盒"}, {"index": 1, "name": ""}]}
    assert service().validate_model_file(path) == expected
    assert service().validate_model_bytes(data) == expected


def test_meshopt_overlapping_views_cannot_exceed_aggregate_decode_budget():
    doc = document()
    size = 48 * 1024 * 1024
    doc.update(extensionsUsed=['EXT_meshopt_compression'], extensionsRequired=['EXT_meshopt_compression'])
    doc['buffers'].append({'byteLength': size, 'extensions': {'EXT_meshopt_compression': {'fallback': True}}})
    for index in range(32):
        doc['bufferViews'].append({'buffer': 1, 'byteLength': size, 'byteStride': 12,
            'extensions': {'EXT_meshopt_compression': {'buffer': 0, 'byteLength': 36,
                'count': size // 12, 'byteStride': 12, 'mode': 'ATTRIBUTES'}}})
        doc['accessors'].append({'bufferView': index + 1, 'componentType': 5126, 'count': 3, 'type': 'VEC3'})
        doc['meshes'][0]['primitives'].append({'attributes': {'POSITION': index + 1}})
    reject(glb(doc))


@pytest.mark.parametrize('skin', [None, {'joints': [999]}, {'joints': []}, {'joints': [0], 'inverseBindMatrices': 999}, {'joints': [0], 'inverseBindMatrices': 0}])
def test_invalid_skin_references_are_rejected(skin):
    doc = document()
    doc['nodes'][0]['skin'] = 0 if skin is not None else 999
    if skin is not None:
        doc['skins'] = [skin]
    reject(glb(doc))


@pytest.mark.parametrize("data", [b"", b"glTF", b"bad!" + glb()[4:],
    glb()[:4] + struct.pack("<I", 1) + glb()[8:],
    glb()[:8] + struct.pack("<I", 12) + glb()[12:], glb()[:-1],
    glb(json_bytes=b"{broken"), glb(json_bytes=b"[]"),
    glb(json_bytes=b'{"asset":{"version":"2.0"},"x":NaN}'),
    glb(json_bytes=b'{"asset":{},"asset":{"version":"2.0"}}'),
    glb() + b"tail"])
def test_bad_containers(data):
    reject(data)


def test_bad_chunk_order_length_duplicates_and_padding():
    good = glb()
    body = good[12:]
    for badbody in [chunk(0x004E4942, b"\0" * 4) + body,
                    body + chunk(0x4E4F534A, b"{}  "),
                    body + chunk(0x004E4942, b"\0" * 4),
                    body + chunk(123, b"\0" * 4),
                    struct.pack("<II", 0xFFFFFFFC, 0x4E4F534A) + body[8:],
                    chunk(0x4E4F534A, b"{} ")]:
        reject(struct.pack("<4sII", b"glTF", 2, 12 + len(badbody)) + badbody)
    reject(glb(binary=b"\0" * 35 + b"x" + b"\0" * 4))


@pytest.mark.parametrize("uri", ["texture.png", "../secret", "https://host/x",
    "file:///etc/passwd", "//host/file", "DATA:image/png;base64,AAAA",
    "data:image/png;base64,!!!!", "data:image/png;base64,", "data:image/svg+xml,%3Csvg/%3E"])
def test_external_or_invalid_images(uri):
    doc = document()
    doc["images"] = [{"uri": uri}]
    reject(glb(doc))


def test_embedded_images_and_data_buffers():
    doc = document()
    doc["images"] = [{"bufferView": 0, "mimeType": "image/png"},
                     {"uri": "data:image/png;base64,iVBORw0KGgo="}]
    assert service().validate_model_bytes(glb(doc))["byte_size"] > 0
    doc["buffers"][0]["uri"] = "data:application/octet-stream;base64," + base64.b64encode(b"\0" * 36).decode()
    assert service().validate_model_bytes(glb(doc, binary=None))["animation_count"] == 0
    doc["buffers"][0]["uri"] = "data:application/gltf-buffer," + "%00" * 36
    service().validate_model_bytes(glb(doc, binary=None))


@pytest.mark.parametrize("change", [
    lambda d: d.update(meshes=[]),
    lambda d: d["meshes"][0].update(primitives=[]),
    lambda d: d["meshes"][0]["primitives"][0].update(attributes={}),
    lambda d: d["meshes"][0]["primitives"][0]["attributes"].update(POSITION=99),
    lambda d: d["meshes"][0]["primitives"][0].update(material=0),
    lambda d: d["buffers"][0].update(uri="mesh.bin"),
    lambda d: d["buffers"][0].update(byteLength=40),
    lambda d: d["bufferViews"][0].update(byteLength=37),
    lambda d: d["bufferViews"][0].update(buffer=True),
    lambda d: d["bufferViews"][0].update(byteOffset=-1),
    lambda d: d["bufferViews"][0].update(byteStride=3),
    lambda d: d["accessors"][0].update(count=4),
    lambda d: d["accessors"][0].update(count=0),
    lambda d: d["accessors"][0].update(byteOffset=1),
    lambda d: d["accessors"][0].update(componentType=999),
    lambda d: d["accessors"][0].update(type="NOPE"),
    lambda d: d.update(images=[{"bufferView": 99, "mimeType": "image/png"}]),
    lambda d: d.update(images=[{"bufferView": 0}]),
    lambda d: d.update(images=[{"uri": "data:image/png;base64,AAAA", "bufferView": 0}]),
    lambda d: d.update(animations=[{}]),
    lambda d: d.update(materials=[{"name": 5}]),
    lambda d: d.update(extras={"uri": "https://host/file"}),
])
def test_invalid_document_ranges_and_references(change):
    doc = document()
    change(doc)
    reject(glb(doc))


@pytest.mark.parametrize("ext", ["KHR_draco_mesh_compression", "KHR_texture_basisu", "UNKNOWN_decoder"])
def test_unsupported_required_extensions(ext):
    doc = document()
    doc.update(extensionsUsed=[ext], extensionsRequired=[ext])
    reject(glb(doc))


@pytest.mark.parametrize("extension", ["EXT_meshopt_compression", "KHR_meshopt_compression"])
def test_meshopt_required_and_range_validation(extension):
    doc = document()
    doc.update(extensionsUsed=[extension], extensionsRequired=[extension])
    doc["bufferViews"][0]["extensions"] = {extension: {
        "buffer": 0, "byteOffset": 0, "byteLength": 12, "byteStride": 12,
        "count": 3, "mode": "ATTRIBUTES"}}
    service().validate_model_bytes(glb(doc))
    doc["bufferViews"][0]["extensions"][extension]["byteLength"] = 100
    reject(glb(doc))


def test_animation_count():
    doc = document()
    doc["accessors"].append({"bufferView": 0, "componentType": 5126, "count": 3, "type": "SCALAR"})
    doc["animations"] = [{"samplers": [{"input": 1, "output": 0}],
                           "channels": [{"sampler": 0, "target": {"node": 0, "path": "translation"}}]}]
    assert service().validate_model_bytes(glb(doc))["animation_count"] == 1


def test_sparse_accessor_bounds_and_indices():
    doc = document()
    doc["accessors"][0].pop("bufferView")
    doc["accessors"][0]["sparse"] = {"count": 1, "indices": {"bufferView": 0, "componentType": 5121},
                                     "values": {"bufferView": 0}}
    service().validate_model_bytes(glb(doc))
    reject(glb(doc, binary=b"\xff" + b"\0" * 35))
    doc["accessors"][0]["sparse"]["values"]["byteOffset"] = 36
    reject(glb(doc))


def test_size_limits_and_read_errors(tmp_path):
    data = glb()
    with pytest.raises(ValueError):
        service().validate_model_bytes(data, max_bytes=len(data) - 1)
    service().validate_model_bytes(data, max_bytes=len(data))
    path = tmp_path / "big.glb"
    with path.open("wb") as handle:
        handle.truncate(50 * 1024 * 1024 + 1)
    with pytest.raises(ValueError):
        service().validate_model_file(path)
    with pytest.raises(ValueError):
        service().validate_model_file(tmp_path / "missing")


@pytest.fixture
def uploader(monkeypatch):
    module = importlib.import_module("scripts.oss_uploader")
    monkeypatch.setattr(module, "oss2", Mock())
    obj = module.OSSUploader({"domain": "https://cdn.example", "upload_path": "order/{date}/{uniqid}.jpg"})
    obj._bucket = Mock()
    obj._bucket.put_object_from_file.return_value.status = 200
    obj._bucket.put_object.return_value.status = 200
    obj._bucket.delete_object.return_value.status = 204
    return obj


KEY = "product_models/20261030/0123456789abcdef0123456789abcdef.glb"


def test_uploader_legacy_and_optional_arguments(uploader, tmp_path):
    path = tmp_path / "image.jpg"
    path.write_bytes(b"image")
    assert uploader.upload(str(path))["path"].startswith("order/")
    assert uploader._bucket.put_object_from_file.call_args.kwargs == {}
    assert uploader.upload(str(path), remote_path=KEY, content_type="model/gltf-binary")["path"] == KEY
    assert uploader._bucket.put_object_from_file.call_args.kwargs == {"headers": {"Content-Type": "model/gltf-binary"}}
    uploader.upload_bytes(b"abc", KEY)
    assert uploader._bucket.put_object.call_args.kwargs == {}
    uploader.upload_bytes(b"abc", KEY, content_type="model/gltf-binary")
    assert uploader._bucket.put_object.call_args.kwargs["headers"]["Content-Type"] == "model/gltf-binary"


@pytest.mark.parametrize("key", ["order/x.jpg", "/" + KEY, "https://cdn.example/" + KEY,
    KEY + "?x", KEY.replace("20261030", "20260230"), KEY.replace("product_models/", "product_models/../"),
    KEY.replace(".glb", ".GLB"), KEY.replace("/0123", "/%30123"), KEY + "\n", None])
def test_delete_refuses_everything_outside_exact_keys(uploader, key):
    with pytest.raises(ValueError):
        uploader.delete_product_model(key)
    uploader._bucket.delete_object.assert_not_called()


def test_delete_success_and_failure(uploader):
    assert uploader.delete_product_model(KEY) is True
    uploader._bucket.delete_object.assert_called_once_with(KEY)
    uploader._bucket.delete_object.return_value.status = 500
    assert uploader.delete_product_model(KEY) is False
    uploader._bucket.delete_object.side_effect = RuntimeError("secret")
    assert uploader.delete_product_model(KEY) is False


def test_storage_helpers_validate_and_normalize(uploader, monkeypatch, tmp_path):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    constructor = Mock(return_value=uploader)
    constructor.validate_product_model_path = uploader.validate_product_model_path
    monkeypatch.setattr(model, "OSSUploader", constructor)
    path = tmp_path / "upload.tmp"
    path.write_bytes(glb())
    assert model.normalize_model_filename("C:\\fakepath\\茶盒\x00\n.GLB") == "茶盒.glb"
    result = model.upload_model_file(path, "../茶盒.glb")
    import re
    assert re.fullmatch(r"product_models/\d{8}/[0-9a-f]{32}\.glb", result["path"])
    assert result["url"] == "https://cdn.example/" + result["path"]
    assert model.cleanup_model_object(result["path"]) is True
    path.write_bytes(b"bad")
    uploader._bucket.put_object.reset_mock()
    with pytest.raises(ValueError):
        model.upload_model_file(path, "bad.glb")
    uploader._bucket.put_object.assert_not_called()


def test_upload_failure_is_sanitized(uploader, monkeypatch, tmp_path):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    path = tmp_path / "file"
    path.write_bytes(glb())
    uploader._bucket.put_object.side_effect = RuntimeError("secret credential")
    with pytest.raises(ValueError, match="上传") as caught:
        model.upload_model_file(path, "x.glb")
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("name", ["", "x.obj", ".glb", "..", "x.glb\u202eexe"])
def test_bad_original_names(name):
    with pytest.raises(ValueError):
        service().normalize_model_filename(name)


@pytest.mark.parametrize("extension", ["EXT_meshopt_compression", "KHR_meshopt_compression"])
@pytest.mark.parametrize("tagged", [True, False])
def test_meshopt_placeholder_buffer(extension, tagged):
    doc = document()
    doc.update(extensionsUsed=[extension], extensionsRequired=[extension])
    placeholder = {"byteLength": 36}
    if tagged:
        placeholder["extensions"] = {extension: {"fallback": True}}
    doc["buffers"].append(placeholder)
    doc["bufferViews"][0].update(buffer=1, extensions={extension: {
        "buffer": 0, "byteLength": 12, "byteStride": 12, "count": 3, "mode": "ATTRIBUTES"}})
    service().validate_model_bytes(glb(doc))
    invalid = copy.deepcopy(doc)
    invalid["bufferViews"][0]["extensions"][extension]["buffer"] = 1
    reject(glb(invalid))


def test_vertex_indices_are_within_position_count():
    doc = document()
    doc["accessors"].append({"bufferView": 0, "componentType": 5121, "count": 3, "type": "SCALAR"})
    doc["meshes"][0]["primitives"][0]["indices"] = 1
    service().validate_model_bytes(glb(doc, binary=b"\0\1\2" + b"\0" * 33))
    reject(glb(doc, binary=b"\0\1\3" + b"\0" * 33))


@pytest.mark.parametrize("nodes", [[{"mesh": 0, "children": [0]}],
    [{"mesh": 0, "children": [1]}, {"children": [0]}],
    [{"mesh": 0, "children": [2]}, {"children": [2]}, {}],
    [{"mesh": 0, "children": [1, 1]}, {}]])
def test_node_cycles_and_multiple_parents(nodes):
    doc = document()
    doc["nodes"] = nodes
    reject(glb(doc))


@pytest.mark.parametrize("change", [
    lambda d: d.update(textures=[{"source": 99}]),
    lambda d: d.update(textures=[{"sampler": 99}]),
    lambda d: d.update(materials=[{"normalTexture": {"index": 99}}]),
    lambda d: d["accessors"][0].update(min=[0, 0, 0], max=[-1, 0, 0]),
    lambda d: d["bufferViews"][0].update(byteStride=4),
    lambda d: d["buffers"][0].update(byteLength=True),
    lambda d: d.update(extensionsRequired=["EXT_meshopt_compression"]),
])
def test_additional_corruption(change):
    doc = document()
    change(doc)
    reject(glb(doc))


def test_cleanup_rejects_before_config(monkeypatch):
    model = service()
    config = Mock(side_effect=AssertionError("configuration must not be read"))
    monkeypatch.setattr(model, "get_config", config)
    with pytest.raises(ValueError):
        model.cleanup_model_object("order/image.jpg")
    config.assert_not_called()


def test_uploaded_bytes_match_validated_content(uploader, monkeypatch, tmp_path):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    path = tmp_path / "source"
    data = glb()
    path.write_bytes(data)
    result = model.upload_model_file(path, "展示.glb")
    uploader._bucket.put_object.assert_called_once_with(
        result["path"], data, headers={"Content-Type": "model/gltf-binary"})


def test_path_and_parser_errors_are_chinese_value_errors():
    reject(glb(json_bytes=b'{"number":' + b"1" * 5000 + b"}"))


def test_invalid_path_error_is_chinese():
    with pytest.raises(ValueError, match=r"[\u4e00-\u9fff]"):
        service().validate_model_file("bad\0path")


def test_sparse_indices_override_base_values():
    doc = document()
    binary = b"\0\1\2\xff\x01\x01" + b"\0" * 30
    doc["bufferViews"].extend([
        {"buffer": 0, "byteOffset": 3, "byteLength": 3},
        {"buffer": 0, "byteOffset": 0, "byteLength": 1},
        {"buffer": 0, "byteOffset": 0, "byteLength": 1},
    ])
    doc["accessors"].append({"bufferView": 1, "componentType": 5121, "count": 3, "type": "SCALAR",
        "sparse": {"count": 1, "indices": {"bufferView": 2, "componentType": 5121},
                   "values": {"bufferView": 3}}})
    doc["meshes"][0]["primitives"][0]["indices"] = 1
    service().validate_model_bytes(glb(doc, binary=binary))


@pytest.mark.parametrize("status", [400, 500])
def test_storage_rejects_upload_http_failure(uploader, monkeypatch, tmp_path, status):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    uploader._bucket.put_object.return_value.status = status
    path = tmp_path / "source"
    path.write_bytes(glb())
    with pytest.raises(ValueError, match="上传"):
        model.upload_model_file(path, "file.glb")


def test_cleanup_configuration_failure_is_false(monkeypatch):
    model = service()
    monkeypatch.setattr(model, "get_config", Mock(side_effect=RuntimeError("secret")))
    assert model.cleanup_model_object(KEY) is False


# Audited against installed three r186 GLTFLoader registrations and parse switch.
BUILTIN_REQUIRED_EXTENSIONS = [
    "KHR_lights_punctual", "KHR_materials_anisotropy", "KHR_materials_clearcoat",
    "KHR_materials_dispersion", "KHR_materials_emissive_strength", "KHR_materials_ior",
    "KHR_materials_iridescence", "KHR_materials_sheen", "KHR_materials_specular",
    "KHR_materials_transmission", "KHR_materials_unlit", "KHR_materials_volume",
    "KHR_mesh_quantization", "KHR_meshopt_compression", "KHR_texture_transform",
    "EXT_materials_bump", "EXT_meshopt_compression", "EXT_mesh_gpu_instancing",
    "EXT_texture_avif", "EXT_texture_webp",
]


@pytest.mark.parametrize("extension", BUILTIN_REQUIRED_EXTENSIONS)
def test_loader_builtin_required_extensions_accepted(extension):
    doc = document()
    doc.update(extensionsUsed=[extension], extensionsRequired=[extension])
    if "materials_" in extension:
        doc["materials"] = [{"name": "finish", "extensions": {extension: {}}}]
        doc["meshes"][0]["primitives"][0]["material"] = 0
    assert service().validate_model_bytes(glb(doc))["byte_size"] > 0


def test_required_materials_combination_and_unknown_extension():
    doc = document()
    extensions = {"KHR_materials_clearcoat": {"clearcoatFactor": 1},
                  "KHR_materials_ior": {"ior": 1.5},
                  "KHR_materials_specular": {"specularFactor": 0.8}}
    doc.update(extensionsUsed=list(extensions), extensionsRequired=list(extensions))
    doc["materials"] = [{"name": "finish", "extensions": extensions}]
    assert service().validate_model_bytes(glb(doc))["materials"] == [{"index": 0, "name": "finish"}]
    doc["extensionsUsed"].append("KHR_future_decoder")
    doc["extensionsRequired"].append("KHR_future_decoder")
    reject(glb(doc))


@pytest.mark.parametrize("extension,mime", [("EXT_texture_webp", "image/webp"),
                                          ("EXT_texture_avif", "image/avif")])
def test_required_embedded_texture_extensions(extension, mime):
    doc = document()
    doc.update(extensionsUsed=[extension, "KHR_texture_transform"], extensionsRequired=[extension, "KHR_texture_transform"])
    doc["images"] = [{"bufferView": 0, "mimeType": mime}]
    doc["textures"] = [{"extensions": {extension: {"source": 0}}}]
    doc["materials"] = [{"pbrMetallicRoughness": {"baseColorTexture": {
        "index": 0, "extensions": {"KHR_texture_transform": {"offset": [0, 0]}}}}}]
    service().validate_model_bytes(glb(doc))
    doc["images"] = [{"uri": f"data:{mime};base64,AAAA"}]
    service().validate_model_bytes(glb(doc))
    doc["textures"][0]["extensions"][extension]["source"] = 1
    reject(glb(doc))


@pytest.mark.parametrize("extension,stride,accepted", [
    ("KHR_meshopt_compression", 4, True), ("KHR_meshopt_compression", 8, True),
    ("KHR_meshopt_compression", 12, False), ("EXT_meshopt_compression", 4, False),
])
def test_meshopt_color_filter(extension, stride, accepted):
    doc = document()
    doc.update(extensionsUsed=[extension], extensionsRequired=[extension])
    doc["bufferViews"].append({"buffer": 0, "byteLength": stride * 3,
        "extensions": {extension: {"buffer": 0, "byteLength": 12,
            "byteStride": stride, "count": 3, "mode": "ATTRIBUTES", "filter": "COLOR"}}})
    if accepted:
        service().validate_model_bytes(glb(doc))
    else:
        reject(glb(doc))


def test_meshopt_variants_cannot_share_buffer_view():
    doc = document()
    names = ["EXT_meshopt_compression", "KHR_meshopt_compression"]
    doc.update(extensionsUsed=names, extensionsRequired=names)
    doc["bufferViews"][0]["extensions"] = {name: {"buffer": 0, "byteLength": 12,
        "byteStride": 12, "count": 3, "mode": "ATTRIBUTES"} for name in names}
    reject(glb(doc))


@pytest.mark.parametrize("status", [None, 201, 500])
def test_upload_unknown_or_failed_status_cleans_only_generated_key(uploader, monkeypatch, tmp_path, status):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    path = tmp_path / "model"
    path.write_bytes(glb())
    uploader._bucket.put_object.return_value.status = status
    with pytest.raises(ValueError, match="上传"):
        model.upload_model_file(path, "model.glb")
    generated_key = uploader._bucket.put_object.call_args.args[0]
    assert uploader.validate_product_model_path(generated_key) == generated_key
    uploader._bucket.delete_object.assert_called_once_with(generated_key)


def test_upload_network_exception_cleans_generated_key_and_hides_cleanup_error(uploader, monkeypatch, tmp_path):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    path = tmp_path / "model"
    path.write_bytes(glb())
    uploader._bucket.put_object.side_effect = RuntimeError("put secret")
    uploader.delete_product_model = Mock(side_effect=RuntimeError("delete secret"))
    with pytest.raises(ValueError, match="上传") as caught:
        model.upload_model_file(path, "model.glb")
    generated_key = uploader._bucket.put_object.call_args.args[0]
    uploader.delete_product_model.assert_called_once_with(generated_key)
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("returned_path", ["order/keep.jpg", KEY])
def test_upload_never_cleans_an_error_results_supplied_path(uploader, monkeypatch, tmp_path, returned_path):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    path = tmp_path / "model"
    path.write_bytes(glb())
    uploader.upload_bytes = Mock(return_value={"error": "secret", "path": returned_path})
    with pytest.raises(ValueError, match="上传"):
        model.upload_model_file(path, "model.glb")
    generated_key = uploader.upload_bytes.call_args.kwargs["remote_path"]
    assert generated_key != returned_path
    uploader._bucket.delete_object.assert_called_once_with(generated_key)


def test_upload_success_and_preflight_failure_never_delete(uploader, monkeypatch, tmp_path):
    model = service()
    monkeypatch.setattr(model, "get_config", lambda: SimpleNamespace(oss_config={}))
    monkeypatch.setattr(model, "OSSUploader", lambda config: uploader)
    path = tmp_path / "model"
    path.write_bytes(glb())
    model.upload_model_file(path, "model.glb")
    uploader._bucket.delete_object.assert_not_called()
    monkeypatch.setattr(model, "get_config", Mock(side_effect=RuntimeError("secret")))
    with pytest.raises(ValueError, match="上传"):
        model.upload_model_file(path, "model.glb")
    uploader._bucket.delete_object.assert_not_called()
