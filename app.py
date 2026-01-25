'''
Author: WR(captain-wangrun-cn)
Date: 2026-01-25 18:09:16
LastEditors: WR(captain-wangrun-cn)
LastEditTime: 2026-01-25 20:21:35
FilePath: /WImageSecretSaver/app.py
'''
from flask import Flask, request, jsonify
import os
import utils
import asyncio


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB 最大上传大小限制
access_key = ""
password = ""
path = ""


@app.route("/")
async def hello():
    return "WISS"

@app.route("/images", methods=["GET", "POST", "PUT", "DELETE"])
async def images():
    global access_key, password, path

    if request.headers.get("Access-Key") != access_key:
        return jsonify({"error": "无效的访问密钥"}), 403

    if request.method in ["POST", "PUT"]:
        # 上传图片或更新图片
        if 'file' not in request.files:
            return jsonify({"error": "未找到文件部分"}), 400

        _path = request.args.get("path", "")
        if _path:
            full_path = os.path.join(path, _path)
            if not os.path.exists(full_path):
                await asyncio.to_thread(os.makedirs, full_path)
        else:
            full_path = path

        file = request.files.get("file")
        if file.filename == '':
            file.filename = utils.get_time_str()+".png"

        file_data = await asyncio.to_thread(file.read)
        encrypted_data = utils.encrypt_image(file_data, password)
        file_path = os.path.join(full_path, file.filename)
        async with asyncio.Lock():
            await asyncio.to_thread(open(file_path, "wb").write, encrypted_data)

        return jsonify({"message": "文件已保存", "filename": file.filename}), 200

    elif request.method == "GET":
        # 获取并解密图片
        filename = request.args.get("filename")
        if not filename:
            return jsonify({"error": "缺少文件名参数"}), 400

        _path = request.args.get("path", "")
        if _path:
            full_path = os.path.join(path, _path)
        else:
            full_path = path
        file_path = os.path.join(full_path, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "文件不存在"}), 404

        encrypted_data = await asyncio.to_thread(open(file_path, "rb").read)

        try:
            image_data = utils.decrypt_image(encrypted_data, password)
        except Exception as e:
            return jsonify({"error": "解密失败", "details": str(e)}), 500

        response = app.response_class(
            response=image_data,
            status=200,
            mimetype='application/octet-stream'
        )
        response.headers.set('Content-Disposition', 'attachment', filename=filename)
        return response
    
    elif request.method == "DELETE":
        # 删除图片
        filename = request.args.get("filename")
        if not filename:
            return jsonify({"error": "缺少文件名参数"}), 400

        _path = request.args.get("path", "")
        if _path:
            full_path = os.path.join(path, _path)
        else:
            full_path = path
        file_path = os.path.join(full_path, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "文件不存在"}), 404

        await asyncio.to_thread(os.remove, file_path)
        return jsonify({"message": "文件已删除", "filename": filename}), 200
    else:
        return jsonify({"error": "不支持的HTTP方法"}), 405


if __name__ == "__main__":
    access_key = os.getenv("WISS_ACCESS_KEY", "default_access_key")
    password = os.getenv("WISS_PASSWORD", "sYs7vNj6es4EWpsm")
    path = os.getenv("WISS_STORAGE_PATH", "./images")
    if not os.path.exists(path):
        os.makedirs(path)

    app.run(host="0.0.0.0", port=5555)
