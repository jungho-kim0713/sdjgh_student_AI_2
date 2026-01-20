import os
import datetime

from flask import Blueprint, jsonify, request, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import ChatFile, ChatSession
from services.file_service import extract_text_from_file

files_bp = Blueprint("files", __name__)


@files_bp.route("/api/upload_file", methods=["POST"])
@login_required
def upload_file_api():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No file"}), 400
    try:
        filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_name = f"{timestamp}_{filename}"

        is_image = file.content_type.startswith("image/")
        if is_image:
            save_dir = current_app.config["UPLOAD_FOLDER"]
            rel_path = f"uploads/{unique_name}"
        else:
            save_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], "files")
            rel_path = f"uploads/files/{unique_name}"

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        save_path = os.path.join(save_dir, unique_name)

        content = file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        text = ""
        if not is_image:
            text = extract_text_from_file(content, filename)

        new_file = ChatFile(
            user_id=current_user.id,
            filename=filename,
            storage_path=rel_path,
            file_type=file.content_type,
            file_size=len(content),
        )
        db.session.add(new_file)
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "file_id": new_file.id,
                "filename": filename,
                "extracted_text": text,
                "is_image": is_image,
                "storage_path": rel_path,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/api/save_ai_file", methods=["POST"])
@login_required
def save_ai_file_api():
    data = request.json
    try:
        filename = secure_filename(data.get("filename", "code.txt"))
        unique_name = (
            f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_AI_{filename}"
        )
        save_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"], "files", unique_name
        )
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(data.get("content"))
        new_file = ChatFile(
            session_id=data.get("session_id"),
            user_id=current_user.id,
            filename=filename,
            storage_path=f"uploads/files/{unique_name}",
            file_type="text/plain",
            file_size=len(data.get("content")),
            uploaded_by="ai",
        )
        db.session.add(new_file)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/api/view_file/<int:file_id>", methods=["GET"])
@login_required
def view_file_api(file_id):
    f = db.session.get(ChatFile, file_id)
    if not f:
        return jsonify({"error": "Not found"}), 404
    try:
        if f.file_type.startswith("image/"):
            path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], os.path.basename(f.storage_path)
            )
        else:
            path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], "files", os.path.basename(f.storage_path)
            )

        if not os.path.exists(path):
            path = os.path.join(
                current_app.static_folder, f.storage_path.replace("uploads/", "", 1)
            )

        with open(path, "rb") as file:
            content = file.read()
        return jsonify(
            {"success": True, "content": extract_text_from_file(content, f.filename)}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@files_bp.route("/api/download_file/<int:file_id>")
@login_required
def download_file_api(file_id):
    f = db.session.get(ChatFile, file_id)
    if not f:
        return "Not found", 404
    if f.user_id != current_user.id and not current_user.is_admin:
        return "Unauthorized", 403

    path = os.path.join(
        current_app.static_folder, f.storage_path.replace("uploads/", "", 1)
    )
    if not os.path.exists(path):
        if f.file_type.startswith("image/"):
            path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], os.path.basename(f.storage_path)
            )
        else:
            path = os.path.join(
                current_app.config["UPLOAD_FOLDER"], "files", os.path.basename(f.storage_path)
            )

    return send_file(path, as_attachment=True, download_name=f.filename)


@files_bp.route("/api/get_session_files/<int:session_id>")
@login_required
def get_session_files(session_id):
    files = ChatFile.query.filter_by(session_id=session_id).all()
    if files and files[0].user_id != current_user.id and not current_user.is_admin:
        return jsonify([])
    return jsonify(
        [
            {
                "id": f.id,
                "filename": f.filename,
                "uploaded_by": f.uploaded_by,
                "is_image": f.file_type.startswith("image/"),
            }
            for f in files
        ]
    )


@files_bp.route("/api/get_my_files")
@login_required
def get_my_files():
    files = (
        ChatFile.query.filter_by(user_id=current_user.id)
        .order_by(ChatFile.timestamp.desc())
        .all()
    )
    result = []
    for f in files:
        session_title = "연결 끊김"
        if f.session_id:
            s = db.session.get(ChatSession, f.session_id)
            if s:
                session_title = s.title
        result.append(
            {
                "id": f.id,
                "filename": f.filename,
                "is_image": f.file_type.startswith("image/"),
                "uploaded_by": f.uploaded_by,
                "timestamp": f.timestamp.strftime("%Y-%m-%d %H:%M"),
                "session_title": session_title,
            }
        )
    return jsonify(result)
