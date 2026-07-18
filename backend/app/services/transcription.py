"""Audio file -> speaker-turned transcript, via Mistral Voxtral.

TO IMPLEMENT.
"""

from app.schemas import TranscriptTurn


def transcribe(audio_path: str) -> list[TranscriptTurn]:
    """Transcribe a call recording into speaker turns.

    Implementation spec:
      1. Call Mistral's audio transcription endpoint with
         model=settings.mistral_audio_model and the file at audio_path,
         requesting segment timestamps.
      2. Voxtral transcription does not diarize. Two acceptable strategies —
         pick one and note it in the code:
           a. (good enough for demo) Label every turn speaker='unknown' and
              let the analyzer work from raw text.
           b. (better) One extra Mistral chat call: give it the timestamped
              segments and ask it to label each 'agent' or 'caller' (the
              agent asks the scripted questions), returning JSON.
      3. Map segments to TranscriptTurn(speaker, start, end, text).
      4. Raise RuntimeError on API failure (router maps to 502 and marks the
         call 'failed').
    """
    raise NotImplementedError
