#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
import email
from email import policy
import urllib.parse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DB_FILE = os.path.join(DATA_DIR, "database.json")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

INITIAL_DATA = {
    "assignments": [
        {
            "id": "HW01",
            "title": "Bài tập Quy hoạch động & Hàm sinh",
            "subject": "Toán học",
            "deadline": "2026-11-30T23:59",
            "maxScore": 10,
            "description": "Trình bày lời giải chi tiết các bài toán tổ hợp và truy hồi. Có thể gõ trực tiếp hoặc đính kèm tệp."
        },
        {
            "id": "HW02",
            "title": "Thuật toán đồ thị & Cấu trúc dữ liệu",
            "subject": "Tin học",
            "deadline": "2026-12-05T20:00",
            "maxScore": 10,
            "description": "Viết mã nguồn giải bài toán đường đi ngắn nhất, kèm giải thích độ phức tạp thời gian."
        }
    ],
    "submissions": []
}


def load_db():
    if not os.path.exists(DB_FILE):
        save_db(INITIAL_DATA)
        return json.loads(json.dumps(INITIAL_DATA))
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_json(payload, status="200 OK"):
    print(f"Status: {status}")
    print("Content-Type: application/json; charset=utf-8")
    print()
    print(json.dumps(payload, ensure_ascii=False))
    sys.exit(0)


def parse_multipart():
    content_type = os.environ.get("CONTENT_TYPE", "")
    content_length = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
    raw_body = sys.stdin.buffer.read(content_length)

    headers_bytes = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    )
    msg = email.message_from_bytes(headers_bytes + raw_body, policy=policy.default)

    fields = {}
    file_info = None

    if msg.is_multipart():
        for part in msg.iter_parts():
            disposition = part.get_content_disposition()
            if disposition == "form-data":
                name = part.get_param("name", header="content-disposition")
                filename = part.get_filename()
                payload_bytes = part.get_payload(decode=True) or b""
                if filename:
                    file_info = {
                        "field": name,
                        "filename": filename,
                        "data": payload_bytes,
                    }
                elif name is not None:
                    charset = part.get_content_charset() or "utf-8"
                    fields[name] = payload_bytes.decode(charset, errors="replace")

    return fields, file_info


def main():
    method = os.environ.get("REQUEST_METHOD", "GET").upper()
    query_string = os.environ.get("QUERY_STRING", "")
    params = urllib.parse.parse_qs(query_string)
    action = params.get("action", [""])[0]

    db = load_db()

    if method == "GET" and action == "get_all":
        send_json({"status": "success", "data": db})

    elif method == "POST" and action == "create_assignment":
        content_length = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
        body = sys.stdin.read(content_length) if content_length > 0 else "{}"
        payload = json.loads(body or "{}")

        new_hw = {
            "id": f"HW{int(time.time() * 1000)}",
            "title": str(payload.get("title", "Bài tập mới")).strip(),
            "subject": str(payload.get("subject", "Chung")).strip(),
            "deadline": str(payload.get("deadline", "")).strip(),
            "maxScore": float(payload.get("maxScore", 10) or 10),
            "description": str(payload.get("description", "")).strip(),
        }
        db["assignments"].insert(0, new_hw)
        save_db(db)
        send_json({"status": "success", "assignment": new_hw})

    elif method == "POST" and action == "submit_homework":
        fields, file_info = parse_multipart()
        hw_id = fields.get("hw_id", "").strip()
        student_name = fields.get("student_name", "").strip() or "Học sinh"
        student_class = fields.get("student_class", "").strip() or "12"
        content_text = fields.get("content_text", "").strip()

        saved_filename = ""
        if file_info and file_info["filename"]:
            safe_base = os.path.basename(file_info["filename"]).replace("..", "_")
            saved_filename = f"{int(time.time())}_{safe_base}"
            out_path = os.path.join(UPLOAD_DIR, saved_filename)
            with open(out_path, "wb") as f:
                f.write(file_info["data"])

        existing = next(
            (
                s
                for s in db["submissions"]
                if s["hw_id"] == hw_id
                and s["student_name"].lower() == student_name.lower()
            ),
            None,
        )

        sub_record = {
            "id": existing["id"] if existing else f"SUB{int(time.time() * 1000)}",
            "hw_id": hw_id,
            "student_name": student_name,
            "student_class": student_class,
            "content_text": content_text,
            "file_name": saved_filename
            if saved_filename
            else (existing["file_name"] if existing else ""),
            "submitted_at": time.strftime("%H:%M %d/%m/%Y"),
            "score": existing["score"] if existing else None,
            "feedback": existing["feedback"] if existing else "",
        }

        if existing:
            db["submissions"] = [
                sub_record if s["id"] == existing["id"] else s
                for s in db["submissions"]
            ]
        else:
            db["submissions"].insert(0, sub_record)

        save_db(db)
        send_json({"status": "success", "submission": sub_record})

    elif method == "POST" and action == "grade_submission":
        content_length = int(os.environ.get("CONTENT_LENGTH", "0") or "0")
        body = sys.stdin.read(content_length) if content_length > 0 else "{}"
        payload = json.loads(body or "{}")
        sub_id = payload.get("sub_id")
        raw_score = payload.get("score")
        score_val = None if raw_score in (None, "") else float(raw_score)
        feedback_val = str(payload.get("feedback", "")).strip()

        for s in db["submissions"]:
            if s["id"] == sub_id:
                s["score"] = score_val
                s["feedback"] = feedback_val
                break

        save_db(db)
        send_json({"status": "success"})

    else:
        send_json(
            {"status": "error", "message": "Unsupported CGI endpoint or action"},
            status="400 Bad Request",
        )


if __name__ == "__main__":
    main()