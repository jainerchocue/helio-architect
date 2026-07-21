import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL, HAS_API_KEY, SYSTEM_PROMPT_PLANNER, SYSTEM_PROMPT_REFINER

_client = None

def _get_client():
    global _client
    if _client is None and HAS_API_KEY:
        _client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_API_BASE, timeout=180)
    return _client

def _is_openai():
    return "api.openai.com" in OPENAI_API_BASE

def _call_llm(system_prompt, user_prompt, temperature=0.3, max_retries=0):
    client = _get_client()
    if not client:
        return None
    for attempt in range(max_retries + 1):
        try:
            kwargs = {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": temperature,
                "max_tokens": 3000,
            }
            if _is_openai():
                kwargs["response_format"] = {"type": "json_object"}
            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content
            if content and content.strip():
                return content
            print(f"[LLM] Attempt {attempt+1}: empty response")
        except Exception as e:
            print(f"[LLM] Attempt {attempt+1} error: {e}")
        if attempt < max_retries:
            import time; time.sleep(2)
    return None

def _clean_json(text):
    """Clean LLM text to extract valid JSON."""
    if not text:
        return ""
    text = text.strip()
    # Remove markdown code fences
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    # Find first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        text = text[start:end+1]
    return text

def _parse_json_fallback(text):
    """Try multiple strategies to parse JSON from LLM text."""
    cleaned = _clean_json(text)
    if not cleaned:
        return None
    # Strategy 1: Direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Strategy 2: Remove trailing commas
    try:
        fixed = re.sub(r',\s*}', '}', cleaned)
        fixed = re.sub(r',\s*]', ']', fixed)
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass
    # Strategy 3: Try parsing truncated JSON by finding valid prefix
    for cut in range(len(cleaned), 0, -1):
        try:
            return json.loads(cleaned[:cut])
        except json.JSONDecodeError:
            continue
    return None

def generate_plan(user_prompt):
    import random
    temp = 0.7 + random.random() * 0.3  # random temperature 0.7-1.0 for variety
    raw = _call_llm(SYSTEM_PROMPT_PLANNER, user_prompt, temperature=temp)
    if raw:
        result = _parse_json_fallback(raw)
        if result:
            # Validate required fields
            if "house" not in result or "rooms" not in result:
                print(f"[LLM] Invalid plan: missing required fields")
            else:
                print(f"[LLM] Plan OK: {result.get('project','?')} ({result.get('floors',1)} floor(s), {len(result.get('rooms',[]))} rooms)")
                return result
        else:
            print(f"[LLM] JSON parse failed. Raw: {raw[:200]}...")

    print(f"[LLM] Using demo fallback plan (with keyword changes)")
    demo = _demo_plan(user_prompt)
    try:
        demo = _apply_changes(demo, user_prompt)
    except:
        pass
    return demo

def _demo_plan(prompt):
    """Return a random demo plan for fallback."""
    import random
    seed = hash(prompt + str(random.random())) & 0xFFFF
    rng = random.Random(seed)
    floors = rng.choice([1, 1, 1, 2, 2])
    w = rng.randint(8, 16)
    d = rng.randint(6, 12)
    h = round(rng.uniform(2.8, 3.3), 1)
    n_rooms = rng.randint(4, 8)
    roofs = ["flat", "gable", "gable"]
    mats = ["S", "St", "S", "Fc", "Wd"]
    accs = ["Dk", "Dk", "St", "Wd", "Mb"]
    room_names = ["sala", "cocina", "comedor", "recamara", "bano", "estudio", "lavanderia", "vestidor", "oficina", "gimnasio"]
    colors = [
        [0.91, 0.85, 0.74], [0.8, 0.8, 0.82], [0.85, 0.82, 0.78],
        [0.88, 0.84, 0.8], [0.92, 0.94, 0.96], [0.86, 0.84, 0.8],
        [0.95, 0.88, 0.72], [0.78, 0.82, 0.88], [0.82, 0.9, 0.82],
        [0.9, 0.78, 0.78]
    ]
    rooms = []
    for i in range(n_rooms):
        rw = round(rng.uniform(2.5, 5), 1)
        rd = round(rng.uniform(2.5, 4.5), 1)
        cx = round(rng.uniform(-w/2 + rw/2, w/2 - rw/2), 1)
        cy = round(rng.uniform(-d/2 + rd/2, d/2 - rd/2), 1)
        name = room_names[i % len(room_names)]
        if i > 1 and i < len(room_names):
            name = room_names[i]
        col = colors[i % len(colors)]
        if floors > 1:
            floor = rng.randint(0, floors - 1)
            rooms.append([name, cx, cy, rw, rd, col, floor])
        else:
            rooms.append([name, cx, cy, rw, rd, col])
    return {
        "project": "Casa Demostracion",
        "desc": prompt[:80],
        "site": [w + 6, d + 6],
        "house": [w, d, h],
        "floors": floors,
        "material": rng.choice(mats),
        "accent_material": rng.choice(accs),
        "roof_overhang": round(rng.uniform(0.3, 0.6), 1),
        "roof": rng.choice(roofs),
        "windows": rng.randint(3, 8),
        "base": 0.2,
        "rooms": rooms,
        "garage": rng.choice([True, False]),
        "balcony": False if floors < 2 else {"cx": round(rng.uniform(-2, 2), 1), "cy": d/2 - 1, "ancho": round(rng.uniform(2, 4), 1), "fondo": round(rng.uniform(1.5, 2.5), 1)},
        "stairs": floors > 1,
        "tall_windows": rng.choice([True, False]),
        "pool": rng.choice([[3, 6], [4, 7], False]),
        "trees": rng.randint(1, 5),
        "lights": rng.randint(2, 5),
        "furniture": rng.choice([True, True, False])
    }

def _summarize_plan(plan):
    """Return short summary of plan instead of full JSON for faster LLM calls."""
    rooms = plan.get("rooms", [])
    hw, hd, hh = plan.get("house", [10, 8, 3])
    return (
        f"Casa: {hw}x{hd}m, {hh}m piso, {plan.get('floors',1)} piso(s), "
        f"techo {plan.get('roof','flat')}, {plan.get('windows',0)} ventanas, "
        f"{len(rooms)} cuartos, alberca={'si' if plan.get('pool') else 'no'}, "
        f"cochera={'si' if plan.get('garage') else 'no'}, "
        f"arboles={plan.get('trees',0)}, material={plan.get('material','S')}"
    )

def _apply_changes(plan, prompt):
    """Modify plan in-place based on keywords in user prompt. No LLM needed."""
    import re, copy
    p = prompt.lower()
    modified = copy.deepcopy(plan)

    # arboles
    m = re.search(r'(\d+)\s*arbol', p)
    if m:
        modified["trees"] = max(modified.get("trees", 0), int(m.group(1)))
    elif 'arbol' in p:
        modified["trees"] = max(modified.get("trees", 0), 3)

    # puerta cafe / marron / brown
    if 'cafe' in p or 'marron' in p or 'brown' in p or 'puerta' in p:
        modified["door_color"] = [0.45, 0.25, 0.1]  # cafe oscuro

    # puerta mas grande (grande/grandes)
    if any(g in p for g in ['grande', 'grandes', 'ancha', 'mas grande']) and 'puerta' in p:
        modified["door_width"] = 2.0

    # mas grande / escalar
    if 'mas grande' in p or 'aumenta' in p or 'agranda' in p:
        hw, hd, hh = modified.get("house", [10, 8, 3])
        modified["house"] = [round(hw * 1.3, 1), round(hd * 1.3, 1), round(hh * 1.1, 1)]
        modified["windows"] = min(modified.get("windows", 4) + 2, 12)

    # piscina
    if 'piscina' in p or 'alberca' in p or 'pool' in p:
        if not modified.get("pool"):
            modified["pool"] = [4, 7]

    # garage
    if 'garage' in p or 'cochera' in p:
        modified["garage"] = True

    # balcon
    if 'balcon' in p or 'balcony' in p:
        hw, hd, _ = modified.get("house", [10, 8, 3])
        modified["balcony"] = {"cx": 0, "cy": hd/2 - 1, "ancho": 3, "fondo": 1.8}

    # escalera
    if 'escalera' in p or 'stairs' in p:
        modified["stairs"] = True

    # rascacielos / skyscraper
    if 'rascacielos' in p or 'skyscraper' in p or 'edificio' in p or 'torre' in p:
        modified["curtain_wall"] = True
        modified["roof"] = "flat"
        modified["windows"] = max(modified.get("windows", 6), 12)
        if 'vidrio' in p or 'glass' in p or 'acero' in p or 'steel' in p:
            modified["material"] = "Gl"
            modified["accent_material"] = "Ss"
        if 'helipuerto' in p or 'helipad' in p or 'heli' in p:
            modified["helipad"] = True
        hw, hd, hh = modified.get("house", [10, 8, 3])
        floors = modified.get("floors", 1)
        if floors < 4:
            modified["floors"] = 5
            modified["house"] = [hw, hd, 3.0]
        modified["furniture"] = True

    # ventanas
    m = re.search(r'(\d+)\s*ventan', p)
    if m:
        modified["windows"] = int(m.group(1))

    # colores - cambiar material/accent
    if 'madera' in p or 'wood' in p:
        modified["material"] = "Wd"
        modified["accent_material"] = "Dk"
    if 'blanco' in p or 'white' in p:
        modified["material"] = "S"
        modified["accent_material"] = "Wt"
    if 'piedra' in p or 'stone' in p:
        modified["material"] = "St"
    if 'moderno' in p or 'modern' in p:
        modified["roof"] = "flat"

    modified["desc"] = prompt[:80]
    return modified

def refine_plan(current_plan, change_prompt):
    # First get safe changes via keyword matching (preserves current structure)
    safe = _apply_changes(current_plan, change_prompt)
    ohw, ohd = current_plan.get("house", [10, 8])[:2]
    orooms = len(current_plan.get("rooms", []))
    ofloors = current_plan.get("floors", 1)

    summary = _summarize_plan(current_plan)
    combined = f"PLANO ACTUAL: {summary}\n\nCAMBIO SOLICITADO: {change_prompt}\n\nGenera el NUEVO JSON COMPLETO preservando el maximo del plano actual. SOLO cambia lo solicitado."
    raw = _call_llm(SYSTEM_PROMPT_REFINER, combined, temperature=0.7)
    if raw:
        result = _parse_json_fallback(raw)
        if result and result.get("house") and len(result.get("rooms", [])) >= 2:
            nhw, nhd = result.get("house", [0, 0])[:2]
            nrooms = len(result.get("rooms", []))
            nfloors = result.get("floors", 1)
            # Only accept LLM result if it's similar to original
            hw_diff = abs(ohw - nhw) / max(ohw, 0.1)
            hd_diff = abs(ohd - nhd) / max(ohd, 0.1)
            room_diff = abs(orooms - nrooms)
            if hw_diff < 0.15 and hd_diff < 0.15 and room_diff <= 3 and nfloors == ofloors:
                print(f"[LLM] Refine OK (similar): {nfloors} floor(s), {nrooms} rooms")
                return result
            print(f"[LLM] Refine rejected: too different (hw_diff={hw_diff:.2f}, hd_diff={hd_diff:.2f}, rooms={room_diff}, floors={nfloors}!={ofloors})")
    print(f"[LLM] Using keyword-based changes (safe path)")
    return safe


