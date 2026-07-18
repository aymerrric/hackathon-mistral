"""Unit tests for the voice agent's pure tree-walking logic and the Twilio
webhook TwiML (no DB, no Mistral calls)."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.voice_agent import speech_of, walk_entry, walk_option

STRUCTURE = {
    "root_id": "n1",
    "nodes": {
        "n1": {
            "id": "n1", "type": "action", "label": "Greet",
            "prompt": "Say: 'Welcome to support.'",
            "options": [{"label": "Continue", "next_id": "n2"}],
        },
        "n2": {
            "id": "n2", "type": "question", "label": "Emergency?",
            "prompt": "Ask: 'Is anyone in danger?'",
            "options": [
                {"label": "Yes", "next_id": "n3"},
                {"label": "No", "next_id": "n4"},
            ],
        },
        "n3": {
            "id": "n3", "type": "end", "label": "Dispatch",
            "prompt": "Say: 'Help is on the way.'", "options": [],
        },
        "n4": {
            "id": "n4", "type": "action", "label": "Verify",
            "prompt": "Verify the caller's account number.",
            "options": [{"label": "Continue", "next_id": "n5"}],
        },
        "n5": {
            "id": "n5", "type": "end", "label": "Done",
            "prompt": "Close the call politely.", "options": [],
        },
    },
}


def test_speech_of_strips_meta_prefix_and_quotes():
    assert speech_of("Ask: 'Is anyone in danger?'") == "Is anyone in danger?"
    assert speech_of('Say: "Welcome to support."') == "Welcome to support."
    assert speech_of("Verify the caller's account number.") == (
        "Verify the caller's account number."
    )


def test_walk_entry_chains_actions_until_question():
    entries, lines, landing, ends = walk_entry(STRUCTURE, "n1")
    assert entries == [{"node_id": "n1", "option_index": 0}]
    assert lines == ["Say: 'Welcome to support.'", "Ask: 'Is anyone in danger?'"]
    assert landing == "n2"
    assert ends is False


def test_walk_option_direct_to_end():
    entries, lines, landing, ends = walk_option(STRUCTURE, "n2", 0)
    assert entries == [{"node_id": "n2", "option_index": 0}]
    assert landing == "n3"
    assert ends is True


def test_walk_option_through_action_to_end():
    entries, lines, landing, ends = walk_option(STRUCTURE, "n2", 1)
    assert entries == [
        {"node_id": "n2", "option_index": 1},
        {"node_id": "n4", "option_index": 0},
    ]
    assert lines == ["Verify the caller's account number.", "Close the call politely."]
    assert landing == "n5"
    assert ends is True


def test_twilio_webhook_returns_stream_twiml():
    client = TestClient(app)
    res = client.post(
        "/api/twilio/voice?tree_id=00000000-0000-0000-0000-000000000000",
        data={"From": "+33612345678"},
        headers={"host": "example.ngrok.app"},
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/xml")
    body = res.text
    assert '<Stream url="wss://example.ngrok.app/api/twilio/media">' in body
    assert '<Parameter name="tree_id" value="00000000-0000-0000-0000-000000000000"/>' in body
    assert '<Parameter name="caller" value="+33612345678"/>' in body
