"""Prompt construction for vision product recognition providers."""

PRODUCT_RECOGNITION_PROMPT = """You are an industrial warehouse product recognition AI.

Analyze the provided image.

Identify the warehouse item as accurately as possible.

Return ONLY valid JSON.

Required fields:

{
  "name":"",
  "category":"",
  "brand":"",
  "material":"",
  "description":"",
  "color":"",
  "shape":"",
  "estimated_size":"",
  "possible_usage":"",
  "confidence":0.0
}

Do not include markdown.

Do not explain.

Only JSON."""


def build_product_prompt() -> str:
    return PRODUCT_RECOGNITION_PROMPT
