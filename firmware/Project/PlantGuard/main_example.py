from camera import Camera

a = Camera(data_pins=[5,18,19,21,36,39,34,35], pclk_pin=22,vsync_pin=25,href_pin=23,sda_pin=26,scl_pin=27,xclk_pin=0)
a.init()

def main():
    print("Welcome to RT-Thread MicroPython!")
    
if __name__ == '__main__':
    main()
