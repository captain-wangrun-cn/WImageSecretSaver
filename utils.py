'''
Author: WR(captain-wangrun-cn)
Date: 2026-01-25 18:09:16
LastEditors: WR(captain-wangrun-cn)
LastEditTime: 2026-01-25 18:41:51
FilePath: /WImageSecretSaver/utils.py
'''
from Crypto.Cipher import AES
import time

def get_time_str() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

def encrypt_image(image_data: bytes, password: str) -> bytes:
    cipher = AES.new(password.encode('utf-8'), AES.MODE_EAX)
    ciphertext, tag = cipher.encrypt_and_digest(image_data)
    return cipher.nonce + tag + ciphertext

def decrypt_image(encrypted_data: bytes, password: str) -> bytes:
    nonce = encrypted_data[:16]
    tag = encrypted_data[16:32]
    ciphertext = encrypted_data[32:]
    cipher = AES.new(password.encode('utf-8'), AES.MODE_EAX, nonce)
    image_data = cipher.decrypt_and_verify(ciphertext, tag)
    return image_data
