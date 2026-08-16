import network
import socket
import time

# Wi-Fi 热点参数
SSID = "PlantGuard_AP"
PASSWORD = "plantguard"
HOST_IP = "192.168.4.1"
HOST_MASK = "255.255.255.0"
HOST_GATEWAY = "192.168.4.1"
HOST_DNS = "8.8.8.8"


def setup_access_point():
    """创建热点，手机可以加入该局域网。"""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)

    # 让 AP 立即启动
    time.sleep(1)

    # 设定热点名称和密码，密码至少 8 位
    ap.config(essid=SSID, password=PASSWORD, authmode=network.AUTH_WPA2_PSK)

    # 设定地址，确保手机可以访问到 192.168.4.1
    ap.ifconfig((HOST_IP, HOST_MASK, HOST_GATEWAY, HOST_DNS))

    return ap


def web_page():
    return """<!DOCTYPE html>
<html>
    <head>
        <meta charset="utf-8">
        <title>PlantGuard</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f8f5; color: #1a2b1d; text-align: center; padding-top: 60px; }
            .box { background: white; width: 360px; margin: auto; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
            h1 { color: #1f7a4d; }
            p { font-size: 18px; }
        </style>
    </head>
    <body>
        <div class="box">
            <h1>PlantGuard</h1>
            <p>设备已连接到热点。</p>
            <p>Wi-Fi: PlantGuard_AP</p>
            <p>访问地址: http://192.168.4.1</p>
        </div>
    </body>
</html>
"""


def start_server():
    """开启一个简单的 HTTP 服务，浏览器访问设备 IP 即可看到页面。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 80))
    server.listen(5)

    print("\n[PlantGuard] 热点已启动")
    print("[PlantGuard] SSID:", SSID)
    print("[PlantGuard] Password:", PASSWORD)
    print("[PlantGuard] Phone URL: http://192.168.4.1")

    while True:
        conn, addr = server.accept()
        print("[PlantGuard] Client connected:", addr)

        try:
            request = conn.recv(1024)
            if request:
                response = "HTTP/1.1 200 OK\r\n"
                response += "Content-Type: text/html; charset=utf-8\r\n"
                response += "Connection: close\r\n\r\n"
                response += web_page()
                conn.sendall(response.encode("utf-8"))
        except OSError:
            pass
        finally:
            conn.close()


def main():
    ap = setup_access_point()
    print("[PlantGuard] AP IP:", ap.ifconfig()[0])
    print("[PlantGuard] 等待手机连接...")
    start_server()


if __name__ == "__main__":
    main()
