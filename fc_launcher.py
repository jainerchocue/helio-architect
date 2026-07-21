import sys, os, socket, threading, json, collections

fc_bin = r"C:\Program Files\FreeCAD 1.1\bin"
sys.path.insert(0, fc_bin)
os.environ["PATH"] = fc_bin + os.pathsep + os.environ.get("PATH", "")

from PySide6 import QtCore, QtWidgets

app = QtWidgets.QApplication(sys.argv)

import FreeCAD as App
import FreeCADGui as Gui

Gui.showMainWindow()

# Ensure Part module is loaded
try:
    import Part
except Exception as e:
    print(f"WARN: could not import Part: {e}")

project_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(project_dir)
sys.path.insert(0, project_dir)

from freecad_agent import handle_command

cmd_queue = collections.deque()
cmd_lock = threading.Lock()

def tcp_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', 9876))
    s.listen(5)
    s.settimeout(1.0)
    print("[AGENT] TCP server ready on port 9876")
    while True:
        try:
            conn, _ = s.accept()
            data = b''
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                data += chunk
                if b'\n' in data:
                    break
            if data:
                with cmd_lock:
                    cmd_queue.append((conn, data))
            else:
                conn.close()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[AGENT] Server error: {e}")
            break

def process_queue():
    while True:
        with cmd_lock:
            if not cmd_queue:
                break
            conn, data = cmd_queue.popleft()
        try:
            cmd = json.loads(data.decode())
            print(f"[AGENT] Processing: {cmd.get('action')}")
            result = handle_command(cmd)
            conn.sendall(json.dumps(result).encode())
        except Exception as e:
            print(f"[AGENT] Handler error: {e}")
            try:
                conn.sendall(json.dumps({"status": "error", "msg": str(e)}).encode())
            except Exception:
                pass
        conn.close()

threading.Thread(target=tcp_server, daemon=True).start()
print("[AGENT] Ready. FreeCAD is alive and listening on port 9876")

timer = QtCore.QTimer()
timer.timeout.connect(process_queue)
timer.start(100)

sys.exit(app.exec())
