
import os
import json

from openai import OpenAI


# ============================================================
# CONFIGURACIÓN OPENAI
# ============================================================

OPENAI_API_KEY = os.getenv(
    'OPENAI_API_KEY'
)

OPENAI_MODEL = os.getenv(
    'OPENAI_MODEL',
    'gpt-4o-mini'
)

client = (
    OpenAI(api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY
    else None
)


# ============================================================
# TRANSCRIBIR Y ANALIZAR AUDIO
# ============================================================

def transcribe_and_parse(file_path: str) -> dict:
    """
    Procesa un archivo de audio mediante dos etapas:

    1. Transcribe el audio a texto.
    2. Analiza la transcripción con IA para identificar
       los datos financieros de la transacción.

    Devuelve:
        transcript:
            Texto transcrito del audio.

        proposal:
            Datos financieros detectados por la IA.
    Nota: usa la fecha actual del mundo, el presente año, el presente mes y el presente dia si el usuario indicara: compre x ayer, antier o al algo, rectifica que la fecha sea la adecuada
    """

    # --------------------------------------------------------
    # Verificar OpenAI
    # --------------------------------------------------------

    if not client:

        return {
            'error': (
                'OPENAI_API_KEY no está configurada.'
            ),
            'transcript': '',
            'proposal': {}
        }

    # --------------------------------------------------------
    # 1. TRANSCRIPCIÓN
    # --------------------------------------------------------

    text = None

    try:

        print(
            'VOICE: iniciando transcripción...'
        )

        with open(
            file_path,
            'rb'
        ) as audio_file:

            response = client.audio.transcriptions.create(
                file=audio_file,
                model='gpt-4o-transcribe'
            )

        # La respuesta normalmente contiene .text
        text = getattr(
            response,
            'text',
            None
        )

        if text:

            text = text.strip()

        print(
            'VOICE: transcripción completada'
        )

        print(
            'VOICE: texto:',
            text
        )

    except Exception as exc:

        print(
            '===================================='
        )

        print(
            'TRANSCRIPTION ERROR'
        )

        print(
            'Tipo:',
            type(exc).__name__
        )

        print(
            'Error:',
            str(exc)
        )

        print(
            '===================================='
        )

        return {
            'error': (
                'No se pudo transcribir el audio.'
            ),
            'transcript': '',
            'proposal': {}
        }

    # --------------------------------------------------------
    # Verificar transcripción
    # --------------------------------------------------------

    if not text:

        return {
            'error': (
                'No se pudo obtener texto del audio.'
            ),
            'transcript': '',
            'proposal': {}
        }

    # --------------------------------------------------------
    # 2. ANALIZAR TRANSCRIPCIÓN CON IA
    # --------------------------------------------------------

    try:

        print(
            'VOICE: analizando transcripción con IA...'
        )

        instructions = """
Eres un asistente financiero especializado en
registrar movimientos financieros a partir de
información proporcionada por voz.

El usuario ha dicho una frase relacionada con
un gasto, ingreso o movimiento financiero.

Analiza cuidadosamente la transcripción y
extrae todos los datos financieros que puedas
identificar.

No te limites a buscar palabras específicas.
Debes interpretar el significado completo de
lo que dijo el usuario.

Devuelve ÚNICAMENTE un JSON válido.

Utiliza exactamente esta estructura:

{
    "amount": null,
    "currency": "GTQ",
    "merchant": null,
    "description": null,
    "category": null,
    "payment_method": null,
    "expense_date": null,
    "transaction_type": "expense",
    "invoice_number": null,
    "products": [],
    "confidence": 0.0,
    "analysis": null
}

REGLAS:

1. amount:
   Identifica el monto de dinero mencionado.

2. currency:
   Identifica la moneda.
   Si el usuario dice quetzales, Q o GTQ,
   utiliza "GTQ".

3. merchant:
   Identifica el comercio, empresa,
   establecimiento o persona relacionada
   con la transacción cuando se mencione.

4. description:
   Genera una descripción breve y clara
   de la transacción.

5. category:
   Selecciona la categoría financiera más
   apropiada según el significado de la compra.

   Algunas categorías posibles son:
   - Alimentación
   - Supermercado
   - Transporte
   - Educación
   - Salud
   - Entretenimiento
   - Tecnología
   - Hogar
   - Servicios
   - Ropa
   - Compras
   - Otros

   Si existen categorías específicas en la
   información proporcionada por la aplicación,
   intenta utilizar exactamente esos nombres.

6. payment_method:
   Identifica si fue:
   - efectivo
   - tarjeta
   - transferencia
   - débito
   - crédito
   - otro

   Si no se menciona, utiliza null.

7. expense_date:
   Si el usuario menciona una fecha,
   conviértela a formato YYYY-MM-DD.

   Si dice "hoy", utiliza la fecha actual
   disponible para el sistema.

   Si no existe información suficiente,
   utiliza null.

8. transaction_type:

   Utiliza:
   "expense"
   para gastos.

   Utiliza:
   "income"
   para ingresos.

9. invoice_number:
   Si menciona un número de factura,
   recibo o comprobante, extráelo.

10. products:
    Si menciona productos específicos,
    inclúyelos en una lista.

11. confidence:
    Utiliza un número entre 0 y 1 que represente
    tu confianza general en la información extraída.

12. analysis:
    Explica brevemente por qué seleccionaste
    la categoría y cómo interpretaste la
    transacción.

No inventes información.

Si un dato no aparece en la transcripción,
utiliza null.

Si existen varias cantidades, identifica cuál
es el monto total de la transacción.

Si el usuario menciona claramente que recibió
dinero, clasifícalo como "income".

Si claramente gastó dinero, clasifícalo como
"expense".
"""

        user_input = f"""
TRANSCRIPCIÓN DEL USUARIO:

{text}

Analiza esta transcripción y extrae los datos
financieros correspondientes.
"""

        response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=instructions,
            input=user_input
        )

        output_text = (
            response.output_text.strip()
        )

        print(
            'VOICE: análisis recibido'
        )

        # ----------------------------------------------------
        # 3. CONVERTIR RESPUESTA A JSON
        # ----------------------------------------------------

        try:

            proposal = json.loads(
                output_text
            )

        except json.JSONDecodeError:

            print(
                'VOICE: la IA no devolvió JSON puro.'
            )

            # Intentar localizar JSON
            start = output_text.find('{')
            end = output_text.rfind('}')

            if start != -1 and end != -1:

                try:

                    proposal = json.loads(
                        output_text[
                            start:end + 1
                        ]
                    )

                except json.JSONDecodeError:

                    return {
                        'transcript': text,
                        'proposal': {},
                        'error': (
                            'La IA devolvió una respuesta '
                            'que no pudo convertirse a JSON.'
                        ),
                        'raw': output_text
                    }

            else:

                return {
                    'transcript': text,
                    'proposal': {},
                    'error': (
                        'La IA no devolvió información '
                        'estructurada.'
                    ),
                    'raw': output_text
                }

        # ----------------------------------------------------
        # 4. NORMALIZAR CAMPOS
        # ----------------------------------------------------

        proposal.setdefault(
            'amount',
            None
        )

        proposal.setdefault(
            'currency',
            'GTQ'
        )

        proposal.setdefault(
            'merchant',
            None
        )

        proposal.setdefault(
            'description',
            None
        )

        proposal.setdefault(
            'category',
            None
        )

        proposal.setdefault(
            'payment_method',
            None
        )

        proposal.setdefault(
            'expense_date',
            None
        )

        proposal.setdefault(
            'transaction_type',
            'expense'
        )

        proposal.setdefault(
            'invoice_number',
            None
        )

        proposal.setdefault(
            'products',
            []
        )

        proposal.setdefault(
            'confidence',
            None
        )

        proposal.setdefault(
            'analysis',
            None
        )

        # ----------------------------------------------------
        # 5. INFORMACIÓN DE ORIGEN
        # ----------------------------------------------------

        proposal['source'] = (
            'ai_voice_analysis'
        )

        # ----------------------------------------------------
        # 6. RESULTADO FINAL
        # ----------------------------------------------------

        print(
            'VOICE: análisis completado correctamente'
        )

        print(
            'VOICE: propuesta:',
            proposal
        )

        return {
            'transcript': text,
            'proposal': proposal
        }

    except Exception as exc:

        print(
            '===================================='
        )

        print(
            'VOICE AI ANALYSIS ERROR'
        )

        print(
            'Tipo:',
            type(exc).__name__
        )

        print(
            'Error:',
            str(exc)
        )

        print(
            '===================================='
        )

        return {
            'transcript': text,
            'proposal': {},
            'error': str(exc)
        }

