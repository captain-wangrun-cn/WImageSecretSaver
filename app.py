"""
Author: WR(captain-wangrun-cn)
Date: 2026-01-25 18:09:16
LastEditors: WR(captain-wangrun-cn)
LastEditTime: 2026-01-31 13:16:32
FilePath: /WImageSecretSaver/app.py
"""

from flask import Flask, request, jsonify
import os
import utils
import asyncio
import time
import random
import pymysql
from collections import defaultdict
from threading import Lock


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB 最大上传大小限制
access_key = ""
password = ""
path = ""
db_config = {}

# 速率限制配置
rate_limit_requests = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))  # 每分钟最多请求数
rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))  # 时间窗口（秒）
rate_limit_storage = defaultdict(list)
rate_limit_lock = Lock()


def get_db_conn():
    return pymysql.connect(**db_config)


def check_rate_limit():
    """检查当前请求是否超过速率限制"""
    ip = request.remote_addr
    current_time = time.time()

    with rate_limit_lock:
        # 清理过期记录
        rate_limit_storage[ip] = [
            t
            for t in rate_limit_storage[ip]
            if current_time - t < rate_limit_window
        ]

        # 检查是否超限
        if len(rate_limit_storage[ip]) >= rate_limit_requests:
            return False

        # 记录本次请求
        rate_limit_storage[ip].append(current_time)
        return True


@app.before_request
async def rate_limit_middleware():
    """全局速率限制中间件"""
    if not check_rate_limit():
        return jsonify({"error": "请求过于频繁，请稍后再试"}), 429


@app.route("/")
async def hello():
    return "WISS"


@app.route("/images", methods=["GET", "POST", "PUT", "DELETE"])
async def images():
    global access_key, password, path

    if (
        request.headers.get("Access-Key") != access_key
        and request.args.get("access_key") != access_key
    ):
        return jsonify({"error": "无效的访问密钥"}), 403

    if request.method in ["POST", "PUT"]:
        # 上传图片或更新图片
        if "file" not in request.files:
            return jsonify({"error": "未找到文件部分"}), 400

        _path = request.args.get("path", "")
        if _path:
            full_path = os.path.join(path, _path)
            if not os.path.exists(full_path):
                await asyncio.to_thread(os.makedirs, full_path)
        else:
            full_path = path

        file = request.files.get("file")
        if file.filename == "":
            file.filename = utils.get_time_str() + ".png"

        # 流式读取上传体，避免一次性读入内存
        t_read = time.perf_counter()
        chunks = bytearray()
        while True:
            part = await asyncio.to_thread(file.stream.read, 65536)
            if not part:
                break
            chunks.extend(part)
        file_data = bytes(chunks)
        read_ms = (time.perf_counter() - t_read) * 1000

        t_enc = time.perf_counter()
        encrypted_data = utils.encrypt_image(file_data, password)
        encrypt_ms = (time.perf_counter() - t_enc) * 1000
        app.logger.info(
            f"Read cost: {read_ms:.2f} ms, Encrypt cost: {encrypt_ms:.2f} ms, file={file.filename}"
        )
        print(
            f"Read cost: {read_ms:.2f} ms, Encrypt cost: {encrypt_ms:.2f} ms, file={file.filename}"
        )
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

        if request.args.get("stream") == "1":
            # 返回图片，而不是下载
            return app.response_class(
                response=image_data, status=200, mimetype="image/png"
            )

        response = app.response_class(
            response=image_data, status=200, mimetype="application/octet-stream"
        )
        response.headers.set("Content-Disposition", "attachment", filename=filename)
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


@app.route("/images/random", methods=["GET"])
async def random_image():
    global access_key, password, path
    if (
        request.headers.get("Access-Key") != access_key
        and request.args.get("access_key") != access_key
    ):
        return jsonify({"error": "无效的访问密钥"}), 403

    meta_only = request.args.get("meta") == "1"
    ratio = request.args.get("ratio")
    if ratio:
        try:
            def get_db_random(r):
                # 使用全局配置连接数据库
                conn = get_db_conn()
                try:
                    with conn.cursor() as cur:
                        if r in ["v", "vertical"]:
                            cond = "height > width"
                        elif r in ["h", "horizontal"]:
                            cond = "width > height"
                        elif r in ["s", "square"]:
                            cond = "width = height"
                        else:
                            cond = "1=1"
                        cur.execute(f"SELECT filepath, filename FROM images WHERE {cond} ORDER BY RAND() LIMIT 1")
                        return cur.fetchone()
                finally:
                    conn.close()

            row = await asyncio.to_thread(get_db_random, ratio)
            if not row:
                return jsonify({"error": "未找到符合比例的图片"}), 404
            file_path = os.path.join(path, row["filepath"], row["filename"])
            if not os.path.exists(file_path):
                return jsonify({"error": "文件不存在"}), 404

            if meta_only:
                rel_full = os.path.join(row["filepath"], row["filename"])
                return jsonify({
                    "filename": row["filename"],
                    "filepath": row["filepath"],
                    "fullpath": rel_full.replace("\\", "/")
                }), 200

            encrypted_data = await asyncio.to_thread(open(file_path, "rb").read)

            try:
                image_data = utils.decrypt_image(encrypted_data, password)
            except Exception as e:
                return jsonify({"error": "解密失败", "details": str(e)}), 500

            if request.args.get("stream") == "1":
                # 返回图片，而不是下载
                return app.response_class(
                    response=image_data,
                    status=200,
                    mimetype='image/png'
                )
            response = app.response_class(
                response=image_data, status=200, mimetype="application/octet-stream"
            )
            response.headers.set("Content-Disposition", "attachment", filename=row["filename"])
            return response
        except Exception as e:
            return jsonify({"error": "数据库查询出错", "details": str(e)}), 500

    _path = request.args.get("path", "")
    full_path = os.path.join(path, _path) if _path else path
    if not os.path.exists(full_path):
        return jsonify({"error": "路径不存在"}), 404

    def collect_files():
        files = []
        for root, _, filenames in os.walk(full_path):
            for name in filenames:
                files.append((root, name))
        return files

    files = await asyncio.to_thread(collect_files)
    if not files:
        return jsonify({"error": "未找到文件"}), 404

    root, name = random.choice(files)
    file_path = os.path.join(root, name)
    if meta_only:
        rel_path = os.path.relpath(file_path, path)
        return jsonify({
            "filename": name,
            "filepath": os.path.dirname(rel_path).replace("\\", "/"),
            "fullpath": rel_path.replace("\\", "/")
        }), 200

    encrypted_data = await asyncio.to_thread(open(file_path, "rb").read)

    try:
        image_data = utils.decrypt_image(encrypted_data, password)
    except Exception as e:
        return jsonify({"error": "解密失败", "details": str(e)}), 500

    if request.args.get("stream") == "1":
        # 返回图片，而不是下载
        return app.response_class(
            response=image_data,
            status=200,
            mimetype='image/png'
        )

    response = app.response_class(
        response=image_data, status=200, mimetype="application/octet-stream"
    )
    response.headers.set("Content-Disposition", "attachment", filename=name)
    return response


@app.route("/get_image/<path:fullpath>")
async def get_image(fullpath):
    global access_key, password, path

    parts = fullpath.strip("/").split("/")

    if len(parts) < 2:
        return jsonify({"error": "路径格式错误"}), 400

    filename = parts[-1]
    if not filename:
        return jsonify({"error": "缺少文件名参数"}), 400

    _path = os.path.join(*parts[:-1])
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

    return app.response_class(response=image_data, status=200, mimetype="image/png")


if __name__ == "__main__":
    access_key = os.getenv("WISS_ACCESS_KEY", "default_access_key")
    password = os.getenv("WISS_PASSWORD", "sYs7vNj6es4EWpsm")
    path = os.getenv("WISS_STORAGE_PATH", "./images")

    # 初始化数据库配置
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASS", ""),
        "database": os.getenv("DB_NAME", "wiss"),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor
    }

    # 尝试连接一次以验证配置
    try:
        test_conn = get_db_conn()
        test_conn.close()
        print("Database connection check passed.")
    except Exception as e:
        print(f"Database connection warning: {e}")

    if not os.path.exists(path):
        os.makedirs(path)

    app.run(host="0.0.0.0", port=5555)
