import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
GENERATED_DIR = PROJECT_ROOT / "generated"
RENDERS_DIR = PROJECT_ROOT / "renders"
GENERATED_DIR.mkdir(exist_ok=True)
RENDERS_DIR.mkdir(exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

BLENDER_PATH = os.getenv(
    "BLENDER_PATH",
    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"
)

HAS_API_KEY = bool(OPENAI_API_KEY) and OPENAI_API_KEY != "sk-your-key-here"

SYSTEM_PROMPT_PLANNER = """Eres un arquitecto AI CREATIVO y ORIGINAL. NUNCA repitas el mismo diseno. Cada respuesta debe ser UNICA.

Genera JSON para construir una casa 3D con estas capacidades:
- rooms: [nombre, cx, cy, ancho, fondo, [R,G,B], piso] (piso 0=planta baja)
- floors: N (default 1). Distribuye rooms entre pisos
- roof: "flat" o "gable"
- windows: N total
- pool: [ancho, fondo] o false
- trees: N
- garage: true/false
- balcony: {"cx":x,"cy":y,"ancho":w,"fondo":d} o false
- stairs: true/false (si floors>1)
- tall_windows: true/false
- furniture: true/false
- house: [ancho (6-18), fondo (6-14), altura_piso (2.5-3.5)]
- site: [ancho, fondo] (mayor que house)
- door_width: ancho de puerta en metros (default 1.2, poner 1.6-2.4 para puerta grande)
- door_color: [R,G,B] color de la puerta (ej [0.45,0.25,0.1] cafe)
- curtain_wall: true/false (muro cortina de vidrio para rascacielos)
- helipad: true/false (helipuerto en techo para 4+ pisos)

CREATIVIDAD:
- VARIA las dimensiones de house CADA VEZ (usa todo el rango 6-18)
- VARIA numero de rooms (3-10)
- VARIA colores de rooms (no repetir grises, usa colores vibrantes)
- Si el usuario pide algo especifico, interpretalo con imaginacion
- Asigna materiales variados: material y accent_material segun el estilo
- Techos planos para moderno, gable para clasico

CRITICO: CADA GENERACION DEBE SER DISTINTA. Cambia tamanos, colores, distribucion.

Responde SOLO JSON valido. SIN markdown."""

SYSTEM_PROMPT_REFINER = """Eres un arquitecto AI. Recibes un RESUMEN del plano actual + el cambio solicitado. Genera el NUEVO JSON COMPLETO.

FORMATO JSON REQUERIDO (ejemplo):
{"project":"...","desc":"...","site":[20,16],"house":[12,8,3],"floors":1,"roof":"gable","windows":4,"rooms":[["sala",0,0,5,4,[0.9,0.85,0.74]],["cocina",3,0,4,4,[0.8,0.8,0.82]]],"pool":false,"trees":2,"garage":false,"balcony":false,"stairs":false,"furniture":true,"door_width":1.2,"door_color":[0.45,0.25,0.1]}

CAPACIDADES: rooms (hasta 10), floors (1-5), roof (flat/gable), windows (2-20), pool, trees, garage, balcony, stairs, furniture, tall_windows, door_width, door_color, curtain_wall, helipad

CREATIVIDAD: Cambia dimensiones, colores, distribucion segun lo solicitado. NUNCA repitas exactamente el plano anterior. SIEMPRE devuelve JSON valido.

Responde UNICAMENTE el JSON. Sin explicaciones, sin markdown."""

