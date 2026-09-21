# Micropython TSL2591 module

This is a simple python library for the Adafruit TSL2591 breakout board based on the [Arduino library](https://github.com/adafruit/Adafruit_TSL2591_Library) from Adafruit. [python-tsl2591](https://github.com/maxlklaxl/python-tsl2591) was developed to work on a Raspberry PI. I then forked it to create a [Micropython](http://www.micropython.org) version. There were two changes from the original:

1. Micropython does not provide an smbus api, so smbus was emulated on top of the lower-level I2C library it does provide.
2. The ESP8266 and other chips are severely memory limited. With the Raspberry Pi version, even importing the tsl2591 module caused it to run out of memory on the ESP8266. The code was simplified were possible and all the comments stripped out.

# INFO

Coming soon...




## Installing ##

Just copy tsl2591.py to your micropython board. Micropython's webrepl has experimental
support for copying files. I instead used the [mpfshell](https://github.com/wendlers/mpfshell)
to copy files to my ESP8266 board.



## Quickstart ##


```
import tsl2591

tsl = tsl2591.Tsl2591()  # initialize
full, ir = tsl.get_full_luminosity()  # read raw values (full spectrum and ir spectrum)
lux = tsl.calculate_lux(full, ir)  # convert raw values to lux
print lux, full, ir
```




## License ##

Python files in this repository are released under the [MIT license](LICENSE.md).
