# NEXT42 — Farmer Dashboard Farm Journal UI

## Locked UX
- Main farmer dashboard journal title: **আজকে জমিতে কি কি করলেন এখানে বলুন**
- Journal box is empty; no placeholder/example text.
- Small `🔒 ব্যক্তিগত` label indicates privacy without consuming much space.
- Farmer can type or use microphone voice-to-text.
- No extra shortcut buttons; existing dashboard features remain.

## Flow
1. Farmer writes or speaks naturally.
2. Voice uses browser SpeechRecognition (`bn-BD`) where supported.
3. Dashboard sends the text to `/api/v1/farmer/farm/journal`.
4. Backend parses against existing private farm/plot/crop context.
5. Structured records are stored without deleting historical records.
6. Dashboard refreshes compact farm summary and recent journal history.

## Safety
- Only farmer accounts see the farm journal UI.
- Backend APIs remain authenticated and user-scoped.
- Voice input is converted locally by the browser speech API; the resulting transcript is sent as `voice_transcript`.
- If browser speech recognition is unavailable, the microphone control is hidden and text input remains available.
