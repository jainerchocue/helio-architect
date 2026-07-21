import FreeCAD as App
import Part
import math

def m(v):
    return v * 1000

def clear_doc():
    for name in list(App.listDocuments().keys()):
        App.closeDocument(name)
    return App.newDocument("ArchitectAgent")

def auto_rooms(hw_m, hd_m, room_list, num_floors=1):
    interior_w = hw_m - m(0.5)
    interior_d = hd_m - m(0.5)
    n = len(room_list)
    if n == 0:
        return []
    max_per_floor = max(1, math.ceil(n / num_floors))
    placed = []
    for level in range(num_floors):
        start = level * max_per_floor
        end = min(start + max_per_floor, n)
        slice_rooms = room_list[start:end]
        m2 = len(slice_rooms)
        if m2 == 0:
            break
        cols = max(1, min(m2, max(1, int(round(math.sqrt(m2 * interior_w / interior_d))))))
        rows = max(1, math.ceil(m2 / cols))
        cell_w = interior_w / cols
        cell_d = interior_d / rows
        for i, r in enumerate(slice_rooms):
            nm = r[0] if r else f"Room{start+i}"
            col = r[5] if len(r) > 5 else [0.8, 0.8, 0.8]
            cx = (i % cols) * cell_w + cell_w / 2 - interior_w / 2
            cy = (i // cols) * cell_d + cell_d / 2 - interior_d / 2
            rw_mm = cell_w * 0.88
            rd_mm = cell_d * 0.88
            placed.append((nm, cx, cy, rw_mm, rd_mm, col, level))
    return placed

def build_plan(plan):
    doc = clear_doc()

    site = plan.get("site", [20, 16])
    hw, hd, hh = plan.get("house", [12, 8, 3.0])
    num_floors = plan.get("floors", 1)
    win_total = plan.get("windows", 4)
    roof_type = plan.get("roof", "flat")
    pool_size = plan.get("pool")
    tree_count = plan.get("trees", 0)
    has_garage = plan.get("garage", False)
    has_furniture = plan.get("furniture", False)
    has_stairs = plan.get("stairs", False)
    balcony = plan.get("balcony")
    tall_windows = plan.get("tall_windows", False)
    rooms_raw = plan.get("rooms", [])

    hw_m, hd_m, hh_m = m(hw), m(hd), m(hh)
    wt = m(0.25)
    fz = m(0.3)

    def floor_z(level):
        return fz + level * hh_m

    wall_col = (0.95, 0.91, 0.84)
    dark_col = (0.85, 0.80, 0.72)
    trim_col = (0.3, 0.3, 0.32)

    # Terrain
    t = doc.addObject("Part::Box", "Terrain")
    t.Width = m(site[0]); t.Length = m(site[1]); t.Height = m(0.15)
    t.Placement.Base = App.Vector(-m(site[0])/2, -m(site[1])/2, -m(0.15))
    t.ViewObject.ShapeColor = (0.38, 0.32, 0.22)

    # Driveway
    if has_garage:
        dw = doc.addObject("Part::Box", "Driveway")
        dw.Width = m(3.5); dw.Length = m(8); dw.Height = m(0.05)
        dw.Placement.Base = App.Vector(-hw_m/2 - m(0.3) - m(3.5)/2, hd_m/2, -m(0.05))
        dw.ViewObject.ShapeColor = (0.45, 0.42, 0.38)

    # Walkway
    walk = doc.addObject("Part::Box", "Walkway")
    walk.Width = m(1.2); walk.Length = m(1.5); walk.Height = m(0.05)
    walk.Placement.Base = App.Vector(-m(0.6), -hd_m/2 - m(1.5), -m(0.05))
    walk.ViewObject.ShapeColor = (0.55, 0.5, 0.45)

    # Slab
    s = doc.addObject("Part::Box", "Slab")
    s.Width = hw_m + m(0.4); s.Length = hd_m + m(0.4); s.Height = fz
    s.Placement.Base = App.Vector(-(hw_m + m(0.4))/2, -(hd_m + m(0.4))/2, 0)
    s.ViewObject.ShapeColor = (0.55, 0.55, 0.58)

    # Walls per floor — outer perimeter, left/right wrap around front/back
    for level in range(num_floors):
        z = floor_z(level)

        # Front wall: spans between side wall inner faces
        fw = doc.addObject("Part::Box", f"Wall_Front_L{level}")
        fw.Width = hw_m; fw.Length = wt; fw.Height = hh_m
        fw.Placement.Base = App.Vector(-hw_m/2, -hd_m/2 - wt, z)
        fw.ViewObject.ShapeColor = wall_col

        # Back wall
        bw = doc.addObject("Part::Box", f"Wall_Back_L{level}")
        bw.Width = hw_m; bw.Length = wt; bw.Height = hh_m
        bw.Placement.Base = App.Vector(-hw_m/2, hd_m/2, z)
        bw.ViewObject.ShapeColor = wall_col

        # Left wall: spans full outer depth (front outer face to back outer face)
        lw = doc.addObject("Part::Box", f"Wall_Left_L{level}")
        lw.Width = wt; lw.Length = hd_m + 2*wt; lw.Height = hh_m
        lw.Placement.Base = App.Vector(-hw_m/2 - wt, -hd_m/2 - wt, z)
        lw.ViewObject.ShapeColor = wall_col

        # Right wall
        rw = doc.addObject("Part::Box", f"Wall_Right_L{level}")
        rw.Width = wt; rw.Length = hd_m + 2*wt; rw.Height = hh_m
        rw.Placement.Base = App.Vector(hw_m/2, -hd_m/2 - wt, z)
        rw.ViewObject.ShapeColor = wall_col

        # Corner columns (decorative, on outer corners)
        for cx, cy in [(-hw_m/2 - wt/2, -hd_m/2 - wt/2),
                       (hw_m/2 + wt/2, -hd_m/2 - wt/2),
                       (-hw_m/2 - wt/2, hd_m/2 + wt/2),
                       (hw_m/2 + wt/2, hd_m/2 + wt/2)]:
            col = doc.addObject("Part::Box", f"Column_L{level}")
            col.Width = wt; col.Length = wt; col.Height = hh_m
            col.Placement.Base = App.Vector(cx - wt/2, cy - wt/2, z)
            col.ViewObject.ShapeColor = dark_col

    # Floor dividers
    for level in range(1, num_floors):
        z = floor_z(level)
        div = doc.addObject("Part::Box", f"FloorDiv_{level}")
        div.Width = hw_m; div.Length = hd_m; div.Height = m(0.1)
        div.Placement.Base = App.Vector(-hw_m/2, -hd_m/2, z - m(0.05))
        div.ViewObject.ShapeColor = (0.5, 0.5, 0.52)

    # Windows — wider with frames
    if win_total > 0 and hw_m > 0:
        win_w = max(m(1.8), min(m(2.5), hw_m * 0.28))
        win_h = hh_m * 0.55
        if tall_windows:
            win_h = hh_m * 0.75
        sill = hh_m * 0.08
        frame_w = m(0.06)
        half = max(1, win_total // 2)

        for level in range(num_floors):
            z = floor_z(level) + sill
            spacing = hw_m / (half + 1)
            for i in range(half):
                wx = -hw_m/2 + spacing * (i + 1)

                # Frame
                frame = doc.addObject("Part::Box", f"FrmFront_{level}_{i}")
                frame.Width = win_w + 2*frame_w
                frame.Height = win_h + 2*frame_w
                frame.Length = m(0.08)
                frame.Placement.Base = App.Vector(wx - (win_w + 2*frame_w)/2,
                                                  -hd_m/2 - wt - m(0.01),
                                                  z - frame_w)
                frame.ViewObject.ShapeColor = trim_col

                # Glass
                glass = doc.addObject("Part::Box", f"WinFront_{level}_{i}")
                glass.Width = win_w; glass.Height = win_h; glass.Length = m(0.04)
                glass.Placement.Base = App.Vector(wx - win_w/2,
                                                  -hd_m/2 - wt - m(0.01),
                                                  z)
                glass.ViewObject.ShapeColor = (0.5, 0.75, 0.92)
                glass.ViewObject.Transparency = 30

            spacing2 = hw_m / (win_total - half + 1)
            for i in range(win_total - half):
                wx = -hw_m/2 + spacing2 * (i + 1)

                frame = doc.addObject("Part::Box", f"FrmBack_{level}_{i}")
                frame.Width = win_w + 2*frame_w
                frame.Height = win_h + 2*frame_w
                frame.Length = m(0.08)
                frame.Placement.Base = App.Vector(wx - (win_w + 2*frame_w)/2,
                                                  hd_m/2 + wt - m(0.04),
                                                  z - frame_w)
                frame.ViewObject.ShapeColor = trim_col

                glass = doc.addObject("Part::Box", f"WinBack_{level}_{i}")
                glass.Width = win_w; glass.Height = win_h; glass.Length = m(0.04)
                glass.Placement.Base = App.Vector(wx - win_w/2,
                                                  hd_m/2 + wt - m(0.04),
                                                  z)
                glass.ViewObject.ShapeColor = (0.5, 0.75, 0.92)
                glass.ViewObject.Transparency = 30

    # Door
    dw, dh = m(1.2), m(2.1)
    door = doc.addObject("Part::Box", "Door")
    door.Width = dw; door.Height = dh; door.Length = m(0.08)
    door.Placement.Base = App.Vector(-dw/2, -hd_m/2 - wt - m(0.01), fz + m(0.1))
    door.ViewObject.ShapeColor = (0.4, 0.22, 0.08)

    door_f = doc.addObject("Part::Box", "DoorFrame")
    door_f.Width = dw + m(0.12); door_f.Height = dh + m(0.12); door_f.Length = m(0.12)
    door_f.Placement.Base = App.Vector(-(dw + m(0.12))/2, -hd_m/2 - wt - m(0.02), fz + m(0.1) - m(0.06))
    door_f.ViewObject.ShapeColor = trim_col

    handle = doc.addObject("Part::Cylinder", "Handle")
    handle.Radius = m(0.018); handle.Height = m(0.12)
    handle.Placement.Base = App.Vector(m(0.3), -hd_m/2 - wt - m(0.03), fz + m(1.0))
    handle.Placement.Rotation = App.Rotation(App.Vector(0, 1, 0), 90)
    handle.ViewObject.ShapeColor = (0.7, 0.6, 0.3)

    # Roof
    top_z = floor_z(num_floors)
    overhang = m(0.4)
    roof_w = hw_m + 2*overhang
    roof_d = hd_m + 2*overhang
    roof_color = (0.62, 0.22, 0.15)

    if roof_type == "gable":
        rh = m(max(1.5, hw * 0.25))
        try:
            verts = [
                App.Vector(-roof_w/2, -roof_d/2, top_z),
                App.Vector(roof_w/2, -roof_d/2, top_z),
                App.Vector(0, -roof_d/2, top_z + rh),
                App.Vector(-roof_w/2, roof_d/2, top_z),
                App.Vector(roof_w/2, roof_d/2, top_z),
                App.Vector(0, roof_d/2, top_z + rh),
            ]
            faces = [[0, 1, 2], [3, 5, 4], [0, 3, 4, 1], [0, 2, 5, 3], [1, 4, 5, 2]]
            shell = Part.makeShell([Part.makeFace(Part.makePolygon([verts[i] for i in f] + [verts[f[0]]])) for f in faces])
            roof = doc.addObject("Part::Feature", "Roof")
            roof.Shape = Part.makeSolid(shell)
            roof.ViewObject.ShapeColor = roof_color
        except:
            roof = doc.addObject("Part::Box", "Roof")
            roof.Width = roof_w; roof.Length = roof_d; roof.Height = m(0.15)
            roof.Placement.Base = App.Vector(-roof_w/2, -roof_d/2, top_z)
            roof.ViewObject.ShapeColor = roof_color
    else:
        roof = doc.addObject("Part::Box", "Roof")
        roof.Width = roof_w; roof.Length = roof_d; roof.Height = m(0.15)
        roof.Placement.Base = App.Vector(-roof_w/2, -roof_d/2, top_z)
        roof.ViewObject.ShapeColor = (0.18, 0.18, 0.2)

    # Roof fascia
    fac = doc.addObject("Part::Box", "Fascia")
    fac.Width = roof_w + m(0.05); fac.Length = m(0.05); fac.Height = m(0.08)
    fac.Placement.Base = App.Vector(-(roof_w + m(0.05))/2, -roof_d/2 - m(0.025), top_z)
    fac.ViewObject.ShapeColor = trim_col

    fac2 = doc.addObject("Part::Box", "FasciaBack")
    fac2.Width = roof_w + m(0.05); fac2.Length = m(0.05); fac2.Height = m(0.08)
    fac2.Placement.Base = App.Vector(-(roof_w + m(0.05))/2, roof_d/2 - m(0.025), top_z)
    fac2.ViewObject.ShapeColor = trim_col

    # Garage
    if has_garage and hw_m > m(3):
        gw, gd, gh = m(3.5), m(5.5), hh_m
        gx = -hw_m/2 - m(0.3) - gw
        gy = hd_m/2 - gd
        gbox = doc.addObject("Part::Box", "Garage")
        gbox.Width = gw; gbox.Length = gd; gbox.Height = gh
        gbox.Placement.Base = App.Vector(gx, gy - gd/2, fz)
        gbox.ViewObject.ShapeColor = wall_col

        groof = doc.addObject("Part::Box", "GarageRoof")
        groof.Width = gw + m(0.4); groof.Length = gd + m(0.4); groof.Height = m(0.12)
        groof.Placement.Base = App.Vector(gx - m(0.2), gy - gd/2 - m(0.2), fz + gh)
        groof.ViewObject.ShapeColor = roof_color

        gdoor = doc.addObject("Part::Box", "GarageDoor")
        gdoor.Width = m(2.8); gdoor.Height = m(2.1); gdoor.Length = m(0.05)
        gdoor.Placement.Base = App.Vector(gx + gw/2 - m(0.04), gy - m(1.4), fz + m(0.05))
        gdoor.ViewObject.ShapeColor = (0.5, 0.5, 0.5)

    # Balcony
    if balcony and num_floors > 1:
        bwx, bwy, bww, bwd = m(balcony["cx"]), m(balcony["cy"]), m(balcony["ancho"]), m(balcony["fondo"])
        bz = floor_z(1)
        bfloor = doc.addObject("Part::Box", "BalconyFloor")
        bfloor.Width = bww; bfloor.Length = bwd; bfloor.Height = m(0.1)
        bfloor.Placement.Base = App.Vector(bwx - bww/2, bwy - bwd/2, bz)
        bfloor.ViewObject.ShapeColor = (0.5, 0.5, 0.5)

        for bx, by in [(bwx - bww/2, bwy - bwd/2), (bwx - bww/2, bwy + bwd/2 - m(0.05)),
                       (bwx + bww/2 - m(0.05), bwy - bwd/2), (bwx + bww/2 - m(0.05), bwy + bwd/2 - m(0.05))]:
            for r in range(4):
                post = doc.addObject("Part::Box", f"BalcPost")
                post.Width = m(0.06); post.Length = m(0.06); post.Height = m(1.0)
                post.Placement.Base = App.Vector(bx + r * (bww - m(0.06))/3 if bx == bwx - bww/2 else bx,
                                                 by + r * (bwd - m(0.06))/3 if by == bwy - bwd/2 else by,
                                                 bz)
                post.ViewObject.ShapeColor = trim_col

    # Pool
    if pool_size and len(pool_size) >= 2:
        pw, pd = m(max(3, pool_size[0])), m(max(3, pool_size[1]))
        px = hw_m/2 + m(2)
        py = -hd_m/2 + m(2)
        pool = doc.addObject("Part::Box", "Pool")
        pool.Width = pw; pool.Length = pd; pool.Height = m(1.5)
        pool.Placement.Base = App.Vector(px, py, -m(1.5))
        pool.ViewObject.ShapeColor = (0.05, 0.45, 0.65)
        pool.ViewObject.Transparency = 35

        rim = doc.addObject("Part::Box", "PoolRim")
        rim.Width = pw + m(0.4); rim.Length = pd + m(0.4); rim.Height = m(0.08)
        rim.Placement.Base = App.Vector(px - m(0.2), py - m(0.2), 0)
        rim.ViewObject.ShapeColor = (0.55, 0.5, 0.45)

    # Interior stairs
    if has_stairs:
        sw, sd, sh = m(1.2), m(0.3), m(0.15)
        steps = int(hh_m / sh)
        for i in range(steps):
            step = doc.addObject("Part::Box", f"Step_{i}")
            step.Width = sw; step.Length = sd; step.Height = sh
            step.Placement.Base = App.Vector(-sw/2, -hd_m/2 + m(0.5) + i * sd, fz + i * sh)
            step.ViewObject.ShapeColor = (0.65, 0.6, 0.5)

    # Trees
    for ti in range(min(tree_count, 8)):
        a = ti * 2.1 + 1.3
        r = max(m(3), hw_m/2 + m(1.5))
        tx = math.cos(a) * r
        ty = math.sin(a) * r
        trunk = doc.addObject("Part::Cylinder", f"Trunk_{ti}")
        trunk.Radius = m(0.1); trunk.Height = m(1.8)
        trunk.Placement.Base = App.Vector(tx, ty, 0)
        trunk.ViewObject.ShapeColor = (0.28, 0.18, 0.08)
        leaf = doc.addObject("Part::Sphere", f"Leaf_{ti}")
        leaf.Radius = m(0.8 if ti % 2 == 0 else 0.6)
        leaf.Placement.Base = App.Vector(tx, ty, m(2.2))
        leaf.ViewObject.ShapeColor = (0.1, 0.45, 0.06)

    # Rooms
    rooms_placed = auto_rooms(hw_m, hd_m, rooms_raw, num_floors)
    for r in rooms_placed:
        nm, rx, ry, rw, rd, col, level = r[0], r[1], r[2], r[3], r[4], r[5], r[6]
        zf = floor_z(level) + 5
        safe = "".join(c for c in nm if c.isalnum() or c in " _-")[:48]
        fm = doc.addObject("Part::Box", f"Flr_{safe}_{level}")
        fm.Width = rw; fm.Length = rd; fm.Height = 10
        fm.Placement.Base = App.Vector(rx - rw/2, ry - rd/2, zf)
        c = [x / 255 if x > 1 else x for x in col]
        fm.ViewObject.ShapeColor = tuple(c[:3])
        fm.ViewObject.Transparency = 50

    doc.recompute()

    try:
        import FreeCADGui as Gui
        v = Gui.ActiveDocument.ActiveView
        v.viewAxonometric()
        v.fitAll()
    except Exception as e:
        print(f"[BUILD] Camera error: {e}")

    print(f"[BUILD] Done: {len(rooms_placed)} rooms, {win_total} windows, {num_floors} floors")

def capture_image(output_path):
    try:
        import FreeCADGui as Gui
        view = Gui.ActiveDocument.ActiveView
        view.saveImage(output_path, 1200, 675, "White")
        print(f"[CAPTURE] Saved to {output_path}")
        return True
    except Exception as e:
        print(f"[CAPTURE] Error: {e}")
        return False
