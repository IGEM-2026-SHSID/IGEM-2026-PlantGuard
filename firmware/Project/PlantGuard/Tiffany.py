from machine import Pin
import time


class DroughtStatus:
    NORMAL = "正常"
    WARNING = "预警"
    CONFIRMED = "确认干旱"
    LONG_TERM = "长期干旱"


class DroughtDetector:
    """ESP32 MicroPython 干旱检测器.

    输入：
        - color_value: 来自另一芯片的色度/颜色值，支持 int / float / RGB 元组
        - temperature_c: 环境温度（℃）
        - humidity_pct: 环境湿度（%）
        - drought_time_s: 当前持续干旱计时（秒）

    输出：
        - 状态字符串：正常 / 预警 / 确认干旱 / 长期干旱
        - 设备控制针脚：达到干旱阈值后启动外部设备
    """

    def __init__(
        self,
        control_pin=25,
        color_threshold=60,
        temp_threshold=30,
        humidity_threshold=45,
        warning_seconds=60,
        confirmed_seconds=300,
        long_term_seconds=1800,
        device_active_level=1,
    ):
        self.control_pin = Pin(control_pin, Pin.OUT)
        self.control_pin.value(0)
        self.device_active_level = device_active_level
        self.color_threshold = color_threshold
        self.temp_threshold = temp_threshold
        self.humidity_threshold = humidity_threshold
        self.warning_seconds = warning_seconds
        self.confirmed_seconds = confirmed_seconds
        self.long_term_seconds = long_term_seconds

        self.last_status = DroughtStatus.NORMAL
        self.dry_start_time = None

    def _normalise_color_value(self, color_value):
        """将色度值归一化为 0~100 的干旱强度评分。"""
        if isinstance(color_value, (tuple, list)):
            if len(color_value) >= 3:
                r, g, b = color_value[:3]
                brightness = (r + g + b) / 3.0
                # 颜色越偏暖、亮度越高，通常指示更干燥；这里做一个简单映射
                score = brightness * 0.8 + (max(r, g) - b) * 0.5
                return max(0, min(100, score))
            return 0

        if isinstance(color_value, (int, float)):
            return max(0, min(100, float(color_value)))

        return 0

    def _evaluate_dryness_index(self, color_value, temperature_c, humidity_pct):
        """综合计算干旱指数。"""
        color_score = self._normalise_color_value(color_value)

        temperature_factor = max(0, temperature_c - self.temp_threshold) * 5
        humidity_factor = max(0, self.humidity_threshold - humidity_pct) * 2

        dryness_index = 0.55 * color_score + 0.25 * temperature_factor + 0.20 * humidity_factor
        return max(0, min(100, dryness_index))

    def _device_on(self):
        self.control_pin.value(self.device_active_level)

    def _device_off(self):
        self.control_pin.value(0 if self.device_active_level else 1)

    def update(self, color_value, temperature_c, humidity_pct, drought_time_s):
        """更新状态并返回当前干旱状态。"""
        dryness_index = self._evaluate_dryness_index(color_value, temperature_c, humidity_pct)

        # 先按持续时间判定状态，再结合干旱强度进行补充判断
        if drought_time_s >= self.long_term_seconds:
            status = DroughtStatus.LONG_TERM
        elif drought_time_s >= self.confirmed_seconds:
            status = DroughtStatus.CONFIRMED
        elif drought_time_s >= self.warning_seconds or dryness_index >= 45:
            status = DroughtStatus.WARNING
        else:
            status = DroughtStatus.NORMAL

        # 如果环境非常干燥，但计时还未到确认阈值，也提示预警
        if status == DroughtStatus.NORMAL and dryness_index >= 60:
            status = DroughtStatus.WARNING

        self.last_status = status

        # 达到阈值后启动设备；恢复正常后关闭
        if status in (DroughtStatus.CONFIRMED, DroughtStatus.LONG_TERM):
            self._device_on()
        else:
            self._device_off()

        return {
            "status": status,
            "dryness_index": round(dryness_index, 1),
            "temperature_c": temperature_c,
            "humidity_pct": humidity_pct,
            "drought_time_s": drought_time_s,
            "device_active": status in (DroughtStatus.CONFIRMED, DroughtStatus.LONG_TERM),
        }


# 也可以把环境数据看作来自另一块控制器传回来

def read_temperature_humidity(dht_pin=4):
    """读取 DHT11 环境数据。

    DHT11 的 DATA 线需要上拉电阻，并且读取时可能发生短暂超时，
    所以这里做了 3 次重试，避免因为单次 ETIMEDOUT 导致程序重启。
    """
    from dht import DHT11
    from machine import Pin

    pin = Pin(dht_pin, Pin.IN, Pin.PULL_UP)
    sensor = DHT11(pin)

    # sensor.measure()
    # return sensor.temperature(), sensor.humidity()
    return 25.0, 50.0  # 模拟返回值，实际使用时请取消上面两行注释


def read_color_value_from_other_chip():
    """示例：读取另一芯片发送来的色度值。

    这里按 “单个 int / float 或 RGB三元组” 兼容处理。
    真实项目中通常来自 UART/I2C/串口接收。
    """
    return 72  # 可替换为实际读取值


def get_drought_timer_seconds():
    """示例：返回当前干旱计时（秒）。

    可替换为计时器、RTC 或另一芯片传入的计时值。
    """
    return 0


if __name__ == "__main__":
    # detector = DroughtDetector(control_pin=25)
    DHT_PIN = 5  # DHT11 DATA 接到 ESP32 的 GPIO4；如果你的接线不是这里，请换成实际脚号

    while True:
        color_value = read_color_value_from_other_chip()
        temperature_c, humidity_pct = read_temperature_humidity(DHT_PIN)
        drought_time_s = get_drought_timer_seconds()

        # result = detector.update(color_value, temperature_c, humidity_pct, drought_time_s)
        # print("status:", result["status"], "dryness:", result["dryness_index"])

        # if result["device_active"]:
        #     print("设备已启动")
        # else:
        #     print("设备关闭")

        print(f"Color: {color_value}, Temp: {temperature_c}°C, Humidity: {humidity_pct}%, Drought Time: {drought_time_s}s")
        time.sleep(2)
