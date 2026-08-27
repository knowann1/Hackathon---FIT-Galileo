import os
import json
import base64
from openai import OpenAI

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def parse_receipt_image(file_path: str) -> dict:
    """
    Analiza una imagen de una factura o recibo utilizando OpenAI.

    La IA lee directamente la imagen y extrae:
    - comercio
    - descripción
    - fecha
    - total
    - moneda
    - categoría
    - método de pago
    - número de factura
    - productos
    - confianza

    El resultado se devuelve como un diccionario para que
    posteriormente pueda ser revisado y confirmado por el usuario
    antes de guardar el gasto.
    """

    if not client:
        return {
            'error': 'OPENAI_API_KEY no está configurada.'
        }

    try:

        # ----------------------------------------------------
        # 1. Leer la imagen
        # ----------------------------------------------------

        with open(file_path, 'rb') as image_file:
            image_bytes = image_file.read()

        # ----------------------------------------------------
        # 2. Convertir imagen a Base64
        # ----------------------------------------------------

        base64_image = base64.b64encode(
            image_bytes
        ).decode('utf-8')

        # ----------------------------------------------------
        # 3. Detectar tipo de imagen
        # ----------------------------------------------------

        extension = os.path.splitext(
            file_path
        )[1].lower()

        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp'
        }

        mime_type = mime_types.get(
            extension,
            'image/jpeg'
        )

        # ----------------------------------------------------
        # 4. Prompt para analizar la factura
        # ----------------------------------------------------

        prompt = """
Analiza cuidadosamente la factura o recibo de la imagen.

Tu objetivo es extraer la información necesaria para registrar
correctamente una transacción financiera.

Lee directamente el contenido visible de la imagen.

Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura:

{
    "merchant": "",
    "description": "",
    "date": "",
    "expense_date": "",
    "total": null,
    "currency": "GTQ",
    "category": "",
    "payment_method": "",
    "invoice_number": "",
    "products": [],
    "confidence": 0.0
}

REGLAS:

- merchant: nombre del comercio o establecimiento.
- description: descripción breve de la compra.
- date: fecha que aparece en la factura.
- expense_date: utiliza el formato YYYY-MM-DD cuando sea posible.
- total: monto TOTAL pagado, no el subtotal.
- currency: moneda utilizada. Si no puede determinarse,
  utiliza "GTQ" únicamente si existe suficiente evidencia.
- category: clasifica la compra en una categoría financiera
  razonable como alimentación, transporte, supermercado,
  entretenimiento, educación, salud, tecnología, hogar,
  servicios u otra categoría apropiada.
- payment_method: efectivo, tarjeta, transferencia, etc.,
  solamente si aparece o puede identificarse claramente.
- invoice_number: número de factura si aparece.
- products: lista de productos identificados. Cada producto
  debe incluir nombre, cantidad y precio cuando estén disponibles.
- confidence: número entre 0 y 1 que represente tu confianza
  general en los datos extraídos.

Si un dato no aparece o no puede determinarse con seguridad,
utiliza null.

No inventes información.

Si existen varios totales, identifica cuidadosamente cuál
corresponde al TOTAL realmente pagado.

Si la imagen no corresponde a una factura o recibo,
devuelve igualmente el JSON utilizando null en los campos
que no puedan determinarse.
"""

        # ----------------------------------------------------
        # 5. Enviar imagen + instrucciones a OpenAI
        # ----------------------------------------------------

        response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                f"data:{mime_type};base64,"
                                f"{base64_image}"
                            )
                        }
                    ]
                }
            ]
        )

        # ----------------------------------------------------
        # 6. Obtener texto de respuesta
        # ----------------------------------------------------

        output_text = response.output_text.strip()

        # ----------------------------------------------------
        # 7. Convertir respuesta JSON
        # ----------------------------------------------------

        try:

            result = json.loads(
                output_text
            )

        except json.JSONDecodeError:

            # Intentar encontrar JSON dentro de la respuesta
            start = output_text.find('{')
            end = output_text.rfind('}')

            if start != -1 and end != -1:

                result = json.loads(
                    output_text[start:end + 1]
                )

            else:

                return {
                    'error': 'La IA no devolvió un JSON válido.',
                    'raw': output_text
                }

        # ----------------------------------------------------
        # 8. Normalizar campos
        # ----------------------------------------------------

        result.setdefault(
            'merchant',
            None
        )

        result.setdefault(
            'description',
            None
        )

        result.setdefault(
            'date',
            None
        )

        result.setdefault(
            'expense_date',
            None
        )

        result.setdefault(
            'total',
            None
        )

        result.setdefault(
            'currency',
            'GTQ'
        )

        result.setdefault(
            'category',
            None
        )

        result.setdefault(
            'payment_method',
            None
        )

        result.setdefault(
            'invoice_number',
            None
        )

        result.setdefault(
            'products',
            []
        )

        result.setdefault(
            'confidence',
            None
        )

        # ----------------------------------------------------
        # 9. Indicar origen
        # ----------------------------------------------------

        result['source'] = 'ai_receipt_analysis'
        if result.get('total') is not None:
            result['amount'] = result['total']
        else:
            result['amount'] = None
        
        # Una factura/recibo normalmente representa un gasto
        if not result.get('transaction_type'):
            result['transaction_type'] = 'expense'
        
        return result

    except Exception as e:

        print(
            'Receipt parse error:',
            type(e).__name__,
            str(e)
        )

        return {
            'error': str(e),
            'source': 'ai_receipt_error'
        }
