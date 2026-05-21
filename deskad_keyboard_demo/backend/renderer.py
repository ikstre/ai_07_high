import base64
import json
import math
import struct
from pathlib import Path


def hex_to_rgba(value: str) -> list[float]:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        value = "cccccc"
    r = int(value[0:2], 16) / 255
    g = int(value[2:4], 16) / 255
    b = int(value[4:6], 16) / 255
    return [r, g, b, 1.0]


class GlbBuilder:
    def __init__(self):
        self.positions: list[float] = []
        self.normals: list[float] = []
        self.indices: list[int] = []
        self.meshes: list[dict] = []
        self.nodes: list[dict] = []
        self.materials: list[dict] = []
        self._index_ranges: list[tuple[int, int, int]] = []

    def add_material(self, name: str, color: str, roughness: float = 0.55, metallic: float = 0.0) -> int:
        material_index = len(self.materials)
        self.materials.append(
            {
                "name": name,
                "pbrMetallicRoughness": {
                    "baseColorFactor": hex_to_rgba(color),
                    "roughnessFactor": roughness,
                    "metallicFactor": metallic,
                },
            }
        )
        return material_index

    def add_box(
        self,
        name: str,
        center: tuple[float, float, float],
        size: tuple[float, float, float],
        material: int,
        taper: float = 0.0,
        rotation_x: float = 0.0,
    ) -> None:
        cx, cy, cz = center
        sx, sy, sz = size
        bottom_x = sx / 2
        bottom_z = sz / 2
        top_x = max(0.01, sx / 2 - taper)
        top_z = max(0.01, sz / 2 - taper)
        y0 = -sy / 2
        y1 = sy / 2

        vertices = [
            (-bottom_x, y0, -bottom_z),
            (bottom_x, y0, -bottom_z),
            (bottom_x, y0, bottom_z),
            (-bottom_x, y0, bottom_z),
            (-top_x, y1, -top_z),
            (top_x, y1, -top_z),
            (top_x, y1, top_z),
            (-top_x, y1, top_z),
        ]
        faces = [
            (0, 1, 2, 3, (0, -1, 0)),
            (4, 7, 6, 5, (0, 1, 0)),
            (0, 4, 5, 1, (0, 0, -1)),
            (1, 5, 6, 2, (1, 0, 0)),
            (2, 6, 7, 3, (0, 0, 1)),
            (3, 7, 4, 0, (-1, 0, 0)),
        ]

        start_vertex = len(self.positions) // 3
        start_index = len(self.indices)
        cos_rx = math.cos(rotation_x)
        sin_rx = math.sin(rotation_x)

        for face in faces:
            normal = face[4]
            nx, ny, nz = normal
            rotated_normal = (nx, ny * cos_rx - nz * sin_rx, ny * sin_rx + nz * cos_rx)
            for vertex_index in face[:4]:
                x, y, z = vertices[vertex_index]
                ry = y * cos_rx - z * sin_rx
                rz = y * sin_rx + z * cos_rx
                self.positions.extend([x + cx, ry + cy, rz + cz])
                self.normals.extend(rotated_normal)

        for face_i in range(len(faces)):
            i = start_vertex + face_i * 4
            self.indices.extend([i, i + 1, i + 2, i, i + 2, i + 3])

        index_range_id = len(self._index_ranges)
        self._index_ranges.append((start_index, len(self.indices) - start_index, material))

        mesh_index = len(self.meshes)
        self.meshes.append(
            {
                "name": name,
                "primitives": [
                    {
                        "attributes": {"POSITION": 0, "NORMAL": 1},
                        "indices": 2 + index_range_id,
                        "material": material,
                    }
                ],
            }
        )
        self.nodes.append({"name": name, "mesh": mesh_index})

    def export(self, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        position_bytes = struct.pack(f"<{len(self.positions)}f", *self.positions)
        normal_bytes = struct.pack(f"<{len(self.normals)}f", *self.normals)
        index_bytes = struct.pack(f"<{len(self.indices)}I", *self.indices)

        chunks = []
        byte_offset = 0
        for blob in (position_bytes, normal_bytes, index_bytes):
            padding = (4 - len(blob) % 4) % 4
            chunks.append((byte_offset, len(blob), blob + (b"\x00" * padding)))
            byte_offset += len(blob) + padding

        binary_blob = b"".join(chunk[2] for chunk in chunks)
        position_offset, position_length, _ = chunks[0]
        normal_offset, normal_length, _ = chunks[1]
        index_offset, index_length, _ = chunks[2]

        min_pos = [
            min(self.positions[0::3]),
            min(self.positions[1::3]),
            min(self.positions[2::3]),
        ]
        max_pos = [
            max(self.positions[0::3]),
            max(self.positions[1::3]),
            max(self.positions[2::3]),
        ]

        buffer_views = [
            {"buffer": 0, "byteOffset": position_offset, "byteLength": position_length, "target": 34962},
            {"buffer": 0, "byteOffset": normal_offset, "byteLength": normal_length, "target": 34962},
        ]
        accessors = [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": len(self.positions) // 3,
                "type": "VEC3",
                "min": min_pos,
                "max": max_pos,
            },
            {
                "bufferView": 1,
                "componentType": 5126,
                "count": len(self.normals) // 3,
                "type": "VEC3",
            },
        ]

        for start_index, index_count, _material in self._index_ranges:
            buffer_view_index = len(buffer_views)
            buffer_views.append(
                {
                    "buffer": 0,
                    "byteOffset": index_offset + start_index * 4,
                    "byteLength": index_count * 4,
                    "target": 34963,
                }
            )
            accessors.append(
                {
                    "bufferView": buffer_view_index,
                    "componentType": 5125,
                    "count": index_count,
                    "type": "SCALAR",
                }
            )

        gltf = {
            "asset": {"version": "2.0", "generator": "DeskAd demo GLB builder"},
            "scene": 0,
            "scenes": [{"nodes": list(range(len(self.nodes)))}],
            "nodes": self.nodes,
            "meshes": self.meshes,
            "materials": self.materials,
            "buffers": [{"byteLength": len(binary_blob)}],
            "bufferViews": buffer_views,
            "accessors": accessors,
        }

        json_blob = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        json_blob += b" " * ((4 - len(json_blob) % 4) % 4)

        total_length = 12 + 8 + len(json_blob) + 8 + len(binary_blob)
        with output_path.open("wb") as file:
            file.write(struct.pack("<4sII", b"glTF", 2, total_length))
            file.write(struct.pack("<I4s", len(json_blob), b"JSON"))
            file.write(json_blob)
            file.write(struct.pack("<I4s", len(binary_blob), b"BIN\x00"))
            file.write(binary_blob)


def build_keyboard_scene_glb(
    layout_path: Path,
    output_path: Path,
    case_color: str,
    keycap_color: str,
    accent_keycap_color: str,
    deskmat_color: str,
    desk_color: str,
    mouse_color: str,
) -> dict:
    layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
    keys = layout_data["layouts"]["LAYOUT"]["layout"]
    board_width = float(layout_data["width"])
    board_depth = float(layout_data["height"])

    builder = GlbBuilder()
    case_mat = builder.add_material("case", case_color, roughness=0.35, metallic=0.15)
    keycap_mat = builder.add_material("keycaps", keycap_color, roughness=0.75, metallic=0.0)
    accent_mat = builder.add_material("accent keycaps", accent_keycap_color, roughness=0.7, metallic=0.0)
    deskmat_mat = builder.add_material("deskmat", deskmat_color, roughness=0.9, metallic=0.0)
    desk_mat = builder.add_material("desk", desk_color, roughness=0.8, metallic=0.0)
    mouse_mat = builder.add_material("mouse", mouse_color, roughness=0.48, metallic=0.0)
    mouse_detail_mat = builder.add_material("mouse details", "#d8dde5", roughness=0.58, metallic=0.0)

    # Default scene objects: desk, deskmat, keyboard, mouse.
    builder.add_box("desk", (0, -0.18, 0), (board_width + 7.0, 0.18, board_depth + 6.0), desk_mat)
    builder.add_box("deskmat", (0, 0.02, 0.15), (board_width + 3.0, 0.06, board_depth + 2.2), deskmat_mat)
    builder.add_box("keyboard case", (0, 0.45, 0), (board_width + 0.9, 0.58, board_depth + 0.9), case_mat, taper=0.08)

    accent_indices = {0, 13, 14, 42, 56, 65, 66}
    for index, key in enumerate(keys):
        key_w = float(key.get("w", 1))
        key_h = float(key.get("h", 1))
        x = float(key["x"]) - board_width / 2 + key_w / 2
        z = float(key["y"]) - board_depth / 2 + key_h / 2
        row = int(min(4, max(1, key["y"] + 1)))
        angle = math.radians({1: -2, 2: 1, 3: 4, 4: 7}.get(row, 2))
        material = accent_mat if index in accent_indices or key_w >= 2.0 else keycap_mat
        builder.add_box(
            name=f"key {index + 1}",
            center=(x, 1.02, z),
            size=(key_w - 0.08, 0.42, key_h - 0.08),
            material=material,
            taper=0.11,
            rotation_x=angle,
        )

    mouse_x = board_width / 2 + 2.4
    builder.add_box("mouse body", (mouse_x, 0.42, 0.45), (1.55, 0.34, 2.35), mouse_mat, taper=0.22)
    builder.add_box("mouse left button", (mouse_x - 0.28, 0.64, -0.28), (0.48, 0.05, 0.82), mouse_detail_mat, taper=0.04)
    builder.add_box("mouse right button", (mouse_x + 0.28, 0.64, -0.28), (0.48, 0.05, 0.82), mouse_detail_mat, taper=0.04)
    builder.add_box("mouse wheel", (mouse_x, 0.69, -0.42), (0.14, 0.08, 0.42), mouse_detail_mat, taper=0.02)
    builder.add_box("monitor stand", (0, 0.36, -board_depth / 2 - 1.4), (5.5, 0.32, 0.8), case_mat, taper=0.04)

    builder.export(output_path)
    return {
        "key_count": len(keys),
        "board_width": board_width,
        "board_depth": board_depth,
        "default_objects": ["desk", "deskmat", "keyboard", "mouse"],
        "model_file": output_path.name,
    }
