'''
Author: WR(captain-wangrun-cn)
Date: 2026-01-25 18:44:44
LastEditors: WR(captain-wangrun-cn)
LastEditTime: 2026-01-25 20:17:24
FilePath: /WImageSecretSaver/test.py
'''
import requests
import sys

base_url = "http://127.0.0.1:5555/images"
access_key = "default_access_key"

def upload():
    with open("test_image.png", "rb") as f:
        file_data = f.read()
    # 上传图片
    files = {'file': ('test_image.png', file_data)}
    headers = {"Access-Key": access_key}
    response = requests.post(base_url, files=files, headers=headers, params={"path": "test_folder"})
    print(response.json())

def download():
    params = {"filename": "test_image.png", "path": "test_folder"}
    headers = {"Access-Key": access_key}
    response = requests.get(base_url, params=params, headers=headers)
    if response.status_code == 200:
        with open("downloaded_image.png", "wb") as f:
            f.write(response.content)
        print("图片下载并保存为 downloaded_image.png")
    else:
        print(response.json())

def delete():
    params = {"filename": "test_image.png", "path": "test_folder"}
    headers = {"Access-Key": access_key}
    response = requests.delete(base_url, params=params, headers=headers)
    print(response.json())

if __name__ == "__main__":
    method = sys.argv[1]
    if method == "upload":
        upload()
    elif method == "download":
        download()
    elif method == "delete":
        delete()
    else:
        print("未知方法，请使用 upload, download 或 delete")
