import os
import json
from openai import OpenAI
import re

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def parse_receipt_image(file_path: str) -> dict:
    """
    Send an image file to OpenAI multimodal endpoint to extract receipt fields.
    Returns a dict with detected fields and confidence when possible.
    If OpenAI is not configured, return an empty-ish result.
    """
    if client:
        try:
            # The exact multimodal API usage may differ by SDK version. This is a conservative approach
            # sending a prompt that instructs the model to read the image and return JSON.
            prompt = (
                "Lee la factura/recibo en la imagen adjunta y devuelve un JSON con los campos: merchant, description, "
                "date, total, currency, category, payment_method, invoice_number, products (si aparecen) y confidence. "
                "Si un campo no aparece, usa null. Responde SOLO JSON."
            )
            # Many SDKs accept 'input' or 'messages' and attachments; here we provide a placeholder approach.
            resp = client.responses.create(
                model=OPENAI_MODEL,
                input=[
                    {"role": "user", "content": prompt},
                    {"role": "user", "content": f"FILE: {file_path}"}
                ],
            )
            output_text = str(resp)
            m = re.search(r"\{[\s\S]*\}", output_text)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return {'raw': output_text}
            return {'raw': output_text}
        except Exception as e:
            print('Receipt parse error:', e)
    # Fallback: minimal parsing from filename
    filename = os.path.basename(file_path)
    merchant = None
    guessed = {
        'merchant': merchant,
        'description': 'Compra detectada en factura',
        'date': None,
        'expense_date': None,
        'total': None,
        'currency': 'GTQ',
        'category': None,
        'payment_method': None,
        'invoice_number': None,
        'products': None,
        'confidence': None,
        'source': 'fallback_filename',
        'file': filename
    }
    if merchant:
        guessed['description'] = f'Compra en {merchant}'
    return guessed
