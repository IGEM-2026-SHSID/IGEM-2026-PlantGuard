from machine import Pin
import time


class DroughtStatus:
    NORMAL = "正常"
    WARNING = "预警"
    CONFIRMED = "确认干旱"
    LONG_TERM = "长期干旱"


def read_temperature_humidity():
    """示例：读取 DHT11 环境数据。
    """
    try:
        for _ in range(3):  # 尝试读取三次
            from dht import DHT11
            from machine import Pin

            pin = Pin(5, Pin.IN, Pin.PULL_UP)
            sensor = DHT11(pin)
            sensor.measure()
        return sensor.temperature(), sensor.humidity()
    except Exception as e:
        # 运行在仿真/测试时可使用默认值
        print("读取 DHT11 失败，使用默认值:", e)
        return 28.0, 45.0


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
    while True:
        color_value = read_color_value_from_other_chip()
        temperature_c, humidity_pct = read_temperature_humidity()
        drought_time_s = get_drought_timer_seconds()

        print(temperature_c, humidity_pct)
        time.sleep(2)
