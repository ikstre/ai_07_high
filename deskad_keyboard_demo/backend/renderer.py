import base64
import json
import math
import struct
from pathlib import Path


def hex_to_rgba(value: str, alpha: float = 1.0) -> list[float]:
    value = value.strip().lstrip("#")
    if len(value) == 8:
        a = int(value[6:8], 16) / 255
        value = value[:6]
    else:
        a = alpha
    if len(value) != 6:
        value = "cccccc"
    r = int(value[0:2], 16) / 255
    g = int(value[2:4], 16) / 255
    b = int(value[4:6], 16) / 255
    return [r, g, b, a]


class GlbBuilder:
    def __init__(self):
        self.positions: list[float] = []
        self.normals: list[float] = []
        self.indices: list[int] = []
        self.meshes: list[dict] = []
        self.nodes: list[dict] = []
        self.materials: list[dict] = []
        self._index_ranges: list[tuple[int, int, int]] = []

    def add_material(
        self,
        name: str,
        color: str,
        roughness: float = 0.55,
        metallic: float = 0.0,
        alpha: float = 1.0,
        alpha_mode: str = "OPAQUE",
        emissive: str | None = None,
        emissive_strength: float = 1.0,
    ) -> int:
        material_index = len(self.materials)
        pbr = {
            "baseColorFactor": hex_to_rgba(color, alpha),
            "roughnessFactor": roughness,
            "metallicFactor": metallic,
        }
        material: dict = {
            "name": name,
            "pbrMetallicRoughness": pbr,
            "doubleSided": False,
        }
        if alpha_mode != "OPAQUE":
            material["alphaMode"] = alpha_mode
            if alpha_mode == "MASK":
                material["alphaCutoff"] = 0.5
        if emissive:
            em_rgba = hex_to_rgba(emissive)
            material["emissiveFactor"] = [em_rgba[0], em_rgba[1], em_rgba[2]]
            if emissive_strength != 1.0:
                material["extensions"] = {
                    "KHR_materials_emissive_strength": {"emissiveStrength": emissive_strength}
                }
        self.materials.append(material)
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
        segments: int = 32,
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
        segments: int = 32,
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

    def add_torus_y(
        self,
        name: str,
        center: tuple[float, float, float],
        major_radius: float,
        minor_radius: float,
        material: int,
        major_segments: int = 24,
        minor_segments: int = 12,
    ) -> None:
        cx, cy, cz = center
        start_vertex = len(self.positions) // 3
        start_index = len(self.indices)
        rings = []
        for i in range(major_segments + 1):
            u = 2 * math.pi * i / major_segments
            cu, su = math.cos(u), math.sin(u)
            ring = []
            for j in range(minor_segments + 1):
                v = 2 * math.pi * j / minor_segments
                cv, sv = math.cos(v), math.sin(v)
                x = (major_radius + minor_radius * cv) * cu
                z = (major_radius + minor_radius * cv) * su
                y = minor_radius * sv
                nx = cv * cu
                nz = cv * su
                ny = sv
                ring.append((cx + x, cy + y, cz + z, nx, ny, nz))
            rings.append(ring)
        for i in range(major_segments):
            for j in range(minor_segments):
                v0 = rings[i][j]
                v1 = rings[i + 1][j]
                v2 = rings[i + 1][j + 1]
                v3 = rings[i][j + 1]
                for x, y, z, nx, ny, nz in (v0, v1, v2, v3):
                    self.positions.extend([x, y, z])
                    self.normals.extend([nx, ny, nz])
                base = start_vertex + (i * minor_segments + j) * 4
                self.indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
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

    def add_sphere(
        self,
        name: str,
        center: tuple[float, float, float],
        radius: float,
        material: int,
        rings: int = 16,
        segments: int = 24,
        radius_y: float | None = None,
        radius_z: float | None = None,
    ) -> None:
        radius_y = radius if radius_y is None else radius_y
        radius_z = radius if radius_z is None else radius_z
        cx, cy, cz = center
        start_vertex = len(self.positions) // 3
        start_index = len(self.indices)
        grid = []
        for i in range(rings + 1):
            phi = math.pi * i / rings - math.pi / 2
            cp, sp = math.cos(phi), math.sin(phi)
            row = []
            for j in range(segments + 1):
                theta = 2 * math.pi * j / segments
                ct, st = math.cos(theta), math.sin(theta)
                x = radius * cp * ct
                y = radius_y * sp
                z = radius_z * cp * st
                nx = cp * ct
                ny = sp
                nz = cp * st
                row.append((cx + x, cy + y, cz + z, nx, ny, nz))
            grid.append(row)
        for i in range(rings):
            for j in range(segments):
                v0 = grid[i][j]
                v1 = grid[i + 1][j]
                v2 = grid[i + 1][j + 1]
                v3 = grid[i][j + 1]
                for x, y, z, nx, ny, nz in (v0, v1, v2, v3):
                    self.positions.extend([x, y, z])
                    self.normals.extend([nx, ny, nz])
                base = start_vertex + (i * segments + j) * 4
                self.indices.extend([base, base + 1, base + 2, base, base + 2, base + 3])
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

        extensions_used = []
        for material in self.materials:
            if "extensions" in material and "KHR_materials_emissive_strength" in material["extensions"]:
                if "KHR_materials_emissive_strength" not in extensions_used:
                    extensions_used.append("KHR_materials_emissive_strength")

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
        if extensions_used:
            gltf["extensionsUsed"] = extensions_used

        json_blob = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
        json_blob += b" " * ((4 - len(json_blob) % 4) % 4)

        total_length = 12 + 8 + len(json_blob) + 8 + len(binary_blob)
        with output_path.open("wb") as file:
            file.write(struct.pack("<4sII", b"glTF", 2, total_length))
            file.write(struct.pack("<I4s", len(json_blob), b"JSON"))
            file.write(json_blob)
            file.write(struct.pack("<I4s", len(binary_blob), b"BIN\x00"))
            file.write(binary_blob)


# Desk setup renderer scale: 1 GLB unit = 1 centimeter.
# Keyboard layout JSON is in MX key units. Standard MX spacing is 19.05 mm.
U_CM = 1.905
TABLE_TOP_THICKNESS_CM = 2.5
SURFACE_Y = 0.0


def _layout_size_cm(layout_data: dict) -> tuple[float, float]:
    return float(layout_data["width"]) * U_CM, float(layout_data["height"]) * U_CM


def _surface_center_y(height_cm: float) -> float:
    return SURFACE_Y + height_cm / 2


# --- Keyboard internal structure (case / plate / pcb / switches / keycaps) ---

PLATE_MATERIAL_COLORS = {
    "aluminum": ("#b8bcc4", 0.32, 0.85),
    "brass": ("#c9a36a", 0.35, 0.80),
    "pom": ("#ece6d8", 0.55, 0.0),
    "fr4": ("#3b4d2a", 0.65, 0.0),
    "carbon": ("#2a2d33", 0.42, 0.20),
    "polycarbonate": ("#dde2eb", 0.45, 0.0),
}

PCB_MATERIAL_COLORS = {
    "black": ("#1d2230", 0.65, 0.0),
    "red": ("#7a1f23", 0.65, 0.0),
    "blue": ("#1d3a6e", 0.65, 0.0),
    "green": ("#1e4d2b", 0.65, 0.0),
    "white": ("#e8e9eb", 0.62, 0.0),
}

SWITCH_STEM_COLORS = {
    "red": "#c83b3b",
    "yellow": "#e7c75a",
    "brown": "#8a6644",
    "blue": "#3766c4",
    "clear": "#dfe2e7",
    "silent_red": "#a83838",
    "tactile_purple": "#7a4dc0",
    "linear_black": "#2a2d33",
}

CASE_FINISH_PRESETS = {
    "anodized": (0.35, 0.45),
    "matte": (0.78, 0.05),
    "polycarbonate": (0.42, 0.0),
    "wood": (0.7, 0.0),
}

KEYCAP_PROFILE_PRESETS = {
    "cherry": {"height": 0.85, "gap": 0.18, "top_inset": 0.16, "top_taper": 0.26, "row_angles": {1: -2, 2: 1, 3: 4, 4: 7}},
    "oem": {"height": 1.00, "gap": 0.18, "top_inset": 0.18, "top_taper": 0.30, "row_angles": {1: -4, 2: 0, 3: 5, 4: 9}},
    "xda": {"height": 0.72, "gap": 0.16, "top_inset": 0.10, "top_taper": 0.20, "row_angles": {1: 0, 2: 0, 3: 0, 4: 0}},
    "sa": {"height": 1.22, "gap": 0.20, "top_inset": 0.24, "top_taper": 0.36, "row_angles": {1: -7, 2: -2, 3: 6, 4: 12}},
    "mda": {"height": 0.95, "gap": 0.17, "top_inset": 0.15, "top_taper": 0.28, "row_angles": {1: -3, 2: 0, 3: 3, 4: 6}},
}

SWITCH_FAMILY_PRESETS = {
    "mx": {"housing": "#26282d", "top": "#3a3c42", "detail": "#5a616b", "housing_w": 1.40, "housing_d": 1.40, "stem": (0.65, 0.42, 0.65)},
    "box": {"housing": "#f0f2f4", "top": "#d9dee4", "detail": "#7b8794", "housing_w": 1.48, "housing_d": 1.48, "stem": (0.58, 0.42, 0.58)},
    "holy_panda": {"housing": "#f2e5c7", "top": "#e7d6aa", "detail": "#a46bb8", "housing_w": 1.42, "housing_d": 1.42, "stem": (0.68, 0.44, 0.68), "stem_color": "#7a4dc0"},
    "topre": {"housing": "#2d3138", "top": "#4b5059", "detail": "#d8dce2", "housing_w": 1.46, "housing_d": 1.46, "stem": (0.72, 0.34, 0.72), "stem_color": "#e8e9eb"},
}


def _profile_row_angle(profile: dict, row: int) -> float:
    return math.radians(profile.get("row_angles", {}).get(row, 0))


def _mix_hex_color(value: str, target: str, amount: float) -> str:
    def parse(color: str) -> tuple[int, int, int]:
        color = color.strip().lstrip("#")[:6]
        if len(color) != 6:
            color = "cccccc"
        return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    amount = max(0.0, min(1.0, amount))
    sr, sg, sb = parse(value)
    tr, tg, tb = parse(target)
    return f"#{round(sr + (tr - sr) * amount):02x}{round(sg + (tg - sg) * amount):02x}{round(sb + (tb - sb) * amount):02x}"


def _add_contact_shadow(
    builder: GlbBuilder,
    *,
    name: str,
    center: tuple[float, float],
    size: tuple[float, float],
    material: int,
    y: float = SURFACE_Y + 0.045,
) -> None:
    x, z = center
    builder.add_box(name, (x, y, z), (size[0], 0.035, size[1]), material, taper=0.9)


def _add_desk_surface_details(
    builder: GlbBuilder,
    *,
    desk_width: float,
    desk_depth: float,
    grain_mat: int,
    edge_mat: int,
    grommet_mat: int,
) -> None:
    front_z = desk_depth / 2
    back_z = -desk_depth / 2
    for index, fraction in enumerate((0.13, 0.25, 0.39, 0.55, 0.71, 0.86)):
        z = back_z + desk_depth * fraction
        builder.add_box(
            f"subtle wood grain line {index + 1}",
            (0, SURFACE_Y + 0.045, z),
            (desk_width - 8.0, 0.025, 0.07),
            grain_mat,
            taper=0.02,
        )
    for index, x in enumerate((-desk_width * 0.28, -desk_width * 0.08, desk_width * 0.16, desk_width * 0.34)):
        builder.add_box(
            f"short wood pore {index + 1}",
            (x, SURFACE_Y + 0.05, back_z + 12.0 + index * 7.0),
            (18.0 + index * 3.0, 0.025, 0.06),
            grain_mat,
            taper=0.02,
        )
    for index, (x, z) in enumerate(
        (
            (-desk_width / 2 + 9.0, back_z + 8.0),
            (desk_width / 2 - 9.0, back_z + 8.0),
            (-desk_width / 2 + 9.0, front_z - 8.0),
            (desk_width / 2 - 9.0, front_z - 8.0),
        )
    ):
        builder.add_box(
            f"desk square leg {index + 1}",
            (x, -TABLE_TOP_THICKNESS_CM - 10.0, z),
            (4.0, 20.0, 4.0),
            edge_mat,
            taper=0.15,
        )
    builder.add_cylinder_y(
        "desk cable grommet",
        (desk_width / 2 - 17.0, SURFACE_Y + 0.08, back_z + 11.0),
        3.4,
        0.14,
        grommet_mat,
        radius_z=3.4,
        segments=32,
    )


def _add_deskmat_details(
    builder: GlbBuilder,
    *,
    center_z: float,
    width: float,
    depth: float,
    stitch_mat: int,
) -> None:
    y = SURFACE_Y + 0.42
    builder.add_box("deskmat stitched front edge", (0, y, center_z + depth / 2 - 0.55), (width - 1.8, 0.05, 0.18), stitch_mat, taper=0.05)
    builder.add_box("deskmat stitched back edge", (0, y, center_z - depth / 2 + 0.55), (width - 1.8, 0.05, 0.18), stitch_mat, taper=0.05)
    builder.add_box("deskmat stitched left edge", (-width / 2 + 0.55, y, center_z), (0.18, 0.05, depth - 1.8), stitch_mat, taper=0.05)
    builder.add_box("deskmat stitched right edge", (width / 2 - 0.55, y, center_z), (0.18, 0.05, depth - 1.8), stitch_mat, taper=0.05)
    for index, offset in enumerate((-0.28, -0.12, 0.08, 0.24)):
        builder.add_box(
            f"deskmat weave thread {index + 1}",
            (0, y + 0.012, center_z + depth * offset),
            (width - 8.0, 0.025, 0.045),
            stitch_mat,
            taper=0.02,
        )


def _add_keyboard_detailed(
    builder: GlbBuilder,
    *,
    layout_data: dict,
    center: tuple[float, float],
    case_color: str,
    keycap_color: str,
    accent_color: str,
    case_finish: str = "anodized",
    plate_material: str = "aluminum",
    pcb_color: str = "black",
    switch_stem: str = "red",
    switch_family: str = "mx",
    keycap_profile: str = "cherry",
    mount_type: str = "top_mount",
    show_internals: bool = True,
    accent_keys: set[int] | None = None,
) -> dict:
    keys = layout_data["layouts"]["LAYOUT"]["layout"]
    board_width_u = float(layout_data["width"])
    board_depth_u = float(layout_data["height"])
    board_width_cm, board_depth_cm = _layout_size_cm(layout_data)
    case_margin_cm = 1.6
    case_outer_w = board_width_cm + case_margin_cm * 2
    case_outer_d = board_depth_cm + case_margin_cm * 2
    case_outer_h = 2.4
    case_bottom_h = 1.1
    plate_h = 0.20
    pcb_h = 0.16
    profile = KEYCAP_PROFILE_PRESETS.get(keycap_profile, KEYCAP_PROFILE_PRESETS["cherry"])
    switch_family_params = SWITCH_FAMILY_PRESETS.get(switch_family, SWITCH_FAMILY_PRESETS["mx"])
    switch_housing_h = 1.12 if switch_family == "topre" else 1.20
    key_height_cm = float(profile["height"])
    key_gap_cm = float(profile["gap"])
    key_top_inset_cm = float(profile["top_inset"])
    key_top_taper = float(profile["top_taper"])
    center_x, center_z = center

    case_finish_params = CASE_FINISH_PRESETS.get(case_finish, CASE_FINISH_PRESETS["anodized"])
    case_top_mat = builder.add_material(
        "keyboard case top",
        case_color,
        roughness=case_finish_params[0],
        metallic=case_finish_params[1],
    )
    case_bottom_mat = builder.add_material(
        "keyboard case bottom",
        case_color,
        roughness=min(0.85, case_finish_params[0] + 0.1),
        metallic=case_finish_params[1] * 0.6,
    )
    case_inner_mat = builder.add_material("keyboard case inner", "#1a1d22", roughness=0.6, metallic=0.0)

    plate_color, plate_rough, plate_metal = PLATE_MATERIAL_COLORS.get(plate_material, PLATE_MATERIAL_COLORS["aluminum"])
    plate_mat = builder.add_material(f"plate {plate_material}", plate_color, roughness=plate_rough, metallic=plate_metal)

    pcb_color_hex, pcb_rough, pcb_metal = PCB_MATERIAL_COLORS.get(pcb_color, PCB_MATERIAL_COLORS["black"])
    pcb_mat = builder.add_material(f"pcb {pcb_color}", pcb_color_hex, roughness=pcb_rough, metallic=pcb_metal)
    pcb_trace_mat = builder.add_material("pcb traces", "#d4af37", roughness=0.45, metallic=0.55)

    switch_housing_mat = builder.add_material(
        f"{switch_family} switch housing",
        switch_family_params["housing"],
        roughness=0.55,
        metallic=0.0,
    )
    switch_top_mat = builder.add_material(
        f"{switch_family} switch top housing",
        switch_family_params["top"],
        roughness=0.55,
        metallic=0.0,
    )
    stem_color = switch_family_params.get("stem_color") or SWITCH_STEM_COLORS.get(switch_stem, SWITCH_STEM_COLORS["red"])
    stem_mat = builder.add_material(f"{switch_family} switch stem {switch_stem}", stem_color, roughness=0.55, metallic=0.0)
    switch_detail_mat = builder.add_material(f"{switch_family} switch detail", switch_family_params["detail"], roughness=0.58, metallic=0.04)

    keycap_mat = builder.add_material("keycaps", keycap_color, roughness=0.72, metallic=0.0)
    accent_mat = builder.add_material("accent keycaps", accent_color, roughness=0.68, metallic=0.0)
    keycap_side_mat = builder.add_material("keycap side shade", _mix_hex_color(keycap_color, "#111827", 0.10), roughness=0.78, metallic=0.0)
    accent_side_mat = builder.add_material("accent keycap side shade", _mix_hex_color(accent_color, "#111827", 0.10), roughness=0.74, metallic=0.0)
    keycap_top_highlight_mat = builder.add_material("keycap satin highlight", _mix_hex_color(keycap_color, "#ffffff", 0.12), roughness=0.82, metallic=0.0)
    accent_top_highlight_mat = builder.add_material("accent keycap satin highlight", _mix_hex_color(accent_color, "#ffffff", 0.10), roughness=0.78, metallic=0.0)
    legend_mat = builder.add_material("keycap legends", "#1b1d22", roughness=0.8, metallic=0.0)
    case_edge_mat = builder.add_material("case bevel shadow", _mix_hex_color(case_color, "#111827", 0.18), roughness=min(0.9, case_finish_params[0] + 0.08), metallic=case_finish_params[1] * 0.55)
    case_highlight_mat = builder.add_material("case soft edge highlight", _mix_hex_color(case_color, "#ffffff", 0.10), roughness=case_finish_params[0], metallic=case_finish_params[1])
    plate_cutout_mat = builder.add_material("plate cutout shadow", "#111318", roughness=0.75, metallic=0.0)
    screw_mat = builder.add_material("case screw recess", "#20242b", roughness=0.55, metallic=0.2)
    mount_mat = builder.add_material("keyboard mount cue", "#d9e3ea", roughness=0.74, metallic=0.0, alpha=0.72, alpha_mode="BLEND")
    mount_dark_mat = builder.add_material("keyboard mount shadow", "#1f232a", roughness=0.68, metallic=0.0)

    case_y_center = SURFACE_Y + case_outer_h / 2
    builder.add_box(
        "case bottom shell",
        (center_x, SURFACE_Y + case_bottom_h / 2, center_z),
        (case_outer_w, case_bottom_h, case_outer_d),
        case_bottom_mat,
        taper=0.35,
    )
    builder.add_box(
        "case top frame",
        (center_x, SURFACE_Y + case_bottom_h + (case_outer_h - case_bottom_h) / 2, center_z),
        (case_outer_w, case_outer_h - case_bottom_h, case_outer_d),
        case_top_mat,
        taper=0.20,
    )
    builder.add_box(
        "case top inner cavity",
        (center_x, SURFACE_Y + case_outer_h - 0.18, center_z),
        (board_width_cm + 0.5, 0.04, board_depth_cm + 0.5),
        case_inner_mat,
        taper=0.04,
    )
    builder.add_box("case front chamfer highlight", (center_x, SURFACE_Y + case_outer_h + 0.03, center_z + case_outer_d / 2 - 0.55), (case_outer_w - 1.2, 0.08, 0.25), case_highlight_mat, taper=0.05)
    builder.add_box("case rear bevel shadow", (center_x, SURFACE_Y + case_outer_h + 0.02, center_z - case_outer_d / 2 + 0.55), (case_outer_w - 1.2, 0.08, 0.25), case_edge_mat, taper=0.05)
    builder.add_box("case left side seam", (center_x - case_outer_w / 2 + 0.42, SURFACE_Y + case_bottom_h + 0.20, center_z), (0.16, 0.18, case_outer_d - 1.0), case_edge_mat, taper=0.03)
    builder.add_box("case right side seam", (center_x + case_outer_w / 2 - 0.42, SURFACE_Y + case_bottom_h + 0.20, center_z), (0.16, 0.18, case_outer_d - 1.0), case_edge_mat, taper=0.03)
    builder.add_box("usb c rear cutout", (center_x, SURFACE_Y + case_bottom_h + 0.45, center_z - case_outer_d / 2 - 0.02), (2.8, 0.50, 0.16), case_inner_mat, taper=0.08)
    for screw_index, (dx, dz) in enumerate(
        (
            (-case_outer_w / 2 + 2.4, -case_outer_d / 2 + 1.8),
            (case_outer_w / 2 - 2.4, -case_outer_d / 2 + 1.8),
            (-case_outer_w / 2 + 2.4, case_outer_d / 2 - 1.8),
            (case_outer_w / 2 - 2.4, case_outer_d / 2 - 1.8),
        )
    ):
        builder.add_cylinder_y(
            f"case screw recess {screw_index + 1}",
            (center_x + dx, SURFACE_Y + case_outer_h + 0.055, center_z + dz),
            0.35,
            0.05,
            screw_mat,
            radius_z=0.35,
            segments=18,
        )
    if case_finish == "wood":
        for grain_index, dz in enumerate((-case_outer_d * 0.22, 0.0, case_outer_d * 0.23)):
            builder.add_box(
                f"keyboard case wood grain {grain_index + 1}",
                (center_x, SURFACE_Y + case_outer_h + 0.07, center_z + dz),
                (case_outer_w - 3.0, 0.025, 0.06),
                case_edge_mat,
                taper=0.02,
            )

    if mount_type == "gasket_mount":
        for side_index, dz in enumerate((-board_depth_cm / 2 - 0.38, board_depth_cm / 2 + 0.38)):
            builder.add_box(
                f"gasket isolation strip {side_index + 1}",
                (center_x, SURFACE_Y + case_outer_h + 0.10, center_z + dz),
                (board_width_cm + 0.8, 0.12, 0.20),
                mount_mat,
                taper=0.04,
            )
        for side_index, dx in enumerate((-board_width_cm / 2 - 0.38, board_width_cm / 2 + 0.38)):
            builder.add_box(
                f"gasket side strip {side_index + 1}",
                (center_x + dx, SURFACE_Y + case_outer_h + 0.10, center_z),
                (0.20, 0.12, board_depth_cm + 0.8),
                mount_mat,
                taper=0.04,
            )
    elif mount_type == "tray_mount":
        for standoff_index, (dx, dz) in enumerate(((-board_width_cm / 3, -board_depth_cm / 4), (0.0, 0.0), (board_width_cm / 3, board_depth_cm / 4))):
            builder.add_cylinder_y(
                f"tray mount standoff {standoff_index + 1}",
                (center_x + dx, SURFACE_Y + case_bottom_h + 0.48, center_z + dz),
                0.36,
                0.56,
                mount_dark_mat,
                radius_z=0.36,
                segments=18,
            )
    elif mount_type == "o_ring_mount":
        ring_y = SURFACE_Y + case_outer_h + 0.12
        builder.add_box("o-ring front rail", (center_x, ring_y, center_z + board_depth_cm / 2 + 0.36), (board_width_cm + 0.8, 0.13, 0.16), mount_mat, taper=0.04)
        builder.add_box("o-ring rear rail", (center_x, ring_y, center_z - board_depth_cm / 2 - 0.36), (board_width_cm + 0.8, 0.13, 0.16), mount_mat, taper=0.04)
        builder.add_box("o-ring left rail", (center_x - board_width_cm / 2 - 0.36, ring_y, center_z), (0.16, 0.13, board_depth_cm + 0.8), mount_mat, taper=0.04)
        builder.add_box("o-ring right rail", (center_x + board_width_cm / 2 + 0.36, ring_y, center_z), (0.16, 0.13, board_depth_cm + 0.8), mount_mat, taper=0.04)
    else:
        for tab_index, dx in enumerate((-board_width_cm / 2 + 2.8, board_width_cm / 2 - 2.8)):
            builder.add_box(
                f"top mount tab {tab_index + 1}",
                (center_x + dx, SURFACE_Y + case_outer_h + 0.10, center_z - board_depth_cm / 2 - 0.15),
                (2.4, 0.10, 0.44),
                mount_dark_mat,
                taper=0.06,
            )

    plate_y: float | None = None
    if not show_internals:
        builder.add_box(
            "plate rim visible between keycaps",
            (center_x, SURFACE_Y + case_outer_h - 0.04, center_z),
            (board_width_cm + 0.35, 0.08, board_depth_cm + 0.35),
            plate_mat,
            taper=0.04,
        )

    if show_internals:
        pcb_y = SURFACE_Y + case_bottom_h + 0.12 + pcb_h / 2
        builder.add_box(
            "pcb board",
            (center_x, pcb_y, center_z),
            (board_width_cm + 0.6, pcb_h, board_depth_cm + 0.6),
            pcb_mat,
            taper=0.04,
        )
        for dx in (-board_width_cm / 3, 0.0, board_width_cm / 3):
            builder.add_box(
                "pcb trace",
                (center_x + dx, pcb_y + pcb_h / 2 + 0.005, center_z),
                (board_width_cm * 0.5, 0.008, 0.15),
                pcb_trace_mat,
            )

        plate_y = pcb_y + pcb_h / 2 + plate_h / 2 + 0.18
        builder.add_box(
            "plate",
            (center_x, plate_y, center_z),
            (board_width_cm + 0.4, plate_h, board_depth_cm + 0.4),
            plate_mat,
            taper=0.04,
        )

    switch_base_y = SURFACE_Y + case_outer_h - 0.05
    stem_y = switch_base_y + switch_housing_h
    accent_idx = accent_keys if accent_keys is not None else {0, 13, 14, 42, 56, 65, 66}

    for index, key in enumerate(keys):
        key_w_u = float(key.get("w", 1))
        key_h_u = float(key.get("h", 1))
        x = (float(key["x"]) - board_width_u / 2 + key_w_u / 2) * U_CM + center_x
        z = (float(key["y"]) - board_depth_u / 2 + key_h_u / 2) * U_CM + center_z
        row = int(min(4, max(1, key["y"] + 1)))
        angle = _profile_row_angle(profile, row)

        if show_internals:
            builder.add_box(
                f"switch housing {index + 1}",
                (x, switch_base_y + switch_housing_h / 2, z),
                (float(switch_family_params["housing_w"]), switch_housing_h, float(switch_family_params["housing_d"])),
                switch_housing_mat,
                taper=0.18,
            )
            builder.add_box(
                f"switch top {index + 1}",
                (x, switch_base_y + switch_housing_h - 0.18, z),
                (max(0.95, float(switch_family_params["housing_w"]) - 0.10), 0.35, max(0.95, float(switch_family_params["housing_d"]) - 0.10)),
                switch_top_mat,
                taper=0.18,
            )
            builder.add_box(
                f"switch stem {index + 1}",
                (x, switch_base_y + switch_housing_h + 0.18, z),
                switch_family_params["stem"],
                stem_mat,
                taper=0.10,
            )
            if switch_family == "box":
                builder.add_box(
                    f"box switch collar {index + 1}",
                    (x, switch_base_y + switch_housing_h + 0.04, z),
                    (0.95, 0.12, 0.95),
                    switch_detail_mat,
                    taper=0.08,
                )
            elif switch_family == "holy_panda":
                builder.add_box(
                    f"tactile leaf glint {index + 1}",
                    (x + 0.48, switch_base_y + switch_housing_h * 0.58, z),
                    (0.08, 0.50, 0.55),
                    switch_detail_mat,
                    taper=0.03,
                )
            elif switch_family == "topre":
                builder.add_cylinder_y(
                    f"topre rubber dome {index + 1}",
                    (x, switch_base_y + 0.42, z),
                    0.92,
                    0.34,
                    switch_detail_mat,
                    radius_z=0.92,
                    top_radius_x=0.58,
                    top_radius_z=0.58,
                    segments=18,
                )

        is_accent = index in accent_idx or key_w_u >= 2.0
        material = accent_mat if is_accent else keycap_mat
        side_material = accent_side_mat if is_accent else keycap_side_mat
        highlight_material = accent_top_highlight_mat if is_accent else keycap_top_highlight_mat
        keycap_y = stem_y + key_height_cm / 2
        keycap_w = max(0.8, key_w_u * U_CM - key_gap_cm)
        keycap_d = max(0.8, key_h_u * U_CM - key_gap_cm)
        if show_internals and plate_y is not None:
            builder.add_box(
                f"plate switch cutout shadow {index + 1}",
                (x, plate_y + plate_h / 2 + 0.012, z),
                (min(1.52, keycap_w - 0.15), 0.025, min(1.52, keycap_d - 0.15)),
                plate_cutout_mat,
                taper=0.05,
            )
        builder.add_box(
            f"keycap skirt {index + 1}",
            (x, keycap_y - 0.10, z),
            (keycap_w, key_height_cm * 0.70, keycap_d),
            side_material,
            taper=0.18,
            rotation_x=angle,
        )
        builder.add_box(
            f"keycap satin top {index + 1}",
            (x, keycap_y + 0.18, z),
            (max(0.55, keycap_w - key_top_inset_cm), key_height_cm * 0.42, max(0.55, keycap_d - key_top_inset_cm)),
            material,
            taper=key_top_taper,
            rotation_x=angle,
        )
        builder.add_box(
            f"keycap top highlight {index + 1}",
            (x - keycap_w * 0.12, keycap_y + key_height_cm / 2 + 0.012, z - keycap_d * 0.10),
            (max(0.45, keycap_w * 0.54), 0.014, max(0.32, keycap_d * 0.22)),
            highlight_material,
            taper=0.12,
            rotation_x=angle,
        )

        if row in (2, 3) and key_w_u < 1.6:
            builder.add_box(
                f"keycap legend {index + 1}",
                (x, keycap_y + key_height_cm / 2 + 0.005, z + 0.1),
                (keycap_w * 0.45, 0.005, 0.18),
                legend_mat,
                rotation_x=angle,
            )

    keyboard_height_total = case_outer_h + switch_housing_h + key_height_cm
    return {
        "key_count": len(keys),
        "board_width": round(board_width_cm, 1),
        "board_depth": round(board_depth_cm, 1),
        "case_outer_width": round(case_outer_w, 1),
        "case_outer_depth": round(case_outer_d, 1),
        "keyboard_total_height": round(keyboard_height_total, 2),
        "case_finish": case_finish,
        "plate_material": plate_material,
        "pcb_color": pcb_color,
        "switch_stem": switch_stem,
        "switch_family": switch_family,
        "keycap_profile": keycap_profile,
        "mount_type": mount_type,
        "show_internals": show_internals,
        "keyboard_unit": "cm",
        "keyboard_source": "MX 1u spacing 19.05mm",
    }


# --- Accessory builders ---


def _add_mouse(builder: GlbBuilder, *, center: tuple[float, float], mouse_mat: int, detail_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_sphere(
        "mouse body",
        (x, SURFACE_Y + 1.9, z),
        3.2,
        mouse_mat,
        rings=14,
        segments=20,
        radius_y=2.0,
        radius_z=5.9,
    )
    builder.add_box("mouse left button", (x - 1.25, SURFACE_Y + 3.55, z - 2.1), (2.2, 0.32, 4.0), detail_mat, taper=0.22)
    builder.add_box("mouse right button", (x + 1.25, SURFACE_Y + 3.55, z - 2.1), (2.2, 0.32, 4.0), detail_mat, taper=0.22)
    builder.add_cylinder_z("mouse wheel", (x, SURFACE_Y + 3.65, z - 3.0), 0.45, 0.45, 0.85, accent_mat, segments=18)


_MONITOR_SIZES_CM: dict[str, tuple[float, float]] = {
    "24": (56.0, 33.0),
    "27": (62.0, 36.0),
    "32": (74.0, 43.0),
}


def _add_monitor(
    builder: GlbBuilder,
    *,
    center_x: float,
    center_z: float,
    body_mat: int,
    screen_mat: int,
    bezel_mat: int,
    stand_mat: int,
    with_stand: bool = True,
    monitor_size: str = "27",
) -> dict:
    screen_w, screen_h = _MONITOR_SIZES_CM.get(monitor_size, _MONITOR_SIZES_CM["27"])
    screen_thickness = 2.8
    screen_center_y = SURFACE_Y + 34.0
    screen_center_z = center_z - 2.0
    screen_back_z = screen_center_z - screen_thickness / 2 - 0.35
    screen_front_z = screen_center_z + screen_thickness / 2 + 0.10
    screen_glare_mat = builder.add_material("monitor glass reflection", "#ffffff", roughness=0.18, metallic=0.0, alpha=0.22, alpha_mode="BLEND")
    screen_ui_mat = builder.add_material("monitor desktop detail", "#6f86b8", roughness=0.45, metallic=0.0, emissive="#34496f", emissive_strength=0.8)

    if with_stand:
        builder.add_box("monitor base", (center_x, _surface_center_y(1.4), screen_center_z + 9.0), (26.0, 1.4, 19.0), stand_mat, taper=0.6)
        builder.add_box("monitor neck", (center_x, SURFACE_Y + 13.0, screen_back_z), (3.2, 24.0, 2.8), stand_mat, taper=0.2)
        builder.add_box("monitor hinge", (center_x, SURFACE_Y + 25.0, screen_back_z + 0.6), (12.0, 3.4, 3.0), stand_mat, taper=0.18)

    # Back chassis: slightly tapered, darker.
    builder.add_box(
        "monitor back chassis",
        (center_x, screen_center_y, screen_center_z - 0.3),
        (screen_w, screen_h, screen_thickness * 0.75),
        body_mat,
        taper=0.5,
    )
    # Front bezel frame.
    builder.add_box(
        "monitor front bezel",
        (center_x, screen_center_y, screen_center_z + screen_thickness / 2 - 0.05),
        (screen_w, screen_h, 0.4),
        bezel_mat,
        taper=0.05,
    )
    # Display panel (slightly recessed and emissive for glow).
    builder.add_box(
        "monitor display",
        (center_x, screen_center_y, screen_center_z + screen_thickness / 2 + 0.04),
        (max(1.0, screen_w - 2.6), max(1.0, screen_h - 2.8), 0.10),
        screen_mat,
        taper=0.08,
    )
    builder.add_box(
        "monitor desktop window band",
        (center_x - screen_w * 0.12, screen_center_y + screen_h * 0.12, screen_front_z),
        (screen_w * 0.42, screen_h * 0.07, 0.05),
        screen_ui_mat,
        taper=0.02,
    )
    builder.add_box(
        "monitor desktop lower panel",
        (center_x + screen_w * 0.10, screen_center_y - screen_h * 0.18, screen_front_z),
        (screen_w * 0.52, screen_h * 0.10, 0.05),
        screen_ui_mat,
        taper=0.02,
    )
    builder.add_box(
        "monitor diagonal reflection",
        (center_x + screen_w * 0.18, screen_center_y + screen_h * 0.05, screen_front_z + 0.02),
        (screen_w * 0.20, screen_h * 0.78, 0.035),
        screen_glare_mat,
        taper=0.12,
        rotation_x=math.radians(-8),
    )
    builder.add_cylinder_z("monitor webcam dot", (center_x, screen_center_y + screen_h / 2 - 1.1, screen_front_z + 0.03), 0.25, 0.25, 0.05, bezel_mat, segments=14)
    return {
        "panel_w": screen_w,
        "panel_h": screen_h,
        "screen_center_y": screen_center_y,
        "screen_center_z": screen_center_z,
    }


def _add_monitor_arm(
    builder: GlbBuilder,
    *,
    center_x: float,
    center_z: float,
    body_mat: int,
    accent_mat: int,
    back_z: float | None = None,
    style: str = "single",
) -> None:
    screen_center_z = center_z - 2.0
    screen_back_z = screen_center_z - 1.65
    raw_clamp_z = center_z - 16.0
    clamp_z = max(back_z + 3.5, raw_clamp_z) if back_z is not None else raw_clamp_z
    builder.add_box("vesa desk clamp", (center_x, _surface_center_y(6.0), clamp_z), (9.5, 6.0, 5.5), body_mat, taper=0.2)
    builder.add_box("vesa clamp screw", (center_x, _surface_center_y(2.0) - 3.5, clamp_z + 0.5), (1.8, 4.0, 1.8), accent_mat, taper=0.08)
    builder.add_cylinder_y(
        "monitor arm upright",
        (center_x, SURFACE_Y + 18.0, clamp_z),
        1.2,
        30.0,
        body_mat,
        segments=18,
    )
    if style == "double_joint":
        midpoint_z = (clamp_z + screen_back_z) / 2
        builder.add_box("arm upper boom", (center_x, SURFACE_Y + 32.0, (clamp_z + midpoint_z) / 2), (2.6, 2.0, abs(midpoint_z - clamp_z)), body_mat, taper=0.08)
        builder.add_cylinder_y("arm elbow joint", (center_x, SURFACE_Y + 32.0, midpoint_z), 1.5, 2.2, accent_mat, segments=18)
        builder.add_box("arm lower boom", (center_x, SURFACE_Y + 31.0, (midpoint_z + screen_back_z) / 2), (2.6, 2.0, abs(midpoint_z - screen_back_z)), body_mat, taper=0.08)
    else:
        builder.add_box("monitor arm boom", (center_x, SURFACE_Y + 31.0, (clamp_z + screen_back_z) / 2), (2.6, 2.0, abs(screen_back_z - clamp_z)), body_mat, taper=0.08)
    builder.add_box("vesa plate 100x100", (center_x, SURFACE_Y + 31.0, screen_back_z), (10.0, 10.0, 0.8), body_mat, taper=0.08)


def _add_desk_lamp(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, light_mat: int, arm_dir: float = 1.0) -> None:
    x, z = center
    arm_x = x + arm_dir * 9.0
    shade_x = x + arm_dir * 19.0
    builder.add_cylinder_y("lamp round base", (x, _surface_center_y(1.4), z), 7.0, 1.4, body_mat, radius_z=7.0, segments=28)
    builder.add_cylinder_y("lamp base highlight", (x, _surface_center_y(1.4) + 0.7, z), 7.05, 0.05, light_mat, radius_z=7.05, segments=28)
    builder.add_cylinder_y("lamp lower arm", (x, SURFACE_Y + 14.0, z), 0.85, 27.0, body_mat, radius_z=0.85, segments=18)
    builder.add_sphere("lamp lower joint", (x, SURFACE_Y + 27.0, z), 1.1, body_mat, rings=10, segments=18)
    builder.add_box("lamp upper arm", (arm_x, SURFACE_Y + 27.0, z - 4.0), (19.0, 1.4, 1.4), body_mat, taper=0.08)
    builder.add_sphere("lamp upper joint", (arm_x + arm_dir * 8.5, SURFACE_Y + 27.0, z - 4.0), 1.1, body_mat, rings=10, segments=18)
    builder.add_cylinder_y(
        "lamp tapered shade",
        (shade_x, SURFACE_Y + 24.0, z - 4.0),
        7.2,
        6.4,
        body_mat,
        radius_z=7.2,
        top_radius_x=4.0,
        top_radius_z=4.0,
        segments=28,
    )
    builder.add_cylinder_y("lamp warm light", (shade_x, SURFACE_Y + 20.6, z - 4.0), 4.6, 0.30, light_mat, radius_z=4.6, segments=28)


def _add_plant(builder: GlbBuilder, *, center: tuple[float, float], pot_mat: int, leaf_mat: int, soil_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("plant ceramic pot", (x, _surface_center_y(8.0), z), 5.0, 8.0, pot_mat, radius_z=5.0, top_radius_x=5.8, top_radius_z=5.8, segments=28)
    builder.add_cylinder_y("plant soil", (x, SURFACE_Y + 7.85, z), 5.5, 0.30, soil_mat, radius_z=5.5, segments=24)
    leaf_y = SURFACE_Y + 14.5
    builder.add_sphere("plant foliage", (x, leaf_y, z), 6.5, leaf_mat, rings=10, segments=18, radius_y=8.0)
    builder.add_sphere("plant foliage upper", (x + 1.4, leaf_y + 4.5, z - 0.5), 4.8, leaf_mat, rings=10, segments=18, radius_y=5.8)
    builder.add_sphere("plant foliage side", (x - 3.5, leaf_y + 1.0, z + 1.2), 3.6, leaf_mat, rings=8, segments=16, radius_y=4.4)


def _add_speakers(builder: GlbBuilder, *, left_x: float, right_x: float, z: float, body_mat: int, cone_mat: int, accent_mat: int) -> None:
    for label, x in (("left", left_x), ("right", right_x)):
        builder.add_box(f"{label} speaker cabinet", (x, _surface_center_y(18.0), z), (12.0, 18.0, 11.0), body_mat, taper=0.32)
        builder.add_box(f"{label} speaker baffle", (x, _surface_center_y(18.0), z + 5.45), (11.4, 17.5, 0.4), accent_mat, taper=0.28)
        builder.add_cylinder_z(f"{label} speaker tweeter", (x, SURFACE_Y + 13.5, z + 5.66), 1.6, 1.6, 0.32, cone_mat, segments=24)
        builder.add_cylinder_z(f"{label} speaker woofer", (x, SURFACE_Y + 6.8, z + 5.66), 3.4, 3.4, 0.32, cone_mat, segments=24)
        builder.add_cylinder_z(f"{label} woofer cone", (x, SURFACE_Y + 6.8, z + 5.81), 2.8, 2.8, 0.06, accent_mat, segments=24)


def _add_desk_shelf(builder: GlbBuilder, *, center: tuple[float, float], wood_mat: int, support_mat: int, width: float = 72.0) -> None:
    x, z = center
    builder.add_box("desk shelf top", (x, SURFACE_Y + 8.0, z), (width, 2.4, 22.0), wood_mat, taper=0.25)
    leg_offset = width / 2 - 5.0
    builder.add_box("desk shelf left leg", (x - leg_offset, SURFACE_Y + 4.0, z), (2.5, 8.0, 16.0), support_mat, taper=0.08)
    builder.add_box("desk shelf right leg", (x + leg_offset, SURFACE_Y + 4.0, z), (2.5, 8.0, 16.0), support_mat, taper=0.08)


def _add_notebook(builder: GlbBuilder, *, center: tuple[float, float], cover_mat: int, page_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_box("notebook cover", (x, SURFACE_Y + 0.55, z), (15.0, 0.55, 21.0), cover_mat, taper=0.2, rotation_x=math.radians(-2))
    builder.add_box("notebook pages", (x + 0.4, SURFACE_Y + 0.95, z + 0.2), (13.5, 0.45, 19.0), page_mat, taper=0.15, rotation_x=math.radians(-2))
    builder.add_box("notebook bookmark", (x + 4.0, SURFACE_Y + 1.0, z + 6.0), (0.8, 0.06, 3.5), accent_mat, taper=0.1)


def _add_headphone_stand(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, accent_mat: int, cushion_mat: int) -> None:
    x, z = center
    builder.add_box("headphone stand base", (x, _surface_center_y(1.4), z), (14.0, 1.4, 9.0), body_mat, taper=0.3)
    builder.add_cylinder_y("headphone stand pole", (x, SURFACE_Y + 13.0, z), 1.0, 25.0, body_mat, segments=18)
    builder.add_torus_y("headphone band top", (x, SURFACE_Y + 25.8, z), 8.5, 1.0, accent_mat, major_segments=24, minor_segments=12)
    builder.add_sphere("headphone earcup left", (x - 8.5, SURFACE_Y + 21.5, z), 3.8, cushion_mat, rings=12, segments=18, radius_y=3.6, radius_z=2.5)
    builder.add_sphere("headphone earcup right", (x + 8.5, SURFACE_Y + 21.5, z), 3.8, cushion_mat, rings=12, segments=18, radius_y=3.6, radius_z=2.5)


def _add_phone_stand(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, screen_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_box("phone stand base", (x, SURFACE_Y + 0.5, z), (8.5, 1.0, 9.0), body_mat, taper=0.18)
    builder.add_box("phone stand back plate", (x, SURFACE_Y + 7.0, z - 2.4), (7.4, 13.0, 1.1), body_mat, taper=0.14, rotation_x=math.radians(-12))
    builder.add_box("phone glass preview", (x, SURFACE_Y + 7.0, z - 1.6), (6.0, 11.0, 0.18), screen_mat, taper=0.12, rotation_x=math.radians(-12))
    builder.add_box("phone front camera", (x, SURFACE_Y + 12.6, z - 1.5), (0.6, 0.45, 0.04), accent_mat, rotation_x=math.radians(-12))
    builder.add_box("phone stand lip", (x, SURFACE_Y + 1.8, z + 1.7), (8.0, 1.2, 1.2), body_mat, taper=0.1)


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
        builder.add_box(f"display keycap {index + 1}", (x + dx, SURFACE_Y + 2.25, z + dz), (3.0, 1.0, 3.0), material, taper=0.28)


def _add_coffee_mug(builder: GlbBuilder, *, center: tuple[float, float], mug_mat: int, coffee_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("coffee mug body", (x, SURFACE_Y + 4.0, z), 4.0, 8.0, mug_mat, radius_z=4.0, top_radius_x=4.3, top_radius_z=4.3, segments=32)
    builder.add_cylinder_y("coffee surface", (x, SURFACE_Y + 8.12, z), 3.55, 0.16, coffee_mat, radius_z=3.55, segments=32)
    builder.add_torus_y("coffee mug handle", (x + 4.5, SURFACE_Y + 4.0, z), 2.4, 0.55, mug_mat, major_segments=20, minor_segments=10)


def _add_digital_clock(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, screen_mat: int) -> None:
    x, z = center
    builder.add_box("digital clock body", (x, SURFACE_Y + 3.2, z), (10.0, 6.4, 4.0), body_mat, taper=0.18)
    builder.add_box("digital clock display", (x, SURFACE_Y + 3.6, z + 2.05), (8.4, 4.8, 0.12), screen_mat, taper=0.08)
    builder.add_box("digital clock stand", (x, SURFACE_Y + 0.3, z + 1.2), (10.0, 0.6, 6.6), body_mat, taper=0.2)


def _add_aroma_diffuser(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, mist_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("diffuser base", (x, _surface_center_y(7.0), z), 4.4, 7.0, body_mat, radius_z=4.4, top_radius_x=3.6, top_radius_z=3.6, segments=28)
    builder.add_cylinder_y("diffuser top cap", (x, SURFACE_Y + 7.4, z), 3.6, 0.6, accent_mat, radius_z=3.6, top_radius_x=2.8, top_radius_z=2.8, segments=28)
    builder.add_cylinder_y("diffuser mist", (x, SURFACE_Y + 11.0, z), 1.4, 4.5, mist_mat, radius_z=1.4, top_radius_x=2.4, top_radius_z=2.4, segments=24)


def _add_wireless_charger(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("wireless charger pad", (x, SURFACE_Y + 0.5, z), 5.2, 1.0, body_mat, radius_z=5.2, segments=32)
    builder.add_cylinder_y("wireless charger ring", (x, SURFACE_Y + 1.05, z), 5.3, 0.1, accent_mat, radius_z=5.3, top_radius_x=4.6, top_radius_z=4.6, segments=32)


def _add_pen_holder(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, ink_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("pen holder body", (x, _surface_center_y(10.0), z), 4.5, 10.0, body_mat, radius_z=4.5, top_radius_x=4.7, top_radius_z=4.7, segments=28)
    pen_positions = [(-2.0, -1.0, ink_mat, 12.5), (1.5, -1.5, accent_mat, 13.5), (-0.5, 2.0, body_mat, 11.5), (2.4, 1.2, ink_mat, 14.0)]
    for index, (dx, dz, mat, length) in enumerate(pen_positions):
        builder.add_cylinder_y(f"pen {index + 1}", (x + dx, SURFACE_Y + length / 2 + 4.0, z + dz), 0.4, length, mat, radius_z=0.4, segments=14)


def _add_monitor_light_bar(builder: GlbBuilder, *, center_x: float, center_z: float, body_mat: int, light_mat: int, monitor_top_y: float, screen_back_z: float) -> None:
    bar_y = monitor_top_y + 2.5
    builder.add_box("monitor light bar mount", (center_x, monitor_top_y, screen_back_z + 1.5), (5.0, 2.5, 4.0), body_mat, taper=0.2)
    builder.add_box("monitor light bar housing", (center_x, bar_y, screen_back_z + 1.0), (45.0, 1.6, 3.4), body_mat, taper=0.1)
    builder.add_box("monitor light bar emitter", (center_x, bar_y - 0.85, screen_back_z + 2.4), (44.0, 0.2, 1.2), light_mat, taper=0.05)


def _add_book_stack(builder: GlbBuilder, *, center: tuple[float, float], cover_a: int, cover_b: int, cover_c: int, page_mat: int) -> None:
    x, z = center
    books = [
        (cover_a, 16.5, 3.0, 22.0, -3.0),
        (cover_b, 15.8, 2.6, 21.4, 0.0),
        (cover_c, 17.0, 2.8, 22.6, 2.5),
    ]
    base_y = SURFACE_Y
    for index, (mat, w, h, d, rot_deg) in enumerate(books):
        y = base_y + h / 2
        builder.add_box(f"book cover {index + 1}", (x, y, z), (w, h, d), mat, taper=0.05, rotation_x=math.radians(rot_deg * 0.05))
        builder.add_box(f"book pages {index + 1}", (x + 0.5, y, z), (w - 0.6, h - 0.2, d - 0.5), page_mat, taper=0.04)
        base_y += h


def _add_humidifier(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, mist_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("humidifier tank", (x, _surface_center_y(14.0), z), 6.5, 14.0, body_mat, radius_z=6.5, top_radius_x=5.5, top_radius_z=5.5, segments=32)
    builder.add_cylinder_y("humidifier top", (x, SURFACE_Y + 14.6, z), 5.5, 1.2, accent_mat, radius_z=5.5, top_radius_x=4.6, top_radius_z=4.6, segments=32)
    builder.add_cylinder_y("humidifier mist", (x, SURFACE_Y + 18.5, z), 1.4, 6.0, mist_mat, radius_z=1.4, top_radius_x=2.8, top_radius_z=2.8, segments=24)


def _add_photo_frame(builder: GlbBuilder, *, center: tuple[float, float], frame_mat: int, photo_mat: int) -> None:
    x, z = center
    builder.add_box("photo frame outer", (x, SURFACE_Y + 9.0, z), (14.0, 18.0, 1.4), frame_mat, taper=0.1, rotation_x=math.radians(-8))
    builder.add_box("photo frame photo", (x, SURFACE_Y + 9.0, z + 0.65), (11.5, 15.0, 0.06), photo_mat, rotation_x=math.radians(-8))
    builder.add_box("photo frame stand", (x, SURFACE_Y + 4.0, z + 1.4), (2.0, 8.0, 0.6), frame_mat, taper=0.05, rotation_x=math.radians(20))


def _add_usb_hub(builder: GlbBuilder, *, center: tuple[float, float], body_mat: int, accent_mat: int) -> None:
    x, z = center
    builder.add_box("usb hub body", (x, SURFACE_Y + 1.0, z), (11.0, 2.0, 5.0), body_mat, taper=0.18)
    for index, dx in enumerate((-3.6, -1.2, 1.2, 3.6)):
        builder.add_box(f"usb hub port {index + 1}", (x + dx, SURFACE_Y + 1.0, z - 2.45), (1.6, 0.8, 0.4), accent_mat)
    builder.add_box("usb hub indicator", (x, SURFACE_Y + 2.05, z + 1.5), (1.4, 0.05, 0.4), accent_mat)


def _add_mouse_pad_round(builder: GlbBuilder, *, center: tuple[float, float], pad_mat: int, edge_mat: int) -> None:
    x, z = center
    builder.add_cylinder_y("round mouse pad", (x, SURFACE_Y + 0.18, z), 11.0, 0.35, pad_mat, radius_z=11.0, segments=40)
    builder.add_cylinder_y("round mouse pad edge", (x, SURFACE_Y + 0.40, z), 11.05, 0.04, edge_mat, radius_z=11.05, top_radius_x=10.6, top_radius_z=10.6, segments=40)


# --- Placement helpers ---


class DeskPlacer:
    """Track 2D bounding boxes already placed on the desk surface to avoid overlap."""

    def __init__(self, desk_width: float, desk_depth: float, margin: float = 1.5):
        self.desk_w = desk_width
        self.desk_d = desk_depth
        self.margin = margin
        self.boxes: list[tuple[float, float, float, float, str]] = []  # x_min,z_min,x_max,z_max,label

    def reserve(self, cx: float, cz: float, w: float, d: float, label: str) -> None:
        self.boxes.append((cx - w / 2, cz - d / 2, cx + w / 2, cz + d / 2, label))

    def overlaps(self, cx: float, cz: float, w: float, d: float) -> bool:
        x0, z0 = cx - w / 2 - self.margin, cz - d / 2 - self.margin
        x1, z1 = cx + w / 2 + self.margin, cz + d / 2 + self.margin
        for bx0, bz0, bx1, bz1, _ in self.boxes:
            if x0 <= bx1 and x1 >= bx0 and z0 <= bz1 and z1 >= bz0:
                return True
        return False

    def within_desk(self, cx: float, cz: float, w: float, d: float) -> bool:
        edge = 1.0
        return (
            cx - w / 2 >= -self.desk_w / 2 + edge
            and cx + w / 2 <= self.desk_w / 2 - edge
            and cz - d / 2 >= -self.desk_d / 2 + edge
            and cz + d / 2 <= self.desk_d / 2 - edge
        )

    def find_slot(
        self,
        preferred: tuple[float, float],
        w: float,
        d: float,
        candidates: list[tuple[float, float]] | None = None,
    ) -> tuple[float, float] | None:
        cands = [preferred] + (candidates or [])
        for cx, cz in cands:
            if self.within_desk(cx, cz, w, d) and not self.overlaps(cx, cz, w, d):
                return cx, cz
        return None


def build_keyboard_scene_glb(
    layout_path: Path,
    output_path: Path,
    case_color: str,
    keycap_color: str,
    accent_keycap_color: str,
    deskmat_color: str,
    desk_color: str,
    mouse_color: str,
    case_finish: str = "anodized",
    plate_material: str = "aluminum",
    pcb_color: str = "black",
    switch_stem: str = "red",
    switch_family: str = "mx",
    keycap_profile: str = "cherry",
    mount_type: str = "top_mount",
    show_internals: bool = True,
) -> dict:
    layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
    board_width = float(layout_data["width"])
    board_depth = float(layout_data["height"])
    board_width_cm = board_width * U_CM
    board_depth_cm = board_depth * U_CM

    builder = GlbBuilder()
    deskmat_mat = builder.add_material("deskmat", deskmat_color, roughness=0.9, metallic=0.0)
    desk_mat = builder.add_material("desk", desk_color, roughness=0.78, metallic=0.0)
    mouse_mat = builder.add_material("mouse", mouse_color, roughness=0.48, metallic=0.0)
    mouse_detail_mat = builder.add_material("mouse details", "#d8dde5", roughness=0.58, metallic=0.0)
    accent_detail_mat = builder.add_material("mouse accent", "#3b4148", roughness=0.5, metallic=0.05)

    builder.add_box("desk", (0, -1.4, 0), (board_width_cm + 18, 2.8, board_depth_cm + 22), desk_mat, taper=0.6)
    builder.add_box("deskmat", (0, -0.02, 0.6), (board_width_cm + 11.0, 0.3, board_depth_cm + 9.0), deskmat_mat, taper=0.6)

    keyboard_meta = _add_keyboard_detailed(
        builder,
        layout_data=layout_data,
        center=(0, 0),
        case_color=case_color,
        keycap_color=keycap_color,
        accent_color=accent_keycap_color,
        case_finish=case_finish,
        plate_material=plate_material,
        pcb_color=pcb_color,
        switch_stem=switch_stem,
        switch_family=switch_family,
        keycap_profile=keycap_profile,
        mount_type=mount_type,
        show_internals=show_internals,
    )

    mouse_x = board_width_cm / 2 + 8.0
    _add_mouse(builder, center=(mouse_x, 1.0), mouse_mat=mouse_mat, detail_mat=mouse_detail_mat, accent_mat=accent_detail_mat)

    builder.export(output_path)
    return {
        **keyboard_meta,
        "default_objects": ["desk", "deskmat", "keyboard", "mouse"],
        "model_file": output_path.name,
    }


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
    case_finish: str = "anodized",
    plate_material: str = "aluminum",
    pcb_color: str = "black",
    switch_stem: str = "red",
    switch_family: str = "mx",
    keycap_profile: str = "cherry",
    mount_type: str = "top_mount",
    show_internals: bool = False,
    monitor_arm_style: str = "single",
) -> dict:
    layout_data = json.loads(layout_path.read_text(encoding="utf-8"))

    builder = GlbBuilder()
    deskmat_mat = builder.add_material("deskmat", deskmat_color, roughness=0.9, metallic=0.0)
    desk_mat = builder.add_material("desk wood", desk_color, roughness=0.78, metallic=0.0)
    desk_edge_mat = builder.add_material("desk edge", desk_color, roughness=0.55, metallic=0.05)
    mouse_mat = builder.add_material("mouse", mouse_color, roughness=0.48, metallic=0.0)
    mouse_detail_mat = builder.add_material("mouse details", "#d8dde5", roughness=0.58, metallic=0.0)
    mouse_accent_mat = builder.add_material("mouse accent", "#3a3f48", roughness=0.5, metallic=0.05)
    neutral_mat = builder.add_material("graphite accessory", "#30343b", roughness=0.55, metallic=0.12)
    monitor_bezel_mat = builder.add_material("monitor bezel", "#1a1d23", roughness=0.6, metallic=0.0)
    monitor_stand_mat = builder.add_material("monitor stand", "#22252b", roughness=0.45, metallic=0.18)
    arm_accent_mat = builder.add_material("arm joint accent", "#5a6068", roughness=0.42, metallic=0.18)
    screen_mat = builder.add_material(
        "soft display glow",
        "#101827",
        roughness=0.32,
        metallic=0.0,
        emissive="#3a4a72",
        emissive_strength=1.8,
    )
    warm_light_mat = builder.add_material(
        "warm lamp glow",
        "#f8d28b",
        roughness=0.25,
        metallic=0.0,
        emissive="#f6c474",
        emissive_strength=3.0,
    )
    plant_mat = builder.add_material("desk plant leaves", "#4a6b4b", roughness=0.84, metallic=0.0)
    pot_mat = builder.add_material("ceramic pot", "#d6c8b9", roughness=0.62, metallic=0.0)
    soil_mat = builder.add_material("plant soil", "#3a2a1a", roughness=0.95, metallic=0.0)
    page_mat = builder.add_material("notebook pages", "#f5f1e8", roughness=0.72, metallic=0.0)
    coffee_mat = builder.add_material("coffee surface", "#3b2417", roughness=0.62, metallic=0.0)
    cushion_mat = builder.add_material("headphone cushion", "#2a2c30", roughness=0.85, metallic=0.0)
    cover_a_mat = builder.add_material("book cover dark", "#2c3e50", roughness=0.65, metallic=0.0)
    cover_b_mat = builder.add_material("book cover warm", "#a36446", roughness=0.65, metallic=0.0)
    cover_c_mat = builder.add_material("book cover light", "#d8c8b0", roughness=0.65, metallic=0.0)
    mist_mat = builder.add_material(
        "mist",
        "#e8eff5",
        roughness=0.5,
        metallic=0.0,
        alpha=0.55,
        alpha_mode="BLEND",
    )
    shadow_mat = builder.add_material("soft contact shadow", "#0f172a", roughness=1.0, metallic=0.0, alpha=0.20, alpha_mode="BLEND")
    wood_grain_mat = builder.add_material("subtle desk wood grain", _mix_hex_color(desk_color, "#4b3621", 0.22), roughness=0.9, metallic=0.0)
    deskmat_stitch_mat = builder.add_material("deskmat woven stitch", _mix_hex_color(deskmat_color, "#ffffff", 0.16), roughness=0.95, metallic=0.0)
    grommet_mat = builder.add_material("desk cable grommet dark", "#1f2328", roughness=0.62, metallic=0.08)

    if theme == "gaming":
        screen_mat = builder.add_material(
            "rgb display glow",
            "#2237ff",
            roughness=0.28,
            metallic=0.0,
            emissive="#2845ff",
            emissive_strength=3.5,
        )
        warm_light_mat = builder.add_material(
            "rgb accent glow",
            "#cb4dff",
            roughness=0.25,
            metallic=0.0,
            emissive="#b13cff",
            emissive_strength=4.5,
        )
    elif theme == "pastel":
        pot_mat = builder.add_material("pastel pot", "#c9d8ef", roughness=0.7, metallic=0.0)
    elif theme == "premium":
        neutral_mat = builder.add_material("anodized dark metal", "#1f242b", roughness=0.4, metallic=0.3)

    enabled_assets = set(assets)
    desk_width = max(100.0, min(float(desk_width), 200.0))
    desk_depth = max(50.0, min(float(desk_depth), 90.0))
    front_z = desk_depth / 2
    back_z = -desk_depth / 2

    # Desk tabletop with thin contrasting edge band for a more finished look.
    builder.add_box(
        "desk tabletop",
        (0, -TABLE_TOP_THICKNESS_CM / 2, 0),
        (desk_width, TABLE_TOP_THICKNESS_CM, desk_depth),
        desk_mat,
        taper=0.6,
    )
    builder.add_box(
        "desk edge front",
        (0, -TABLE_TOP_THICKNESS_CM, front_z - 0.4),
        (desk_width - 0.6, 0.4, 0.5),
        desk_edge_mat,
    )
    builder.add_box(
        "desk edge back",
        (0, -TABLE_TOP_THICKNESS_CM, back_z + 0.4),
        (desk_width - 0.6, 0.4, 0.5),
        desk_edge_mat,
    )
    _add_desk_surface_details(
        builder,
        desk_width=desk_width,
        desk_depth=desk_depth,
        grain_mat=wood_grain_mat,
        edge_mat=desk_edge_mat,
        grommet_mat=grommet_mat,
    )
    # Deskmat sized relative to the keyboard footprint, centered slightly forward.
    deskmat_w = min(desk_width - 16.0, 95.0)
    deskmat_d = min(desk_depth - 10.0, 38.0)
    deskmat_z = max(min(front_z - deskmat_d / 2 - 6.0, 12.0), 5.0)
    builder.add_box("deskmat", (0, SURFACE_Y + 0.18, deskmat_z), (deskmat_w, 0.35, deskmat_d), deskmat_mat, taper=0.8)
    _add_deskmat_details(builder, center_z=deskmat_z, width=deskmat_w, depth=deskmat_d, stitch_mat=deskmat_stitch_mat)

    keyboard_center_z = deskmat_z + 3.0
    keyboard_meta = _add_keyboard_detailed(
        builder,
        layout_data=layout_data,
        center=(0, keyboard_center_z),
        case_color=case_color,
        keycap_color=keycap_color,
        accent_color=accent_keycap_color,
        case_finish=case_finish,
        plate_material=plate_material,
        pcb_color=pcb_color,
        switch_stem=switch_stem,
        switch_family=switch_family,
        keycap_profile=keycap_profile,
        mount_type=mount_type,
        show_internals=show_internals,
    )

    placer = DeskPlacer(desk_width=desk_width, desk_depth=desk_depth, margin=1.5)
    case_w = keyboard_meta["case_outer_width"]
    case_d = keyboard_meta["case_outer_depth"]
    _add_contact_shadow(
        builder,
        name="keyboard soft deskmat shadow",
        center=(0, keyboard_center_z),
        size=(case_w + 2.8, case_d + 2.2),
        material=shadow_mat,
        y=SURFACE_Y + 0.46,
    )
    placer.reserve(0, keyboard_center_z, case_w, case_d, "keyboard")

    # Monitor + arm placement reserved at the back so other accessories steer clear.
    monitor_center_z = back_z + 18.0
    panel_w, panel_h = _MONITOR_SIZES_CM.get(monitor_size, _MONITOR_SIZES_CM["27"])
    monitor_meta: dict = {}
    if "monitor" in enabled_assets:
        monitor_meta = _add_monitor(
            builder,
            center_x=0,
            center_z=monitor_center_z,
            body_mat=neutral_mat,
            screen_mat=screen_mat,
            bezel_mat=monitor_bezel_mat,
            stand_mat=monitor_stand_mat,
            with_stand="monitor_arm" not in enabled_assets,
            monitor_size=monitor_size,
        )
        if "monitor_arm" not in enabled_assets:
            placer.reserve(0, monitor_center_z + 7.0, 26.0, 19.0, "monitor base")
        else:
            placer.reserve(0, back_z + 4.0, 12.0, 7.0, "monitor arm clamp")
    if "monitor_arm" in enabled_assets:
        _add_monitor_arm(
            builder,
            center_x=0,
            center_z=monitor_center_z,
            body_mat=neutral_mat,
            accent_mat=arm_accent_mat,
            back_z=back_z,
            style=monitor_arm_style,
        )
    if "monitor_light_bar" in enabled_assets and monitor_meta:
        monitor_top_y = monitor_meta["screen_center_y"] + panel_h / 2 - 1.0
        _add_monitor_light_bar(
            builder,
            center_x=0,
            center_z=monitor_center_z,
            body_mat=neutral_mat,
            light_mat=warm_light_mat,
            monitor_top_y=monitor_top_y,
            screen_back_z=monitor_center_z - 4.0,
        )

    # Mouse placed to the right of keyboard within mat bounds.
    if "mouse" in enabled_assets:
        mouse_x = min(case_w / 2 + 8.0, desk_width / 2 - 6.0)
        mouse_z = keyboard_center_z + 1.0
        placer.reserve(mouse_x, mouse_z, 6.4, 11.0, "mouse")
        _add_contact_shadow(builder, name="mouse soft deskmat shadow", center=(mouse_x, mouse_z), size=(7.0, 12.0), material=shadow_mat, y=SURFACE_Y + 0.46)
        _add_mouse(builder, center=(mouse_x, mouse_z), mouse_mat=mouse_mat, detail_mat=mouse_detail_mat, accent_mat=mouse_accent_mat)

    # Dynamic placement for accessories using DeskPlacer slots.
    def place(asset_id: str, prefer: tuple[float, float], size: tuple[float, float], candidates: list[tuple[float, float]] | None = None) -> tuple[float, float] | None:
        slot = placer.find_slot(prefer, size[0], size[1], candidates)
        if slot is None:
            return None
        placer.reserve(slot[0], slot[1], size[0], size[1], asset_id)
        _add_contact_shadow(
            builder,
            name=f"{asset_id} soft tabletop shadow",
            center=slot,
            size=(max(2.0, size[0] * 0.92), max(2.0, size[1] * 0.92)),
            material=shadow_mat,
            y=SURFACE_Y + 0.07,
        )
        return slot

    if "desk_lamp" in enabled_assets:
        lamp_pref = (-desk_width / 2 + 12.0, back_z + 14.0)
        slot = place("desk_lamp", lamp_pref, (14.0, 14.0), [
            (-desk_width / 2 + 12.0, front_z - 14.0),
            (desk_width / 2 - 12.0, back_z + 14.0),
        ])
        if slot:
            arm_dir = 1.0 if slot[0] < 0 else -1.0
            _add_desk_lamp(builder, center=slot, body_mat=neutral_mat, light_mat=warm_light_mat, arm_dir=arm_dir)

    if "plant" in enabled_assets:
        slot = place("plant", (desk_width / 2 - 12.0, back_z + 16.0), (14.0, 14.0), [
            (-desk_width / 2 + 12.0, back_z + 14.0),
            (desk_width / 2 - 14.0, front_z - 16.0),
        ])
        if slot:
            _add_plant(builder, center=slot, pot_mat=pot_mat, leaf_mat=plant_mat, soil_mat=soil_mat)

    if "speakers" in enabled_assets:
        speaker_gap = min(desk_width / 2 - 12.0, max(panel_w / 2 + 9.0, 36.0))
        sp_z = back_z + 16.0
        for side, side_x in (("left", -speaker_gap), ("right", speaker_gap)):
            placer.reserve(side_x, sp_z, 12.0, 11.0, f"speaker {side}")
        _add_speakers(builder, left_x=-speaker_gap, right_x=speaker_gap, z=sp_z, body_mat=neutral_mat, cone_mat=warm_light_mat, accent_mat=monitor_bezel_mat)

    if "desk_shelf" in enabled_assets:
        shelf_w = min(72.0, desk_width - 20.0)
        slot_z = back_z + 14.0
        placer.reserve(0, slot_z, shelf_w, 22.0, "desk shelf")
        _add_desk_shelf(builder, center=(0, slot_z), wood_mat=desk_mat, support_mat=neutral_mat, width=shelf_w)

    if "notebook" in enabled_assets:
        slot = place("notebook", (-desk_width / 2 + 22.0, front_z - 16.0), (16.0, 22.0), [
            (-desk_width / 2 + 22.0, front_z - 16.0),
            (desk_width / 2 - 22.0, front_z - 16.0),
        ])
        if slot:
            _add_notebook(builder, center=slot, cover_mat=arm_accent_mat, page_mat=page_mat, accent_mat=warm_light_mat)

    if "headphone_stand" in enabled_assets:
        slot = place("headphone_stand", (desk_width / 2 - 14.0, front_z - 14.0), (16.0, 11.0), [
            (-desk_width / 2 + 14.0, front_z - 14.0),
            (desk_width / 2 - 14.0, back_z + 18.0),
        ])
        if slot:
            _add_headphone_stand(builder, center=slot, body_mat=neutral_mat, accent_mat=arm_accent_mat, cushion_mat=cushion_mat)

    if "phone_stand" in enabled_assets:
        slot = place("phone_stand", (desk_width / 2 - 14.0, back_z + 14.0), (10.0, 11.0), [
            (-desk_width / 2 + 14.0, back_z + 14.0),
            (desk_width / 2 - 14.0, 0.0),
        ])
        if slot:
            _add_phone_stand(builder, center=slot, body_mat=neutral_mat, screen_mat=screen_mat, accent_mat=arm_accent_mat)

    if "keycap_tray" in enabled_assets:
        slot = place("keycap_tray", (-desk_width / 2 + 18.0, front_z - 10.0), (22.0, 14.0), [
            (desk_width / 2 - 18.0, front_z - 10.0),
            (-desk_width / 2 + 18.0, back_z + 14.0),
        ])
        if slot:
            _add_keycap_tray(builder, center=slot, tray_mat=neutral_mat, cap_mat=mouse_mat, accent_mat=warm_light_mat)

    if "coffee_mug" in enabled_assets:
        slot = place("coffee_mug", (desk_width / 2 - 12.0, 0.0), (10.0, 10.0), [
            (-desk_width / 2 + 12.0, 0.0),
            (desk_width / 2 - 12.0, front_z - 10.0),
        ])
        if slot:
            _add_coffee_mug(builder, center=slot, mug_mat=page_mat, coffee_mat=coffee_mat)

    if "digital_clock" in enabled_assets:
        slot = place("digital_clock", (-desk_width / 2 + 16.0, back_z + 8.0), (12.0, 9.0))
        if slot:
            _add_digital_clock(builder, center=slot, body_mat=neutral_mat, screen_mat=screen_mat)

    if "aroma_diffuser" in enabled_assets:
        slot = place("aroma_diffuser", (-desk_width / 2 + 14.0, 2.0), (10.0, 10.0), [
            (desk_width / 2 - 14.0, 2.0),
            (-desk_width / 2 + 14.0, back_z + 14.0),
        ])
        if slot:
            _add_aroma_diffuser(builder, center=slot, body_mat=pot_mat, mist_mat=mist_mat, accent_mat=neutral_mat)

    if "wireless_charger" in enabled_assets:
        slot = place("wireless_charger", (desk_width / 2 - 13.0, front_z - 13.0), (12.0, 12.0), [
            (-desk_width / 2 + 13.0, front_z - 13.0),
            (desk_width / 2 - 13.0, -2.0),
        ])
        if slot:
            _add_wireless_charger(builder, center=slot, body_mat=neutral_mat, accent_mat=warm_light_mat)

    if "pen_holder" in enabled_assets:
        slot = place("pen_holder", (-desk_width / 2 + 14.0, front_z - 10.0), (10.0, 10.0))
        if slot:
            _add_pen_holder(builder, center=slot, body_mat=neutral_mat, ink_mat=mouse_accent_mat, accent_mat=warm_light_mat)

    if "book_stack" in enabled_assets:
        slot = place("book_stack", (-desk_width / 2 + 18.0, front_z - 16.0), (18.0, 23.0))
        if slot:
            _add_book_stack(builder, center=slot, cover_a=cover_a_mat, cover_b=cover_b_mat, cover_c=cover_c_mat, page_mat=page_mat)

    if "humidifier" in enabled_assets:
        slot = place("humidifier", (-desk_width / 2 + 14.0, back_z + 16.0), (14.0, 14.0))
        if slot:
            _add_humidifier(builder, center=slot, body_mat=pot_mat, mist_mat=mist_mat, accent_mat=neutral_mat)

    if "photo_frame" in enabled_assets:
        slot = place("photo_frame", (desk_width / 2 - 14.0, back_z + 10.0), (16.0, 8.0))
        if slot:
            _add_photo_frame(builder, center=slot, frame_mat=neutral_mat, photo_mat=screen_mat)

    if "usb_hub" in enabled_assets:
        slot = place("usb_hub", (desk_width / 2 - 12.0, front_z - 6.0), (12.0, 6.0))
        if slot:
            _add_usb_hub(builder, center=slot, body_mat=neutral_mat, accent_mat=warm_light_mat)

    if "mouse_pad_round" in enabled_assets:
        slot = place("mouse_pad_round", (case_w / 2 + 14.0, keyboard_center_z), (22.0, 22.0))
        if slot:
            _add_mouse_pad_round(builder, center=slot, pad_mat=deskmat_mat, edge_mat=warm_light_mat)

    if theme == "gaming":
        builder.add_box("rgb left strip", (-desk_width / 2 + 1.2, SURFACE_Y + 0.28, 0), (0.7, 0.35, desk_depth - 4.0), warm_light_mat)
        builder.add_box("rgb back strip", (0, SURFACE_Y + 0.28, back_z + 1.2), (desk_width - 4.0, 0.35, 0.7), warm_light_mat)

    builder.export(output_path)

    monitor_dim = _MONITOR_SIZES_CM.get(monitor_size, _MONITOR_SIZES_CM["27"])
    placed_items = [box[4] for box in placer.boxes]
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
        "placed_items": placed_items,
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
