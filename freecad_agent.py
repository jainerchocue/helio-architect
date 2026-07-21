import json, traceback

from build_freecad import build_plan, capture_image

def handle_command(cmd):
    action = cmd.get("action")
    try:
        if action == "build_and_render":
            plan = cmd["plan"]
            output_path = cmd["output_path"]
            build_plan(plan)
            ok = capture_image(output_path)
            return {"status": "ok" if ok else "error", "file": output_path}
        elif action == "build":
            plan = cmd["plan"]
            build_plan(plan)
            return {"status": "ok", "rooms": len(plan.get("rooms", []))}
        elif action == "render":
            output_path = cmd["output_path"]
            ok = capture_image(output_path)
            return {"status": "ok" if ok else "error", "file": output_path}
        return {"status": "error", "msg": f"Unknown action: {action}"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}
