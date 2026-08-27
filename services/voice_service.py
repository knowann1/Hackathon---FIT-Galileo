import os
from openai import OpenAI
from services.ai_service import parse_expense_text

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


def transcribe_and_parse(file_path: str) -> dict:
    """
    Transcribe audio and parse into expense proposal.
    Uses OpenAI speech-to-text when available, otherwise returns fallback.
    """
    text = None
    if client:
        try:
            # SDKs vary; this uses the 'audio.transcriptions' convenience endpoint if available.
            # If your installed SDK uses a different method, adjust accordingly.
            with open(file_path, 'rb') as f:
                resp = client.audio.transcriptions.create(file=f, model='gpt-4o-transcribe')
                # resp may have a 'text' attribute
                text = getattr(resp, 'text', None) or resp.get('text') if isinstance(resp, dict) else None
        except Exception as e:
            print('Transcription error:', e)
    if not text:
        # Fallback: use filename as hint
        text = f"Archivo de audio: {os.path.basename(file_path)}"

    # Parse the transcribed text into an expense proposal
    proposal = parse_expense_text(text)
    return {'transcript': text, 'proposal': proposal}
