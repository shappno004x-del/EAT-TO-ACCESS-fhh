from flask import Flask, request, jsonify
import httpx
import asyncio
import warnings
from urllib.parse import urlparse, parse_qs
import binascii
import random
import base64
import json
import sys
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

warnings.filterwarnings("ignore")

app = Flask(__name__)

# ---------- Constants ----------
MAJOR_LOGIN_URL = "https://loginbp.ggpolarbear.com/MajorLogin"
FREEFIRE_VERSION = "OB54"

KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# ---------- Device Database ----------
DEVICES = [
    {"model": "SM-G998B", "android": "13", "api": "33", "cpu": "ARMv8 | 2800 | 8", "gpu": "Mali-G78", "res": ["1440", "1080"], "dpi": "480", "ram": "8192", "build": "TP1A.220624.014"},
    {"model": "realme C31", "android": "12", "api": "31", "cpu": "ARMv8 | 2000 | 8", "gpu": "Mali-G52", "res": ["720", "1600"], "dpi": "320", "ram": "4096", "build": "SQ3A.220705.003"},
    {"model": "Mi 11", "android": "12", "api": "32", "cpu": "ARMv8 | 2500 | 8", "gpu": "Adreno 650", "res": ["1080", "2400"], "dpi": "395", "ram": "6144", "build": "SQ3A.220705.003"},
    {"model": "OnePlus 9", "android": "13", "api": "33", "cpu": "ARMv8 | 2900 | 8", "gpu": "Adreno 660", "res": ["1080", "2400"], "dpi": "420", "ram": "8192", "build": "TP1A.220624.014"},
    {"model": "Pixel 6", "android": "13", "api": "33", "cpu": "ARMv8 | 2800 | 8", "gpu": "Mali-G78", "res": ["1080", "2400"], "dpi": "440", "ram": "8192", "build": "TP1A.220624.014"},
]

def get_random_device():
    device = random.choice(DEVICES)
    return {
        "model": device["model"],
        "android": device["android"],
        "api": device["api"],
        "cpu": device["cpu"],
        "gpu": device["gpu"],
        "width": device["res"][0],
        "height": device["res"][1],
        "dpi": device["dpi"],
        "ram": device["ram"],
        "build": device["build"]
    }

def encrypt_data(data_bytes):
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    padded = pad(data_bytes, AES.block_size)
    return cipher.encrypt(padded)

async def get_garena_data(eat_token: str):
    try:
        # যদি পুরো URL দেওয়া হয়, eat_token বের করব
        if eat_token.startswith("http"):
            parsed = urlparse(eat_token)
            params = parse_qs(parsed.query)
            eat_token = params.get("eat", [None])[0]
            if not eat_token:
                return {"error": "Eat token not found in URL"}

        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            # Step 1: Get Access Token from Eat Token
            callback_url = f"https://api-otrss.garena.com/support/callback/?access_token={eat_token}"
            response = await client.get(callback_url, follow_redirects=False)

            if 300 <= response.status_code < 400 and "Location" in response.headers:
                redirect_url = response.headers["Location"]
                parsed_url = urlparse(redirect_url)
                query_params = parse_qs(parsed_url.query)

                token_value = query_params.get("access_token", [None])[0]
                account_id = query_params.get("account_id", [None])[0]
                account_nickname = query_params.get("nickname", [None])[0]
                region = query_params.get("region", [None])[0]

                if not token_value or not account_id:
                    return {"error": "Failed to extract data from Garena"}
            else:
                return {"error": f"Invalid access token or session expired. Status: {response.status_code}"}

            # Step 2: Get OpenID from Shop2Game
            openid_url = "https://topup.pk/api/auth/player_id_login"
            openid_headers = { 
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "en-MM,en-US;q=0.9,en;q=0.8",
                "Content-Type": "application/json",
                "Origin": "https://topup.pk",
                "Referer": "https://topup.pk/",
                "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36",
                "X-Requested-With": "mark.via.gp",
            }
            payload = {"app_id": 100067, "login_id": str(account_id)}
            
            openid_res = await client.post(openid_url, headers=openid_headers, json=payload)
            openid_data = openid_res.json()
            open_id = openid_data.get("open_id")
            
            if not open_id:
                return {"error": "Failed to extract open_id"}

            # Step 3: Major Login to get JWT
            try:
                import my_pb2
                game_data = my_pb2.GameData()
                device = get_random_device()
                
                game_data.timestamp = "2025-01-15 10:30:45"
                game_data.game_name = "free fire"
                game_data.game_version = 1
                game_data.version_code = "1.121.0"
                game_data.os_info = f"Android OS {device['android']} / API-{device['api']} ({device['build']})"
                game_data.device_type = "Handheld"
                game_data.network_provider = "Verizon Wireless"
                game_data.connection_type = "WIFI"
                game_data.screen_width = int(device['width'])
                game_data.screen_height = int(device['height'])
                game_data.dpi = device['dpi']
                game_data.cpu_info = device['cpu']
                game_data.total_ram = int(device['ram'])
                game_data.gpu_name = device['gpu']
                game_data.gpu_version = "OpenGL ES 3.2"
                game_data.user_id = f"Google|{random.randint(1000000000000, 9999999999999)}"
                game_data.ip_address = f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
                game_data.language = "en"
                game_data.open_id = open_id
                game_data.access_token = token_value
                game_data.platform_type = 8
                game_data.field_99 = "8"
                game_data.field_100 = "8"
                game_data.device_form_factor = "Phone"
                game_data.device_model = device['model']

                serialized_data = game_data.SerializeToString()
                encrypted = encrypt_data(serialized_data)
                hex_encrypted = binascii.hexlify(encrypted).decode('utf-8')
                edata = bytes.fromhex(hex_encrypted)
                
                headers = {
                    "User-Agent": f"Dalvik/2.1.0 (Linux; U; Android {device['android']}; {device['model']} Build/{device['build']})",
                    "Connection": "Keep-Alive",
                    "Accept-Encoding": "gzip",
                    "Content-Type": "application/octet-stream",
                    "Expect": "100-continue",
                    "X-Unity-Version": "2018.4.11f1",
                    "X-GA": "v1 1",
                    "ReleaseVersion": FREEFIRE_VERSION
                }
                
                major_res = await client.post(MAJOR_LOGIN_URL, data=edata, headers=headers)
                jwt_token = None
                
                if major_res.status_code == 200:
                    try:
                        import output_pb2
                        msg = output_pb2.Garena_420()
                        msg.ParseFromString(major_res.content)
                        for field in msg.DESCRIPTOR.fields:
                            if field.name == "token":
                                jwt_token = getattr(msg, field.name)
                    except:
                        pass
            except Exception as e:
                jwt_token = None

            return {
                "status": "success",
                "eat_token": eat_token,
                "account_id": account_id,
                "account_nickname": account_nickname,
                "open_id": open_id,
                "access_token": token_value,
                "region": region,
                "generated_jwt": jwt_token,
                "version": "OB54",
                "credit": "Telegram: @SHAPPNO_CODEX"
            }

    except Exception as e:
        return {"error": "Server error", "details": str(e)}

# ---------- Routes ----------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "api": "Eat Token to Access Token Converter",
        "version": "OB54",
        "credit": "Telegram: @SHAPPNO_CODEX",
        "status": "running on Vercel ✅",
        "endpoint": "/access_token?eat_token={YOUR_EAT_TOKEN_OR_URL}",
        "example": "/access_token?eat_token=https://ticket.kiosgamer.co.id/?eat=xxxxx"
    })

@app.route("/access_token", methods=["GET"])
def get_token_info():
    eat_token = request.args.get("eat_token")
    if not eat_token:
        return jsonify({"error": "Missing eat_token parameter"}), 400
    result = asyncio.run(get_garena_data(eat_token))
    return jsonify(result)

# ========== VERCEL HANDLER ==========
app = app

def handler(request, context):
    return app(request, context)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)