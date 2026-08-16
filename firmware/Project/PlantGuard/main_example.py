import network
import socket
import time
from machine import Pin, SoftI2C
from dht import DHT11
from AS726X import AS726X
from Webpage import WEBPAGESTRING

SSID = "PlantGuard_AP"
PASSWORD = "plantguard"
HOST_IP = "192.168.4.1"
HOST_MASK = "255.255.255.0"
HOST_GATEWAY = "192.168.4.1"
HOST_DNS = "8.8.8.8"
POLL_INTERVAL_MS = 5000
DHT_PIN = 2

last_temperature = 0.0
last_humidity = 0.0
last_blue = 0.0
blue_cool = 0

iic = SoftI2C(4,5)
color_sensor = AS726X(iic)
dht_sensor = DHT11(Pin(DHT_PIN, Pin.IN, Pin.PULL_UP))


def setup_access_point():
    """Create a Wi-Fi access point so a phone or PC can connect."""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    time.sleep(1)
    ap.config(essid=SSID, password=PASSWORD, authmode=network.AUTH_WPA2_PSK)
    ap.ifconfig((HOST_IP, HOST_MASK, HOST_GATEWAY, HOST_DNS))
    return ap


def read_dht11():
    """Read DHT11 temperature and humidity."""
    global last_temperature, last_humidity, dht_sensor

    try:
        dht_sensor.measure()
        last_temperature = dht_sensor.temperature()
        last_humidity = dht_sensor.humidity()
        print(last_temperature,last_humidity)
        return last_temperature, last_humidity
    except Exception as exc:
        print("[PlantGuard] DHT11 reading failed:", exc)
        return last_temperature, last_humidity

def read_bule():
    global last_blue, color_sensor, blue_cool

    try:
        # color_sensor.enable_bulb()
        if blue_cool == 0:
            last_blue = color_sensor.get_calibrated_blue()
            time.sleep_ms(100)
            # color_sensor.disable_bulb()
            print(last_blue)
        blue_cool += 1
        blue_cool %= 5
        return last_blue
    except Exception as e:
        print("[PlantGuard] AS726X failed:", e)
        return last_blue

last_refresh_time = 0


def build_json_response():
    global last_temperature, last_humidity, last_refresh_time
    temperature = last_temperature
    humidity = last_humidity
    now = time.ticks_ms()

    if last_refresh_time == 0:
        elapsed = 0
    else:
        elapsed = max(0, (now - last_refresh_time) // 1000)

    last_refresh_time = now

    return {
        "temperature": temperature,
        "humidity": humidity,
        "elapsed": elapsed
    }


def handle_http_request(request):
    request_line = request.decode('utf-8', 'ignore').split('\r\n', 1)[0]
    method, path, _ = request_line.split(' ')

    if method != 'GET':
        return "HTTP/1.1 405 Method Not Allowed\r\nContent-Type: text/plain\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"

    if path == '/data':
        payload = build_json_response()
        body = ('{"temperature": %.1f, "humidity": %.1f, "elapsed": %d}' % (
            payload['temperature'], payload['humidity'], payload['elapsed']
        )).encode('utf-8')
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: application/json\r\n"
        response += "Connection: close\r\n"
        response += "Content-Length: %d\r\n\r\n" % len(body)
        return response.encode('utf-8') + body

    body = WEBPAGESTRING.encode('utf-8')
    response = "HTTP/1.1 200 OK\r\n"
    response += "Content-Type: text/html; charset=utf-8\r\n"
    response += "Connection: close\r\n"
    response += "Content-Length: %d\r\n\r\n" % len(body)
    return response.encode('utf-8') + body


def start_server():
    """Start a simple HTTP server and serve the web UI."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", 8080))
    server.listen(5)

    print("\n[PlantGuard] Wi-Fi hotspot started")
    print("[PlantGuard] SSID:", SSID)
    print("[PlantGuard] Password:", PASSWORD)
    print("[PlantGuard] Access URL: http://%s" % HOST_IP)

    while True:
        conn, addr = server.accept()
        print("[PlantGuard] Client connected:", addr)
        read_dht11()
        read_bule()
        # time.sleep(10)
        try:
            request = conn.recv(4096)
            if request:
                response = handle_http_request(request)
                conn.sendall(response)
        except OSError as exc:
            print("[PlantGuard] Socket error:", exc)
        finally:
            conn.close()


def main():
    setup_access_point()
    read_dht11()
    print("[PlantGuard] AP IP:", HOST_IP)
    print("[PlantGuard] Waiting for connection...")
    start_server()


if __name__ == '__main__':
    main()
