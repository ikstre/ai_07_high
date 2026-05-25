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

    def add_cylinder_y(
        self,
        name: str,
        center: tuple[float, float, float],
        radius_x: float,
        height: float,
        material: int,
        radius_z: float | None = None,
        top_radius_x: float | None = None,
        top_radius_z: float | None = None,
        segments: int = 24,
    ) -> None:
        cx, cy, cz = center
        radius_z = radius_x if radius_z is None else radius_z
        top_radius_x = radius_x if top_radius_x is None else top_radius_x
        top_radius_z = radius_z if top_radius_z is None else top_radius_z
        y0 = cy - height / 2
        y1 = cy + height / 2
        start_vertex = len(self.positions) // 3
        start_index = len(self.indices)

        for index in range(segments):
            a0 = 2 * math.pi * index / segments
            a1 = 2 * math.pi * (index + 1) / segments
            c0, s0 = math.cos(a0), math.sin(a0)
            c1, s1 = math.cos(a1), math.sin(a1)
            verts = [
                (cx + radius_x * c0, y0, cz + radius_z * s0, c0, 0, s0),
                (cx + radius_x * c1, y0, cz + radius_z * s1, c1, 0, s1),
                (cx + top_radius_x * c1, y1, cz + top_radius_z * s1, c1, 0, s1),
                (cx + top_radius_x * c0, y1, cz + top_radius_z * s0, c0, 0, s0),
            ]
            for x, y, z, nx, ny, nz in verts:
                self.positions.extend([x, y, z])
                self.normals.extend([nx, ny, nz])
            base = start_vertex + index * 4
            self.indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

        cap_start = len(self.positions) // 3
        for index in range(segments):
            a0 = 2 * math.pi * index / segments
            a1 = 2 * math.pi * (index + 1) / segments
            for x, y, z, normal in [
                (cx, y0, cz, (0, -1, 0)),
                (cx + radius_x * math.cos(a1), y0, cz + radius_z * math.sin(a1), (0, -1, 0)),
                (cx + radius_x * math.cos(a0), y0, cz + radius_z * math.sin(a0), (0, -1, 0)),
                (cx, y1, cz, (0, 1, 0)),
                (cx + top_radius_x * math.cos(a0), y1, cz + top_radius_z * math.sin(a0), (0, 1, 0)),
                (cx + top_radius_x * math.cos(a1), y1, cz + top_radius_z * math.sin(a1), (0, 1, 0)),
            ]:
                self.positions.extend([x, y, z])
                self.normals.extend(normal)
            base = cap_start + index * 6
            self.indices.extend([base, base + 1, base + 2, base + 3, base + 4, base + 5])

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

    def add_cylinder_z(
        self,
        name: str,
        center: tuple[float, float, float],
        radius_x: float,
        radius_y: float,
        depth: float,
        material: int,
        segments: int = 24,
    ) -> None:
        cx, cy, cz = center
        z0 = cz - depth / 2
        z1 = cz + depth / 2
        start_vertex = len(self.positions) // 3
        start_index = len(self.indices)

        for index in range(segments):
            a0 = 2 * math.pi * index / segments
            a1 = 2 * math.pi * (index + 1) / segments
            c0, s0 = math.cos(a0), math.sin(a0)
            c1, s1 = math.cos(a1), math.sin(a1)
            verts = [
                (cx + radius_x * c0, cy + radius_y * s0, z0, c0, s0, 0),
                (cx + radius_x * c1, cy + radius_y * s1, z0, c1, s1, 0),
                (cx + radius_x * c1, cy + radius_y * s1, z1, c1, s1, 0),
                (cx + radius_x * c0, cy + radius_y * s0, z1, c0, s0, 0),
            ]
            for x, y, z, nx, ny, nz in verts:
                self.positions.extend([x, y, z])
                self.normals.extend([nx, ny, nz])
            base = start_vertex + index * 4
            self.indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])

        cap_start = len(self.positions) // 3
        for index in range(segments):
            a0 = 2 * math.pi * index / segments
            a1 = 2 * math.pi * (index + 1) / segments
            for x, y, z, normal in [
                (cx, cy, z0, (0, 0, -1)),
                (cx + radius_x * math.cos(a0), cy + radius_y * math.sin(a0), z0, (0, 0, -1)),
                (cx + radius_x * math.cos(a1), cy + radius_y * math.sin(a1), z0, (0, 0, -1)),
                (cx, cy, z1, (0, 0, 1)),
                (cx + radius_x * math.cos(a1), cy + radius_y * math.sin(a1), z1, (0, 0, 1)),
                (cx + radius_x * math.cos(a0), cy + radius_y * math.sin(a0), z1, (0, 0, 1)),
            ]:
                self.positions.extend([x, y, z])
                self.normals.extend(normal)
            base = cap_start + index * 6
            self.indices.extend([base, base + 1, base + 2, base + 3, base + 4, base + 5])

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




# Desk setup renderer scale: 1 GLB unit = 1 centimeter.
# Keyboard layout JSON is in MX key units. Standard MX spacing is 19.05 mm.
U_CM = 1.905
TABLE_TOP_THICKNESS_CM = 2.5
SURFACE_Y = 0.0


def _layout_size_cm(layout_data: dict) -> tuple[float, float]:
    return float(layout_data["width"]) * U_CM, float(layout_data["height"]) * U_CM


def _surface_center_y(height_cm: float) -> float:
    return SURFACE_Y + height_cm / 2


def _add_keyboard(
    builder: GlbBuilder,
    *,
    layout_data: dict,
    center: tuple[float, float],
    case_mat: int,
    keycap_mat: int,
    accent_mat: int,
) -> dict:
    keys = layout_data["layouts"]["LAYOUT"]["layout"]
    board_width_u = float(layout_data["width"])
    board_depth_u = float(layout_data["height"])
    board_width_cm, board_depth_cm = _layout_size_cm(layout_data)
    case_margin_cm = 1.6
    case_height_cm = 2.4
    key_height_cm = 0.8
    key_gap_cm = 0.16
    center_x, center_z = center

    builder.add_box(
        "keyboard case",
        (center_x, _surface_center_y(case_height_cm), center_z),
        (board_width_cm + case_margin_cm * 2, case_height_cm, board_depth_cm + case_margin_cm * 2),
        case_mat,
        taper=0.35,
    )

    accent_indices = {0, 13, 14, 42, 56, 65, 66}
    for index, key in enumerate(keys):
        key_w_u = float(key.get("w", 1))
        key_h_u = float(key.get("h", 1))
        x = (float(key["x"]) - board_width_u / 2 + key_w_u / 2) * U_CM + center_x
        z = (float(key["y"]) - board_depth_u / 2 + key_h_u / 2) * U_CM + center_z
        row = int(min(4, max(1, key["y"] + 1)))
        angle = math.radians({1: -2, 2: 1, 3: 4, 4: 7}.get(row, 2))
        material = accent_mat if index in accent_indices or key_w_u >= 2.0 else keycap_mat
        builder.add_box(
            name=f"key {index + 1}",
            center=(x, SURFACE_Y + case_height_cm + key_height_cm / 2 - 0.1, z),
            size=(max(0.6, key_w_u * U_CM - key_gap_cm), key_height_cm, max(0.6, key_h_u * U_CM - key_gap_cm)),
            material=material,
            taper=0.18,
            rotation_x=angle,
        )

    return {
        "key_count": len(keys),
        "board_width": round(board_width_cm, 1),
        "board_depth": round(board_depth_cm, 1),
        "keyboard_unit": "cm",
        "keyboard_source": "MX 1u spacing 19.05mm",
    }


def _add_mouse(builder: GlbBuilder, *, center: tuple[float, float], mouse_mat: int, detail_mat: int) -> None:
    x, z = center
    builder.add_box("mouse body", (x, _surface_center_y(3.6), z), (6.3, 3.6, 11.8), mouse_mat, taper=1.0)
    builder.add_box("mouse left button", (x - 1.25, SURFACE_Y + 3.75, z - 2.3), (2.25, 0.28, 4.1), detail_mat, taper=0.18)
    builder.add_box("mouse right button", (x + 1.25, SURFACE_Y + 3.75, z - 2.3), (2.25, 0.28, 4.1), detail_mat, taper=0.18)
    builder.add_box("mouse wheel", (x, SURFACE_Y + 4.0, z - 3.3), (0.62, 0.45, 1.5), detail_mat, taper=0.12)


_MONITOR_SIZES_CM: dict[str, tuple[float, float]] = {
    "24": (56.0, 33.0),
    "27": (62.0, 36.0),
    "32": (74.0, 43.0),
}


def _add_monitor(builder: GlbBuilder, *, center_x: float, center_z: float, body_mat: int, screen_mat: int, with_stand: bool = True, monitor_size: str = "27") -> None:
    # Panel sizes per diagonal: 24" ≈56×33 cm, 27" ≈62×36 cm, 32" ≈74×43 cm (16:9 + bezel).
    screen_w, screen_h = _MONITOR_SIZES_CM.get(monitor_size, _MONITOR_SIZES_CM["27"])
    screen_thickness = 2.6
    screen_center_y = SURFACE_Y + 34.0
    screen_center_z = center_z - 2.0
    screen_back_z = screen_center_z - screen_thickness / 2 - 0.35

    if with_stand:
        # Front face is +Z. The neck must sit behind the panel, not in front of the display.
        builder.add_box("monitor base", (center_x, _surface_center_y(1.2), screen_center_z + 8.0), (24.0, 1.2, 18.0), body_mat, taper=0.55)
        builder.add_box("monitor neck", (center_x, SURFACE_Y + 13.5, screen_back_z), (3.0, 25.0, 2.6), body_mat, taper=0.18)
        builder.add_box("monitor hinge", (center_x, SURFACE_Y + 25.5, screen_back_z + 0.6), (10.0, 3.2, 2.8), body_mat, taper=0.16)

    builder.add_box("monitor screen", (center_x, screen_center_y, screen_center_z), (screen_w, screen_h, screen_thickness), body_mat, taper=0.35)
    builder.add_box(
        "monitor display",
        (center_x, screen_center_y, screen_center_z + screen_thickness / 2 + 0.06),
        (max(1.0, screen_w - 2.2), max(1.0, screen_h - 2.4), 0.12),
        screen_mat,
        taper=0.08,
    )


def _add_monitor_arm(builder: GlbBuilder, *, center_x: float, center_z: float, body_mat: int, back_z: float | None = None) -> None:
    screen_center_z = center_z - 2.0
    screen_back_z = screen_center_z - 1.65
    raw_clamp_z = center_z - 16.0
    # Keep clamp at least 3.5 cm inside the desk back edge so it doesn't clip out.
    clamp_z = max(back_z + 3.5, raw_clamp_z) if back_z is not None else raw_clamp_z
    mid_z = (clamp_z + screen_back_z) / 2
    builder.add_box("vesa desk clamp", (center_x, _surface_center_y(6.0), clamp_z), (9.0, 6.0, 5.0), body_mat, taper=0.18)
    builder.add_box("monitor arm upright", (center_x, SURFACE_Y + 18.0, clamp_z), (2.2, 30.0, 2.2), body_mat, taper=0.08)
    builder.add_box("monitor arm boom", (center_x, SURFACE_Y + 31.0, mid_z), (2.6, 2.0, abs(screen_back_z - clamp_z)), body_mat, taper=0.08)
    builder.add_box("vesa plate 100x100", (center_x, SURFACE_Y + 31.0, screen_back_z), (10.0, 10.0, 0.8), body_mat, taper=0.08)


def _add_desk_lamp(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, light_mat: int, arm_dir: float = 1.0) -> None:
    """arm_dir: +1.0 extends arm toward desk center (right), -1.0 toward outside (left)."""
    x, z = center
    arm_x = x + arm_dir * 9.0
    shade_x = x + arm_dir * 21.0
    builder.add_cylinder_y("lamp round base", (x, _surface_center_y(1.2), z), 6.5, 1.2, body_mat, radius_z=6.5)
    builder.add_cylinder_y("lamp lower arm", (x, SURFACE_Y + 14.0, z), 0.95, 27.0, body_mat, radius_z=0.95, segments=16)
    builder.add_box("lamp upper arm", (arm_x, SURFACE_Y + 27.0, z - 4.0), (21.0, 1.6, 1.6), body_mat, taper=0.08)
    builder.add_cylinder_y(
        "lamp tapered shade",
        (shade_x, SURFACE_Y + 25.0, z - 4.0),
        6.8,
        6.2,
        body_mat,
        radius_z=6.8,
        top_radius_x=4.2,
        top_radius_z=4.2,
        segments=24,
    )
    builder.add_cylinder_y("lamp warm light", (shade_x, SURFACE_Y + 21.8, z - 4.0), 4.4, 0.25, light_mat, radius_z=4.4, segments=24)


def _add_plant(builder: GlbBuilder, *, center: tuple[float, float], pot_mat: int, leaf_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("plant ceramic pot", (x, _surface_center_y(8.0), z), 4.9, 8.0, pot_mat, radius_z=4.9, top_radius_x=5.7, top_radius_z=5.7, segments=24)
    builder.add_box("plant leaf back", (x, SURFACE_Y + 15.0, z - 1.0), (3.2, 14.0, 5.6), leaf_mat, taper=1.0, rotation_x=math.radians(-18))
    builder.add_box("plant leaf left", (x - 3.4, SURFACE_Y + 13.2, z + 0.2), (2.8, 11.5, 4.8), leaf_mat, taper=1.0, rotation_x=math.radians(22))
    builder.add_box("plant leaf right", (x + 3.4, SURFACE_Y + 13.2, z + 0.2), (2.8, 11.5, 4.8), leaf_mat, taper=1.0, rotation_x=math.radians(12))


def _add_speakers(builder: GlbBuilder, *, left_x: float, right_x: float, z: float, body_mat: int, cone_mat: int) -> None:
    for label, x in (("left", left_x), ("right", right_x)):
        builder.add_box(f"{label} speaker cabinet", (x, _surface_center_y(18.0), z), (11.5, 18.0, 10.0), body_mat, taper=0.28)
        builder.add_cylinder_z(f"{label} speaker tweeter", (x, SURFACE_Y + 12.8, z + 5.18), 1.6, 1.6, 0.36, cone_mat, segments=24)
        builder.add_cylinder_z(f"{label} speaker woofer", (x, SURFACE_Y + 6.7, z + 5.18), 3.1, 3.1, 0.36, cone_mat, segments=24)


def _add_desk_shelf(builder: GlbBuilder, *, center: tuple[float, float], wood_mat: int, support_mat: int) -> None:
    x, z = center
    builder.add_box("desk shelf top", (x, SURFACE_Y + 8.0, z), (72.0, 2.4, 22.0), wood_mat, taper=0.25)
    builder.add_box("desk shelf left leg", (x - 31.0, SURFACE_Y + 4.0, z), (2.5, 8.0, 16.0), support_mat, taper=0.08)
    builder.add_box("desk shelf right leg", (x + 31.0, SURFACE_Y + 4.0, z), (2.5, 8.0, 16.0), support_mat, taper=0.08)


def _add_notebook(builder: GlbBuilder, *, center: tuple[float, float], cover_mat: int, page_mat: int) -> None:
    x, z = center
    builder.add_box("notebook cover", (x, SURFACE_Y + 0.55, z), (15.0, 0.55, 21.0), cover_mat, taper=0.2, rotation_x=math.radians(-2))
    builder.add_box("notebook pages", (x + 0.4, SURFACE_Y + 0.95, z + 0.2), (13.5, 0.45, 19.0), page_mat, taper=0.15, rotation_x=math.radians(-2))


def _add_headphone_stand(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_box("headphone stand base", (x, _surface_center_y(1.2), z), (14.0, 1.2, 9.0), body_mat, taper=0.25)
    builder.add_box("headphone stand pole", (x, SURFACE_Y + 13.0, z), (2.0, 25.0, 2.0), body_mat, taper=0.08)
    builder.add_box("headphone stand cradle", (x, SURFACE_Y + 25.5, z), (11.0, 1.8, 3.0), body_mat, taper=0.12)
    builder.add_box("headphone band preview", (x, SURFACE_Y + 21.5, z + 3.2), (13.0, 2.2, 1.8), accent_mat, taper=0.25)


def _add_phone_stand(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, screen_mat: int) -> None:
    x, z = center
    builder.add_box("phone stand base", (x, SURFACE_Y + 0.45, z), (8.0, 0.9, 8.8), body_mat, taper=0.18)
    builder.add_box("phone stand back plate", (x, SURFACE_Y + 6.2, z - 2.2), (7.0, 11.5, 1.0), body_mat, taper=0.14, rotation_x=math.radians(-10))
    builder.add_box("phone glass preview", (x, SURFACE_Y + 6.35, z - 1.55), (5.8, 9.6, 0.18), screen_mat, taper=0.12, rotation_x=math.radians(-10))
    builder.add_box("phone stand lip", (x, SURFACE_Y + 1.7, z + 1.7), (7.8, 1.2, 1.2), body_mat, taper=0.1)


def _add_keycap_tray(builder: GlbBuilder, *, center: tuple[float, float], tray_mat: int, cap_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_box("keycap tray base", (x, SURFACE_Y + 0.5, z), (20.0, 1.0, 12.0), tray_mat, taper=0.28)
    builder.add_box("keycap tray back rail", (x, SURFACE_Y + 1.5, z - 5.6), (20.0, 2.2, 0.9), tray_mat, taper=0.12)
    builder.add_box("keycap tray front rail", (x, SURFACE_Y + 1.5, z + 5.6), (20.0, 2.2, 0.9), tray_mat, taper=0.12)
    builder.add_box("keycap tray left rail", (x - 9.6, SURFACE_Y + 1.5, z), (0.9, 2.2, 12.0), tray_mat, taper=0.12)
    builder.add_box("keycap tray right rail", (x + 9.6, SURFACE_Y + 1.5, z), (0.9, 2.2, 12.0), tray_mat, taper=0.12)
    offsets = [(-5.7, -2.4), (-1.9, -2.4), (1.9, -2.4), (5.7, -2.4), (-3.8, 2.0), (0.0, 2.0), (3.8, 2.0)]
    for index, (dx, dz) in enumerate(offsets):
        material = accent_mat if index in {2, 5} else cap_mat
        builder.add_box(f"display keycap {index + 1}", (x + dx, SURFACE_Y + 2.25, z + dz), (2.9, 1.0, 2.9), material, taper=0.28)


def _add_coffee_mug(builder: GlbBuilder, *, center: tuple[float, float], mug_mat: int, coffee_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("coffee mug body", (x, SURFACE_Y + 4.0, z), 4.0, 8.0, mug_mat, radius_z=4.0, top_radius_x=4.3, top_radius_z=4.3, segments=28)
    builder.add_cylinder_y("coffee surface", (x, SURFACE_Y + 8.12, z), 3.45, 0.16, coffee_mat, radius_z=3.45, segments=28)
    builder.add_box("coffee mug handle upper", (x + 4.6, SURFACE_Y + 5.6, z), (1.1, 1.2, 4.8), mug_mat, taper=0.18)
    builder.add_box("coffee mug handle lower", (x + 4.6, SURFACE_Y + 2.7, z), (1.1, 1.2, 4.8), mug_mat, taper=0.18)
    builder.add_box("coffee mug handle side", (x + 5.4, SURFACE_Y + 4.15, z), (1.1, 4.0, 1.2), mug_mat, taper=0.18)


def build_desk_setup_scene_glb(
    *,
    layout_path: Path,
    output_path: Path,
    case_color: str,
    keycap_color: str,
    accent_keycap_color: str,
    deskmat_color: str,
    desk_color: str,
    mouse_color: str,
    theme: str,
    assets: list[str],
    desk_width: float = 120.0,
    desk_depth: float = 60.0,
    monitor_size: str = "27",
) -> dict:
    layout_data = json.loads(layout_path.read_text(encoding="utf-8"))

    builder = GlbBuilder()
    case_mat = builder.add_material("keyboard case", case_color, roughness=0.35, metallic=0.15)
    keycap_mat = builder.add_material("keycaps", keycap_color, roughness=0.75, metallic=0.0)
    accent_mat = builder.add_material("accent", accent_keycap_color, roughness=0.7, metallic=0.0)
    deskmat_mat = builder.add_material("deskmat", deskmat_color, roughness=0.9, metallic=0.0)
    desk_mat = builder.add_material("desk", desk_color, roughness=0.8, metallic=0.0)
    mouse_mat = builder.add_material("mouse", mouse_color, roughness=0.48, metallic=0.0)
    neutral_mat = builder.add_material("graphite accessory", "#30343b", roughness=0.55, metallic=0.1)
    screen_mat = builder.add_material("soft display glow", "#101827", roughness=0.36, metallic=0.0)
    warm_light_mat = builder.add_material("warm lamp glow", "#f8d28b", roughness=0.2, metallic=0.0)
    plant_mat = builder.add_material("desk plant leaves", "#59795a", roughness=0.86, metallic=0.0)
    pot_mat = builder.add_material("ceramic pot", "#d6c8b9", roughness=0.68, metallic=0.0)
    page_mat = builder.add_material("notebook pages", "#f5f1e8", roughness=0.72, metallic=0.0)
    coffee_mat = builder.add_material("coffee surface", "#3b2417", roughness=0.62, metallic=0.0)

    if theme == "gaming":
        screen_mat = builder.add_material("rgb display glow", "#2237ff", roughness=0.28, metallic=0.0)
        warm_light_mat = builder.add_material("rgb accent glow", "#cb4dff", roughness=0.25, metallic=0.0)
    elif theme == "pastel":
        pot_mat = builder.add_material("pastel pot", "#c9d8ef", roughness=0.72, metallic=0.0)
    elif theme == "premium":
        neutral_mat = builder.add_material("anodized dark metal", "#1f242b", roughness=0.42, metallic=0.25)

    enabled_assets = set(assets)
    desk_width = max(100.0, min(float(desk_width), 200.0))
    desk_depth = max(50.0, min(float(desk_depth), 90.0))
    front_z = desk_depth / 2
    back_z = -desk_depth / 2

    builder.add_box("desk tabletop", (0, -TABLE_TOP_THICKNESS_CM / 2, 0), (desk_width, TABLE_TOP_THICKNESS_CM, desk_depth), desk_mat, taper=0.55)
    builder.add_box("deskmat", (0, SURFACE_Y + 0.18, 12.0), (min(90.0, desk_width - 24.0), 0.35, 30.0), deskmat_mat, taper=0.8)

    keyboard_meta = _add_keyboard(
        builder,
        layout_data=layout_data,
        center=(0, 15.0),
        case_mat=case_mat,
        keycap_mat=keycap_mat,
        accent_mat=accent_mat,
    )

    keyboard_right = keyboard_meta["board_width"] / 2
    if "mouse" in enabled_assets:
        _add_mouse(builder, center=(keyboard_right + 14.0, 15.5), mouse_mat=mouse_mat, detail_mat=page_mat)
    monitor_center_z = back_z + 18.0
    if "monitor" in enabled_assets:
        _add_monitor(
            builder,
            center_x=0,
            center_z=monitor_center_z,
            body_mat=neutral_mat,
            screen_mat=screen_mat,
            with_stand="monitor_arm" not in enabled_assets,
            monitor_size=monitor_size,
        )
    if "monitor_arm" in enabled_assets:
        _add_monitor_arm(builder, center_x=0, center_z=monitor_center_z, body_mat=neutral_mat, back_z=back_z)
    if "desk_lamp" in enabled_assets:
        # Front-left placement keeps the lamp visible in both perspective and top view.
        lamp_z = min(front_z - 14.0, 14.0)
        _add_desk_lamp(builder, center=(-desk_width / 2 + 17.0, lamp_z), body_mat=neutral_mat, light_mat=warm_light_mat, arm_dir=1.0)
    if "plant" in enabled_assets:
        _add_plant(builder, center=(desk_width / 2 - 14.0, back_z + 17.0), pot_mat=pot_mat, leaf_mat=plant_mat)
    if "speakers" in enabled_assets:
        speaker_gap = min(43.0, desk_width / 2 - 24.0)
        _add_speakers(builder, left_x=-speaker_gap, right_x=speaker_gap, z=back_z + 22.0, body_mat=neutral_mat, cone_mat=warm_light_mat)
    if "desk_shelf" in enabled_assets:
        _add_desk_shelf(builder, center=(0, back_z + 19.0), wood_mat=desk_mat, support_mat=neutral_mat)
    if "notebook" in enabled_assets:
        _add_notebook(builder, center=(-desk_width / 2 + 22.0, front_z - 18.0), cover_mat=accent_mat, page_mat=page_mat)
    if "headphone_stand" in enabled_assets:
        _add_headphone_stand(builder, center=(desk_width / 2 - 16.0, front_z - 16.0), body_mat=neutral_mat, accent_mat=accent_mat)
    if "phone_stand" in enabled_assets:
        _add_phone_stand(builder, center=(desk_width / 2 - 16.0, back_z + 20.0), body_mat=neutral_mat, screen_mat=screen_mat)
    if "keycap_tray" in enabled_assets:
        _add_keycap_tray(builder, center=(-desk_width / 2 + 24.0, front_z - 12.0), tray_mat=neutral_mat, cap_mat=keycap_mat, accent_mat=accent_mat)
    if "coffee_mug" in enabled_assets:
        _add_coffee_mug(builder, center=(desk_width / 2 - 13.0, 2.0), mug_mat=page_mat, coffee_mat=coffee_mat)

    if theme == "gaming":
        builder.add_box("rgb left strip", (-desk_width / 2 + 1.0, SURFACE_Y + 0.28, 0), (0.8, 0.35, desk_depth - 4.0), warm_light_mat)
        builder.add_box("rgb back strip", (0, SURFACE_Y + 0.28, back_z + 1.0), (desk_width - 4.0, 0.35, 0.8), warm_light_mat)

    builder.export(output_path)

    monitor_dim = _MONITOR_SIZES_CM.get(monitor_size, _MONITOR_SIZES_CM["27"])
    return {
        **keyboard_meta,
        "desk_width": desk_width,
        "desk_depth": desk_depth,
        "monitor_size_inch": monitor_size,
        "monitor_panel_cm": f"{monitor_dim[0]} x {monitor_dim[1]}",
        "dimension_unit": "cm",
        "scale_notes": [
            "1 GLB unit = 1 cm",
            "keyboard uses MX 1u spacing = 1.905 cm",
            f"monitor {monitor_size}-inch panel = {monitor_dim[0]} x {monitor_dim[1]} cm",
            "monitor arm uses VESA MIS-D 100 x 100 mm plate",
        ],
        "enabled_assets": sorted(enabled_assets),
        "asset_count": len(enabled_assets),
        "model_file": output_path.name,
    }

def build_uploaded_step_proxy_glb(
    *,
    output_path: Path,
    source_name: str,
    source_size: int,
    case_color: str = "#9ca3af",
) -> dict:
    size_hint = max(1.0, min(4.0, math.log(max(source_size, 1024), 1024)))
    builder = GlbBuilder()
    body_mat = builder.add_material("uploaded step proxy body", case_color, roughness=0.48, metallic=0.12)
    edge_mat = builder.add_material("uploaded step proxy edges", "#334155", roughness=0.5, metallic=0.0)
    note_mat = builder.add_material("conversion needed marker", "#f59e0b", roughness=0.38, metallic=0.0)

    builder.add_box("uploaded STEP bounding body", (0, 0.55, 0), (5.4 + size_hint, 0.82, 3.4 + size_hint / 2), body_mat, taper=0.08)
    builder.add_box("front bevel marker", (0, 1.04, 1.88 + size_hint / 4), (4.8 + size_hint, 0.12, 0.16), edge_mat, taper=0.03)
    builder.add_box("left reference edge", (-2.8 - size_hint / 2, 0.98, 0), (0.12, 0.16, 3.2 + size_hint / 2), edge_mat)
    builder.add_box("right reference edge", (2.8 + size_hint / 2, 0.98, 0), (0.12, 0.16, 3.2 + size_hint / 2), edge_mat)
    builder.add_box("STEP converter status marker", (0, 1.3, 0), (1.1, 0.12, 1.1), note_mat, taper=0.12)

    builder.export(output_path)
    return {
        "source_file": source_name,
        "source_size": source_size,
        "conversion": "proxy_glb",
        "message": "STEP converter CLI is not configured, so a proxy GLB was generated.",
        "model_file": output_path.name,
    }
