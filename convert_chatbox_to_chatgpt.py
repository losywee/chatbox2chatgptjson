#!/usr/bin/env python3

import argparse
import json
import uuid
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a Chatbox export JSON file into ChatGPT conversations.json format."
    )
    parser.add_argument("input", help="Path to the Chatbox export JSON file")
    parser.add_argument(
        "-o",
        "--output",
        default="conversations.json",
        help="Path to the output ChatGPT conversations JSON file",
    )
    return parser.parse_args()


def ms_to_seconds(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value / 1000.0 if value > 10_000_000_000 else float(value)
    return None


def extract_parts(message: dict) -> list[str]:
    parts = []
    for part in message.get("contentParts") or []:
        if isinstance(part, dict) and part.get("type") == "text":
            text = part.get("text")
            if text is not None:
                parts.append(str(text))
        elif isinstance(part, str):
            parts.append(part)

    if parts:
        return parts

    content = message.get("content")
    if content is None:
        return [""]
    if isinstance(content, list):
        return [str(item) for item in content]
    return [str(content)]


def build_message_node(message: dict, parent_id: str) -> tuple[str, dict]:
    message_id = str(message.get("id") or uuid.uuid4())
    role = message.get("role") or "user"
    create_time = ms_to_seconds(message.get("timestamp"))

    metadata = {}
    if message.get("model"):
        metadata["model_slug"] = message["model"]
    if message.get("aiProvider"):
        metadata["chatbox_ai_provider"] = message["aiProvider"]
    if message.get("status"):
        metadata["chatbox_status"] = message["status"]
    if message.get("wordCount") is not None:
        metadata["chatbox_word_count"] = message["wordCount"]
    if message.get("tokenCount") is not None:
        metadata["chatbox_token_count"] = message["tokenCount"]
    if message.get("tokensUsed") is not None:
        metadata["chatbox_tokens_used"] = message["tokensUsed"]

    node = {
        "id": message_id,
        "message": {
            "id": message_id,
            "author": {
                "role": role,
                "name": None,
                "metadata": {},
            },
            "create_time": create_time,
            "update_time": None,
            "content": {
                "content_type": "text",
                "parts": extract_parts(message),
            },
            "status": "finished_successfully",
            "end_turn": role != "system",
            "weight": 1.0,
            "metadata": metadata,
            "recipient": "all",
        },
        "parent": parent_id,
        "children": [],
    }
    return message_id, node


def build_conversation(session: dict) -> dict:
    root_id = str(uuid.uuid4())
    mapping = {
        root_id: {
            "id": root_id,
            "message": None,
            "parent": None,
            "children": [],
        }
    }

    parent_id = root_id
    first_time = None
    last_time = None

    for raw_message in session.get("messages") or []:
        message_id, node = build_message_node(raw_message, parent_id)
        mapping[message_id] = node
        mapping[parent_id]["children"].append(message_id)
        parent_id = message_id

        message_time = node["message"]["create_time"]
        if message_time is not None:
            if first_time is None:
                first_time = message_time
            last_time = message_time

    return {
        "title": session.get("name") or "Untitled",
        "create_time": first_time,
        "update_time": last_time,
        "mapping": mapping,
        "moderation_results": [],
        "current_node": parent_id,
        "plugin_ids": None,
        "conversation_id": session.get("id") or str(uuid.uuid4()),
        "conversation_template_id": None,
        "gizmo_id": None,
        "is_archived": False,
        "safe_urls": [],
        "blocked_urls": [],
        "default_model_slug": None,
        "voice": None,
        "async_status": None,
        "disabled_tool_ids": [],
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    export_data = json.loads(input_path.read_text(encoding="utf-8"))
    conversations = []

    for key in sorted(export_data):
        if key.startswith("session:"):
            conversations.append(build_conversation(export_data[key]))

    output_path.write_text(
        json.dumps(conversations, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Converted {len(conversations)} conversations to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
