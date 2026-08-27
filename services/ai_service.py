import os
import re
from openai import OpenAI

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def parse_expense_text(text: str) -> dict:
    """
    Sends the text to OpenAI to extract a structured expense proposal.
    Returns a dictionary proposal but does NOT save to DB.
    If OpenAI is not configured, fall back to a simple heuristic.
    """
    if not text:
        return {}

    # Try calling OpenAI structured response if available
    if client:
        try:
            prompt = f"Extrae en JSON la información de este gasto en Guatemala (quetzales/Q): \n\n'{text}'\n\nCampos: amount, currency, merchant, description, category, payment_method, expense_date. Si no aparece un campo, usar null. Devuelve SOLO JSON."
            resp = client.responses.create(
                model=OPENAI_MODEL,
                input=prompt,
            )
            # The new SDK returns content in different places; try to parse.
            # Attempt to find JSON in output_text
            output_text = ''
            try:
                for item in resp.output:
                    if hasattr(item, 'content'):
                        output_text += item.content if isinstance(item.content, str) else str(item.content)
                    elif isinstance(item, dict):
                        output_text += str(item)
            except Exception:
                output_text = str(resp)
            # Extract JSON-like substring
            m = re.search(r"\{[\s\S]*\}", output_text)
            if m:
                import json
                try:
                    return json.loads(m.group(0))
                except Exception:
                    # fallback: return raw text
                    return {'raw': output_text}
            return {'raw': output_text}
        except Exception as e:
            # Do not crash — fallback to heuristic
            print('OpenAI parse error:', e)

    # Heuristic fallback
    amount = None
    currency = 'GTQ'
    merchant = None
    payment_method = None
    date = None
    category = None
    description = None

    lower_text = text.lower()

    # amount detection (numbers)
    m = re.search(r"(\d+[\.,]?\d*)\s*(quetzales|Q|gtq|GTQ)?", text)
    if m:
        try:
            amount = float(m.group(1).replace(',', '.'))
        except Exception:
            amount = None

    # date detection
    for pattern in [r"(\d{4}-\d{2}-\d{2})", r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", r"(\d{1,2}\s+de\s+[A-Za-z]+\s+de\s+\d{4})"]:
        m_date = re.search(pattern, text, flags=re.IGNORECASE)
        if m_date:
            date = m_date.group(1).strip()
            break

    # merchant heuristic: proper nouns
    m2 = re.search(r"(?:en|en la|en el|en los|en las)\s+([A-Za-z0-9áéíóúüñÁÉÍÓÚÜÑ\s]+?)(?=\s+(?:por\s+Q|por\s+\d|con\s+|el\s+\d{1,2}|$))", text, flags=re.IGNORECASE)
    if m2:
        merchant = m2.group(1).strip()
    if not merchant:
        for keyword in ['walmart', 'puma', 'pizza hut', 'cafeteria', 'super', 'farmacia', 'ferreteria', 'bodega', 'taco', 'mercado']:
            if keyword in lower_text:
                merchant = keyword.title()
                break

    if 'tarjeta' in lower_text:
        payment_method = 'Tarjeta de crédito/debito'
    if 'efectivo' in lower_text:
        payment_method = 'Efectivo'
    if 'gasolina' in lower_text:
        category = 'Transporte'
    if 'walmart' in lower_text or 'super' in lower_text:
        category = 'Supermercado'

    if not description:
        if merchant:
            description = f"Compra en {merchant}"
        elif amount is not None:
            description = 'Gasto detectado'
        else:
            description = 'Gasto registrado'

    return {
        'amount': amount,
        'currency': currency,
        'merchant': merchant,
        'description': description,
        'category': category,
        'payment_method': payment_method,
        'expense_date': date,
        'proposal_source': 'heuristic'
    }


def analyze_finances_with_ai(summary: dict) -> dict:
    """
    Given a numeric summary (prepared by Python), optionally call OpenAI to produce
    human-readable insights and recommendations. If OpenAI is not configured, return
    a simple interpretation based on the summary.
    """
    if not summary:
        return {'insights': []}

    # If OpenAI is available, send the summary and ask for JSON insights
    if client:
        try:
            import json
            prompt = (
                "Tienes el siguiente resumen financiero (en JSON). Genera una lista JSON llamada 'insights' "
                "con objetos que contengan: type (warning/info/alert), title, description y recommendation. "
                "No inventes datos, usa únicamente lo que esté en el resumen. Responde solo JSON.\n\n"
                f"Resumen:\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n"
            )
            resp = client.responses.create(
                model=OPENAI_MODEL,
                input=prompt
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
            print('OpenAI analyze error:', e)

    # Fallback: basic textual insights
    insights = []
    if summary.get('expense_growth_percentage') and summary['expense_growth_percentage'] > 0:
        insights.append({
            'type': 'info',
            'title': 'Variación de gastos',
            'description': f"Tus gastos variaron {summary['expense_growth_percentage']}% respecto al mes anterior.",
            'recommendation': 'Revisa categorías con mayor crecimiento y ajusta presupuestos.'
        })
    if summary.get('expense_by_category'):
        top = sorted(summary['expense_by_category'].items(), key=lambda x: x[1], reverse=True)[:3]
        top_str = ', '.join([f"{k} (Q{v})" for k, v in top])
        insights.append({
            'type': 'info',
            'title': 'Principales categorías',
            'description': f"Las categorías principales son: {top_str}.",
            'recommendation': 'Considera establecer límites semanales en estas categorías.'
        })
    return {'insights': insights}


def simulate_savings(amount: float, months=[1,6,12,24]) -> dict:
    months = sorted(list(set(int(m) for m in months)))
    result = {}
    for m in months:
        result[str(m)] = round(amount * m, 2)
    return {
        'monthly_amount': float(amount),
        'projections': result
    }
