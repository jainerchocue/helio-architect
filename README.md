# Helio Architect - AI 3D House Generator

Generate 3D architectural models from natural language prompts using Blender + AI.

## Stack

- **Python 3.14** + **Blender 5.2** for 3D rendering
- **Streamlit** web interface
- **OpenRouter** (DeepSeek V4 Flash) for AI planning
- **GPT-5.6 + Codex** used for code generation and debugging

## Quick Start

1. Clone the repo
2. Create `.env` file:
   ```
   OPENAI_API_KEY=sk-or-v1-...
   OPENAI_API_BASE=https://openrouter.ai/api/v1
   OPENAI_MODEL=deepseek/deepseek-v4-flash
   ```
3. Install deps: `pip install -r requirements.txt`
4. Open Blender 5.2, install addon from `blender_architect_addon.py`
5. Run: `streamlit run web_app.py`
6. Type a prompt like: *"Modern villa with pool and large windows"*

## Features

- Parametric house generation from text
- Furniture layout (living room, kitchen, bedrooms, bathrooms, office)
- PBR materials (glass, metal, wood, concrete)
- Curtain walls and helipads auto-activate for tall buildings
- Real-time preview via Blender Eevee renderer
