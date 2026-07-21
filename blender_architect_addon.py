"""
AI Architect Agent - Blender Addon
Instalar: Blender > Edit > Preferences > Add-ons > Install > seleccionar este archivo
Luego activar: "AI Architect Agent"
"""

bl_info = {
    "name": "AI Architect Agent",
    "author": "AI Architect",
    "version": (2, 0, 0),
    "blender": (4, 0, 0),
    "location": "View3D > Sidebar > AI Architect",
    "description": "TCP agent + builder for AI-generated architecture",
    "category": "3D View",
}

import bpy
import json
import socket
import threading
import math
import os
import sys
import collections

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)
sys.path.insert(0, script_dir)

# ── TCP AGENT ────────────────────────────────────────────────
AGENT_PORT = 9876
cmd_queue = collections.deque()
cmd_lock = threading.Lock()

def handle_command(cmd):
    action = cmd.get("action")
    try:
        if action in ("build_and_render", "build"):
            plan = cmd["plan"]
            print(f"[ARCHITECT] Plan keys: {list(plan.keys())}")
            print(f"[ARCHITECT] house={plan.get('house')}, floors={plan.get('floors')}, roof={plan.get('roof')}, windows={plan.get('windows')}, rooms={len(plan.get('rooms',[]))}, curtain={plan.get('curtain_wall')}, helipad={plan.get('helipad')}")
            build_plan(plan)
            if action == "build_and_render":
                output_path = cmd["output_path"]
                h = plan.get("house", [12, 8, 3])
                render_image(output_path, hw=h[0], hd=h[1], floors=plan.get("floors", 1))
                return {"status": "ok", "file": output_path}
            return {"status": "ok"}
        elif action == "render":
            output_path = cmd["output_path"]
            render_image(output_path)
            return {"status": "ok", "file": output_path}
        return {"status": "error", "msg": f"Unknown action: {action}"}
    except Exception as e:
        import traceback as _tb2
        _tb2.print_exc()
        err = f"[{type(e).__name__}] {e}"
        print(f"[ARCHITECT] BUILD FAILED: {err}")
        return {"status": "error", "msg": err}

def process_queue():
    with cmd_lock:
        while cmd_queue:
            conn, data = cmd_queue.popleft()
            try:
                cmd = json.loads(data.decode().strip())
                print(f"[ARCHITECT] Processing: {cmd.get('action')}")
                result = handle_command(cmd)
                conn.sendall(json.dumps(result).encode())
            except Exception as e:
                print(f"[ARCHITECT] Error: {e}")
                try:
                    conn.sendall(json.dumps({"status": "error", "msg": str(e)}).encode())
                except:
                    pass
            finally:
                try:
                    conn.close()
                except:
                    pass
    return 0.1

def tcp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", AGENT_PORT))
    s.listen(5)
    s.settimeout(1.0)
    print(f"[ARCHITECT] TCP server ready on port {AGENT_PORT}")
    while True:
        try:
            conn, _ = s.accept()
            data = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break
            if data:
                with cmd_lock:
                    cmd_queue.append((conn, data))
            else:
                conn.close()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[ARCHITECT] Server error: {e}")
            break

# ── MATERIALS ────────────────────────────────────────────────
M = {}

def make_mat(name, color, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name=name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color
        bsdf.inputs["Roughness"].default_value = rough
        bsdf.inputs["Metallic"].default_value = metal
    M[name] = m
    return m

def add_bump(mat_node, scale=50.0, strength=0.1):
    nodes = mat_node.node_tree.nodes
    links = mat_node.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return
    noise = nodes.new(type="ShaderNodeTexNoise")
    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = scale
    bump = nodes.new(type="ShaderNodeBump")
    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = strength
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

def setup_glass(mat_node):
    bsdf = mat_node.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.55, 0.75, 0.95, 0.3)
        if "Transmission" in bsdf.inputs:
            bsdf.inputs["Transmission"].default_value = 0.9
        bsdf.inputs["Roughness"].default_value = 0.05
    if hasattr(mat_node, "blend_method"):
        mat_node.blend_method = "BLEND"
    if hasattr(mat_node, "shadow_method"):
        mat_node.shadow_method = "NONE"

def setup_wood(mat_node, color, r=0.4):
    nodes = mat_node.node_tree.nodes
    links = mat_node.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    if not bsdf:
        return
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = r
    coord = nodes.new(type="ShaderNodeTexCoord")
    mapping = nodes.new(type="ShaderNodeMapping")
    if "Scale" in mapping.inputs:
        mapping.inputs["Scale"].default_value = (5.0, 0.2, 1.0)
    noise = nodes.new(type="ShaderNodeTexNoise")
    if "Scale" in noise.inputs:
        noise.inputs["Scale"].default_value = 25.0
    bump = nodes.new(type="ShaderNodeBump")
    if "Strength" in bump.inputs:
        bump.inputs["Strength"].default_value = 0.12
    links.new(coord.outputs["Generated"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

def init_mats():
    make_mat("Wall", (0.92, 0.90, 0.87, 1), 0.6)
    add_bump(M["Wall"], 250.0, 0.03)
    make_mat("Trim", (0.3, 0.3, 0.32, 1), 0.4)
    make_mat("Roof", (0.62, 0.22, 0.15, 1), 0.9)
    add_bump(M["Roof"], 60.0, 0.15)
    make_mat("Floor", (0.55, 0.55, 0.58, 1), 0.7)
    make_mat("Glass", (0.55, 0.75, 0.95, 0.3), 0.05)
    setup_glass(M["Glass"])
    make_mat("Wood", (0.4, 0.25, 0.1, 1), 0.4)
    setup_wood(M["Wood"], (0.4, 0.25, 0.1, 1), 0.4)
    make_mat("DarkWood", (0.35, 0.32, 0.28, 1), 0.5, 0.1)
    setup_wood(M["DarkWood"], (0.35, 0.32, 0.28, 1), 0.5)
    make_mat("Stone", (0.82, 0.78, 0.72, 1), 0.7)
    add_bump(M["Stone"], 20.0, 0.2)
    make_mat("Water", (0.05, 0.35, 0.70, 0.8), 0.02)
    for n, c, r, m in [
        ("Grass", (0.18, 0.52, 0.12, 1), 0.9, 0),
        ("Bark", (0.30, 0.20, 0.10, 1), 0.9, 0),
        ("Leaf", (0.15, 0.50, 0.08, 1), 0.8, 0),
        ("Metal", (0.65, 0.65, 0.67, 1), 0.2, 0.8),
        ("Gold", (0.85, 0.72, 0.30, 1), 0.2, 0.7),
        ("Dark", (0.25, 0.25, 0.28, 1), 0.8, 0),
        ("White", (0.95, 0.95, 0.97, 1), 0.7, 0),
    ]:
        make_mat(n, c, r, m)

def mt(name):
    return M.get(name)

MAT_CODE_MAP = {
    "S": "Wall", "Dk": "DarkWood", "St": "Stone", "Fc": "Floor",
    "Wd": "Wood", "Rf": "Roof", "Gl": "Glass", "Wa": "Water",
    "Wt": "White", "Cp": "Metal", "Ss": "Metal", "Mb": "Stone",
    "Gr": "Grass", "Bk": "Bark",
}

def resolve_mat(code):
    """Map LLM material code to actual material name."""
    if not code:
        return None
    name = MAT_CODE_MAP.get(code)
    if name and mt(name):
        return name
    # Try direct name
    if mt(code):
        return code
    return None

# ── BUILD HELPERS ────────────────────────────────────────────
def box(pos, scale, name, mat_name):
    bpy.ops.mesh.primitive_cube_add(size=1, location=pos)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    if mat_name and mt(mat_name):
        obj.data.materials.append(mt(mat_name))
    return obj

def cyl(pos, radius, depth, name, mat_name):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth, location=pos)
    obj = bpy.context.active_object
    obj.name = name
    if mat_name and mt(mat_name):
        obj.data.materials.append(mt(mat_name))
    return obj

def sphere(pos, radius, name, mat_name):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=radius, location=pos)
    obj = bpy.context.active_object
    obj.name = name
    if mat_name and mt(mat_name):
        obj.data.materials.append(mt(mat_name))
    return obj

def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    M.clear()

# ── BUILD PLAN ───────────────────────────────────────────────
def auto_rooms(hw, hd, room_list, num_floors=1):
    n = len(room_list)
    if n == 0:
        return []
    max_per_floor = max(1, math.ceil(n / num_floors))
    placed = []
    for level in range(num_floors):
        start = level * max_per_floor
        end = min(start + max_per_floor, n)
        slice_r = room_list[start:end]
        m2 = len(slice_r)
        if m2 == 0:
            break
        cols = max(1, min(m2, max(1, int(round(math.sqrt(m2 * hw / hd))))))
        rows = max(1, math.ceil(m2 / cols))
        cell_w = hw / cols
        cell_d = hd / rows
        for i, r in enumerate(slice_r):
            nm = r[0] if r else f"Room{start+i}"
            col = r[5] if len(r) > 5 else [0.8, 0.8, 0.8]
            cx = (i % cols) * cell_w + cell_w / 2 - hw / 2
            cy = (i // cols) * cell_d + cell_d / 2 - hd / 2
            rw = cell_w * 0.85
            rd_ = cell_d * 0.85
            placed.append((nm, cx, cy, rw, rd_, col, level))
    return placed

def build_plan(plan):
    clear_scene()
    init_mats()
    bpy.context.scene.unit_settings.system = "METRIC"
    import traceback as _tb

    site = [float(x) for x in plan.get("site", [20, 16])]
    hw = float(plan.get("house", [12, 8, 3.0])[0])
    hd = float(plan.get("house", [12, 8, 3.0])[1])
    hh = float(plan.get("house", [12, 8, 3.0])[2])
    num_floors = int(plan.get("floors", 1))
    win_total = int(plan.get("windows", 4))
    roof_type = plan.get("roof", "flat")
    pool_size = plan.get("pool")
    tree_count = int(plan.get("trees", 0))
    has_garage = bool(plan.get("garage", False))
    has_furniture = bool(plan.get("furniture", False))
    has_stairs = bool(plan.get("stairs", False))
    balcony = plan.get("balcony")
    tall_windows = bool(plan.get("tall_windows", False))
    rooms_raw = plan.get("rooms", [])
    hw2, hd2 = hw / 2, hd / 2
    fz = 0.3
    wt = 0.2
    curtain = bool(plan.get("curtain_wall", False)) or (num_floors >= 3 and win_total >= 8)
    helipad = bool(plan.get("helipad", False)) or (num_floors >= 4 and roof_type == "flat")
    # Resolve materials
    wall_mat = resolve_mat(plan.get("material", "S")) or "Wall"
    accent_mat = resolve_mat(plan.get("accent_material")) or "Dark"

    def _try(section_name, fn):
        """Run fn and log errors without crashing build_plan."""
        try:
            fn()
        except Exception as e:
            _tb.print_exc()
            print(f"[BUILD] FAILED in {section_name}: {type(e).__name__}: {e}")

    def floor_z(level):
        return fz + level * hh

    # Terrain
    box((0, 0, -0.15), (site[0], site[1], 0.15), "Terrain", "Grass")
    # Driveway
    if has_garage:
        box((-hw2 - 0.3 - 1.75, hd2 + 4, -0.05), (3.5, 8, 0.05), "Driveway", "Stone")
    # Walkway
    box((-0.6, -hd2 - 0.75, -0.05), (1.2, 1.5, 0.05), "Walkway", "Stone")
    # Slab
    box((0, 0, fz / 2), (hw + 0.4, hd + 0.4, fz), "Slab", "Floor")

    # Walls per floor
    for level in range(num_floors):
        z = floor_z(level)
        if curtain and num_floors >= 3:
            # Thin frame structure, glass fills gaps
            # Corner structure pillars
            for cx, cy in [(-hw2 - wt, -hd2 - wt), (hw2 + wt, -hd2 - wt),
                           (-hw2 - wt, hd2 + wt), (hw2 + wt, hd2 + wt)]:
                box((cx, cy, z + hh / 2), (wt * 2, wt * 2, hh), f"Pillar_L{level}", accent_mat)
            # Floor slab edges (all 4 sides)
            box((0, -hd2 - wt / 2, z + hh / 2), (hw, wt, hh), f"SpandrelFront_L{level}", accent_mat)
            box((0, hd2 + wt / 2, z + hh / 2), (hw, wt, hh), f"SpandrelBack_L{level}", accent_mat)
            box((-hw2 - wt / 2, 0, z + hh / 2), (wt, hd, hh), f"SpandrelLeft_L{level}", accent_mat)
            box((hw2 + wt / 2, 0, z + hh / 2), (wt, hd, hh), f"SpandrelRight_L{level}", accent_mat)
        else:
            box((0, -hd2 - wt / 2, z + hh / 2), (hw, wt, hh), f"WallFront_L{level}", wall_mat)
            box((0, hd2 + wt / 2, z + hh / 2), (hw, wt, hh), f"WallBack_L{level}", wall_mat)
            box((-hw2 - wt / 2, 0, z + hh / 2), (wt, hd + 2 * wt, hh), f"WallLeft_L{level}", wall_mat)
            box((hw2 + wt / 2, 0, z + hh / 2), (wt, hd + 2 * wt, hh), f"WallRight_L{level}", wall_mat)
            # Corner columns
            for cx, cy in [(-hw2 - wt / 2, -hd2 - wt / 2),
                           (hw2 + wt / 2, -hd2 - wt / 2),
                           (-hw2 - wt / 2, hd2 + wt / 2),
                           (hw2 + wt / 2, hd2 + wt / 2)]:
                box((cx, cy, z + hh / 2), (wt, wt, hh), f"Column_L{level}", accent_mat)

    # Floor dividers
    for level in range(1, num_floors):
        z = floor_z(level)
        box((0, 0, z - 0.05), (hw, hd, 0.1), f"FloorDiv_{level}", "Floor")

    # Windows with frames
    if hw > 0:
        def place_windows(wname, wy, cnt, back=False):
            spacing = hw / (cnt + 1)
            for level in range(num_floors):
                z = floor_z(level)
                for i in range(cnt):
                    wx = -hw2 + spacing * (i + 1)
                    side = 1 if back else -1
                    yf = wy + side * 0.01
                    pwin_h = hh - 0.2
                    if curtain:
                        box((wx, yf, z + pwin_h / 2), (spacing * 0.8, 0.03, pwin_h),
                            f"Curtain_{wname}_{level}_{i}", "Glass")
                        box((wx, yf, z + pwin_h / 2), (0.04, 0.04, pwin_h),
                            f"Mullion_{wname}_{level}_{i}", "Metal")
                    elif win_total > 0:
                        win_w = max(1.8, min(2.5, hw * 0.28))
                        win_h = hh * 0.55
                        if tall_windows:
                            win_h = hh * 0.75
                        sill = hh * 0.08
                        fw = 0.06
                        wz = z + sill
                        box((wx, yf, wz - fw), (win_w + 2 * fw, 0.06, win_h + 2 * fw),
                            f"Frm{wname}_{level}_{i}", "Dark")
                        box((wx, yf + side * 0.02, wz), (win_w, 0.02, win_h),
                            f"Win{wname}_{level}_{i}", "Glass")

        half = max(1, win_total // 2) if win_total > 0 else 1
        place_windows("Front", -hd2 - wt, half)
        place_windows("Back", hd2 + wt, half, True)

    # Curtain wall side glass panels (for skyscraper)
    if curtain:
        for level in range(num_floors):
            z = floor_z(level)
            pwin_h = hh - 0.2
            # Left side full glass
            cnt_side = max(2, int(hd / 2))
            spacing_side = hd / (cnt_side + 1)
            for i in range(cnt_side):
                wy = -hd2 + spacing_side * (i + 1)
                box((-hw2 - wt - 0.02, wy, z + pwin_h / 2), (0.03, spacing_side * 0.8, pwin_h),
                    f"CurtainLeft_{level}_{i}", "Glass")
            # Right side full glass
            for i in range(cnt_side):
                wy = -hd2 + spacing_side * (i + 1)
                box((hw2 + wt + 0.02, wy, z + pwin_h / 2), (0.03, spacing_side * 0.8, pwin_h),
                    f"CurtainRight_{level}_{i}", "Glass")

    # Door + frame
    dw = float(plan.get("door_width", 1.2))
    dh = 2.1
    door_color = plan.get("door_color")
    if door_color:
        dc = door_color[:3]
        dc_tuple = (dc[0], dc[1], dc[2], 1)
        if "DoorMat" not in M:
            make_mat("DoorMat", dc_tuple, 0.5)
        else:
            bsdf = M["DoorMat"].node_tree.nodes.get("Principled BSDF")
            if bsdf:
                bsdf.inputs["Base Color"].default_value = dc_tuple
        door_mat = "DoorMat"
    else:
        door_mat = "Wood"
    box((0, -hd2 - wt - 0.01, fz + dh / 2 + 0.1), (dw, 0.06, dh),
        "Door", door_mat)
    box((0, -hd2 - wt - 0.02, fz + dh / 2 + 0.04), (dw + 0.12, 0.08, dh + 0.12),
        "DoorFrame", "Dark")
    # Doorknob
    if dw > 0.5:
        knob_x = dw / 2 - 0.15
        box((knob_x, -hd2 - wt - 0.08, fz + dh * 0.45), (0.04, 0.04, 0.08),
            "Doorknob", "Gold")

    # Roof
    overhang = 0.4
    roof_w = hw + 2 * overhang
    roof_d = hd + 2 * overhang
    top_z = floor_z(num_floors)
    if roof_type == "gable":
        rh = max(1.5, hw * 0.25)
        import bmesh
        bm = bmesh.new()
        verts = [bm.verts.new((p[0], p[1], p[2])) for p in [
            (-roof_w / 2, -roof_d / 2, top_z), (roof_w / 2, -roof_d / 2, top_z),
            (0, -roof_d / 2, top_z + rh),
            (-roof_w / 2, roof_d / 2, top_z), (roof_w / 2, roof_d / 2, top_z),
            (0, roof_d / 2, top_z + rh)]]
        bm.faces.new((verts[0], verts[1], verts[5], verts[4]))
        bm.faces.new((verts[1], verts[2], verts[5]))
        bm.faces.new((verts[2], verts[0], verts[4], verts[5]))
        bm.faces.new((verts[0], verts[2], verts[1]))
        bm.faces.new((verts[3], verts[4], verts[0]))
        bm.faces.ensure_lookup_table()
        bm.normal_update()
        me = bpy.data.meshes.new("Roof")
        bm.to_mesh(me)
        bm.free()
        roof_obj = bpy.data.objects.new("Roof", me)
        bpy.context.collection.objects.link(roof_obj)
        if mt("Roof"):
            roof_obj.data.materials.append(mt("Roof"))
        # Ridge
        box((0, 0, top_z + rh), (roof_w + 0.05, 0.15, 0.08), "Ridge", "Roof")
    else:
        box((0, 0, top_z + 0.075), (roof_w, roof_d, 0.15), "Roof", "Dark")
    # Fascia
    box((0, -roof_d / 2 - 0.025, top_z), (roof_w + 0.05, 0.05, 0.08),
        "FasciaFront", "Trim")
    box((0, roof_d / 2 - 0.025, top_z), (roof_w + 0.05, 0.05, 0.08),
        "FasciaBack", "Trim")

    # Garage
    if has_garage and hw > 3:
        gw, gd, gh = 3.5, 5.5, hh
        gx = -hw2 - 0.3 - gw / 2
        gy = hd2 - gd / 2
        box((gx, gy, fz + gh / 2), (gw, gd, gh), "Garage", wall_mat)
        box((gx, gy, fz + gh), (gw + 0.4, gd + 0.4, 0.12), "GarageRoof", "Roof")

    # Helipad
    if helipad:
        hrad = max(hw, hd) * 0.35
        hz = top_z + 0.5
        cyl((0, 0, hz), hrad, 0.08, "Helipad", "Dark")
        cyl((0, 0, hz + 0.04), hrad - 0.15, 0.04, "HelipadInner", "White")
        # H marker
        box((-0.6, 0, hz + 0.06), (0.12, 1.2, 0.02), "HeliH_L", "Dark")
        box((0.6, 0, hz + 0.06), (0.12, 1.2, 0.02), "HeliH_R", "Dark")
        box((0, -0.1, hz + 0.06), (1.32, 0.12, 0.02), "HeliH_M", "Dark")
        # Rail / perimeter light ring
        for a in range(0, 360, 30):
            ra = math.radians(a)
            rx = math.cos(ra) * (hrad - 0.1)
            ry = math.sin(ra) * (hrad - 0.1)
            cyl((rx, ry, hz + 0.06), 0.03, 0.04, f"HeliLight_{a}", "Gold")
        print(f"[BUILD] Helipad added (r={hrad:.1f}m)")

    # Balcony
    if balcony and num_floors > 1:
        bwx, bwy, bww, bwd = (balcony.get(k, 0) for k in ("cx", "cy", "ancho", "fondo"))
        bz = floor_z(1)
        box((bwx, bwy, bz - 0.05), (bww, bwd, 0.1), "BalconyFloor", "Floor")
        for dx in (-bww / 2 + 0.1, bww / 2 - 0.1):
            for dy in (-bwd / 2 + 0.1, bwd / 2 - 0.1):
                for _ in range(2):
                    box((bwx + dx, bwy + dy, bz + 0.5), (0.06, 0.06, 1.0),
                        f"BalcPost", "Metal")

    # Pool
    if pool_size and len(pool_size) >= 2:
        pw, pd = max(3, pool_size[0]), max(3, pool_size[1])
        px = hw2 + 2
        py = -hd2 + 2
        box((px, py, -0.75), (pw, pd, 1.5), "Pool", "Dark")
        box((px, py, 0.04), (pw - 0.4, pd - 0.4, 0.08), "PoolWater", "Water")
        box((px, py, 0.04), (pw + 0.4, pd + 0.4, 0.08), "PoolRim", "Stone")

    # Stairs
    if has_stairs:
        sh = 0.15
        steps = int(hh / sh)
        for i in range(steps):
            box((-0.6, -hd2 + 0.5 + i * 0.3, fz + i * sh),
                (1.2, 0.3, sh), f"Step_{i}", "Wood")

    # Trees
    for ti in range(min(tree_count, 8)):
        a = ti * 2.1 + 1.3
        r = max(3, hw2 + 1.5)
        tx = math.cos(a) * r
        ty = math.sin(a) * r
        cyl((tx, ty, 0), 0.1, 1.8, f"Trunk_{ti}", "Bark")
        sphere((tx, ty, 2.2), 0.8 if ti % 2 == 0 else 0.6, f"Leaf_{ti}", "Leaf")

    # Furniture
    def place_furniture(rooms):
        types = {
            "sala": [("Couch", 2.0, 0.8, 0.6, "Dark"), ("Table", 0.8, 0.8, 0.4, "Wood")],
            "living": [("Couch", 2.0, 0.8, 0.6, "Dark"), ("Table", 0.8, 0.8, 0.4, "Wood")],
            "cocina": [("Counter", 1.2, 0.6, 0.8, "Metal"), ("Table", 0.8, 0.6, 0.7, "Wood")],
            "kitchen": [("Counter", 1.2, 0.6, 0.8, "Metal"), ("Table", 0.8, 0.6, 0.7, "Wood")],
            "comedor": [("DiningTable", 1.2, 0.8, 0.7, "Wood")],
            "dining": [("DiningTable", 1.2, 0.8, 0.7, "Wood")],
            "recamara": [("Bed", 1.6, 2.0, 0.4, "Wood"), ("Nightstand", 0.4, 0.4, 0.5, "Dark")],
            "dormitorio": [("Bed", 1.6, 2.0, 0.4, "Wood"), ("Nightstand", 0.4, 0.4, 0.5, "Dark")],
            "bedroom": [("Bed", 1.6, 2.0, 0.4, "Wood"), ("Nightstand", 0.4, 0.4, 0.5, "Dark")],
            "bano": [("Sink", 0.6, 0.5, 0.7, "White"), ("Toilet", 0.4, 0.4, 0.5, "White")],
            "bathroom": [("Sink", 0.6, 0.5, 0.7, "White"), ("Toilet", 0.4, 0.4, 0.5, "White")],
            "bath": [("Sink", 0.6, 0.5, 0.7, "White"), ("Toilet", 0.4, 0.4, 0.5, "White")],
            "oficina": [("Desk", 1.0, 0.5, 0.7, "Wood"), ("Chair", 0.4, 0.4, 0.4, "Dark")],
            "office": [("Desk", 1.0, 0.5, 0.7, "Wood"), ("Chair", 0.4, 0.4, 0.4, "Dark")],
            "estudio": [("Desk", 1.0, 0.5, 0.7, "Wood"), ("Chair", 0.4, 0.4, 0.4, "Dark")],
        }
        for r in rooms:
            nm, rx, ry, rw, rd_, col, level = r
            for k, items in types.items():
                if k in nm.lower():
                    zbase = floor_z(level) + 0.005
                    n = len(items)
                    for idx, (item_name, iw, id_, ih, mat) in enumerate(items):
                        fw = min(iw, rw * 0.65)
                        fd = min(id_, rd_ * 0.65)
                        off = (n - 1) * 0.15
                        fx = rx + (rw - fw) / 2 - off + idx * 0.3
                        fy = ry + (rd_ - fd) / 2 - off + idx * 0.3
                        box((fx, fy, zbase + ih / 2), (fw, fd, ih), f"{item_name}_{level}", mat)
                    break
    # Rooms
    rooms_placed = auto_rooms(hw, hd, rooms_raw, num_floors)
    for r in rooms_placed:
        nm, rx, ry, rw, rd_, col, level = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        zf = floor_z(level) + 0.005
        obj = box((rx, ry, zf), (rw, rd_, 0.01), f"Room_{nm}_{level}", None)
        if obj:
            c = [x / 255 if x > 1 else x for x in col[:3]]
            m_name = f"Mat_{nm}_{level}"
            m_obj = bpy.data.materials.new(name=m_name)
            c_tuple = (c[0], c[1], c[2], 1) if len(c) >= 3 else (0.8, 0.8, 0.8, 1)
            actual_len = len(c_tuple)
            m_obj.diffuse_color = c_tuple
            if obj.data.materials:
                obj.data.materials[0] = m_obj
            else:
                obj.data.materials.append(m_obj)

    # Furniture on top of rooms
    if has_furniture:
        place_furniture(rooms_placed)

    # Sun + sky
    bpy.ops.object.light_add(type="SUN", location=(10, -12, 15))
    sun = bpy.context.active_object
    sun.name = "Sun"
    sun.rotation_euler = (0.8, 0.2, 0.5)
    sun.data.energy = 5
    if hasattr(sun.data, "shadow_soft_size"):
        sun.data.shadow_soft_size = 0.1
    world = bpy.context.scene.world
    if world and world.use_nodes:
        bg = world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs["Color"].default_value = (0.75, 0.85, 0.95, 1)
            bg.inputs["Strength"].default_value = 1.0

    print(f"[BUILD] Done: {len(rooms_placed)} rooms, {win_total} windows, {num_floors} floors")

def render_image(output_path, hw=None, hd=None, floors=1):
    for eng in ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"]:
        try:
            bpy.context.scene.render.engine = eng
            break
        except:
            continue
    bpy.context.scene.render.resolution_x = 1200
    bpy.context.scene.render.resolution_y = 675
    try:
        bpy.context.scene.eevee.taa_render_samples = 8
    except:
        pass
    bpy.context.scene.render.film_transparent = False

    # Camera
    if hw is None: hw = 12
    if hd is None: hd = 8
    total_h = 0.3 + floors * 3.0
    cam_dist = max(hw, hd) * 1.8 + total_h * 0.8 + 4
    bpy.ops.object.camera_add(location=(cam_dist * 0.65, -cam_dist, cam_dist * 0.5 + total_h * 0.3))
    cam = bpy.context.active_object
    cam.rotation_euler = (1.05, 0, 0.6)
    bpy.context.scene.camera = cam

    bpy.context.scene.render.filepath = output_path
    print(f"[RENDER] Rendering to {output_path}...")
    bpy.ops.render.render(write_still=True)
    print(f"[RENDER] Saved: {output_path}")

# ── BLENDER OPERATORS / UI ──────────────────────────────────
class ARCHITECT_OT_start_agent(bpy.types.Operator):
    bl_idname = "architect.start_agent"
    bl_label = "Start Agent"
    bl_description = "Start TCP agent on port 9876"

    def execute(self, context):
        if any("tcp_server" in th.name for th in threading.enumerate() if hasattr(th, "name")):
            self.report({"INFO"}, "Agent already running")
            return {"FINISHED"}
        t = threading.Thread(target=tcp_server, daemon=True, name="tcp_server")
        t.start()
        if not hasattr(bpy.types, "_architect_timer"):
            bpy.app.timers.register(process_queue)
            bpy.types._architect_timer = True
        self.report({"INFO"}, "Agent started on port 9876")
        return {"FINISHED"}

class ARCHITECT_PT_panel(bpy.types.Panel):
    bl_label = "AI Architect Agent"
    bl_idname = "ARCHITECT_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "AI Architect"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Agent port: 9876")
        layout.operator("architect.start_agent", text="Start Agent", icon="PLAY")
        layout.separator()
        layout.label(text="Abre http://localhost:8501")
        layout.label(text="para disenar desde el web app")

# ── REGISTRATION ─────────────────────────────────────────────
classes = [ARCHITECT_OT_start_agent, ARCHITECT_PT_panel]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Auto-start agent
    t = threading.Thread(target=tcp_server, daemon=True, name="tcp_server")
    t.start()
    if not hasattr(bpy.types, "_architect_timer"):
        bpy.app.timers.register(process_queue)
        bpy.types._architect_timer = True
    print("[ARCHITECT] Agent auto-started on port 9876")

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    if hasattr(bpy.types, "_architect_timer"):
        try:
            bpy.app.timers.unregister(process_queue)
        except:
            pass
        del bpy.types._architect_timer

if __name__ == "__main__":
    register()
