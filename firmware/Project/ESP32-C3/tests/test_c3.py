import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from history import RingHistory
from sensors import SensorSampler
from app import Application, validate_camera_reading
from calculation import calculate
from tsl2591 import TSL2591

class DHT:
    def measure(self): pass
    def temperature(self): return 24
    def humidity(self): return 61
class Broken:
    def measure(self): raise OSError("offline")
class Light:
    def read(self): return {"lux": 12.5, "full_spectrum": 20, "infrared": 5, "visible": 15}
class I2C:
    def __init__(self): self.regs={0xB4: bytes((100,0)),0xB6:bytes((20,0))}
    def writeto_mem(self,*args): pass
    def readfrom_mem(self,a,r,n): return self.regs[r]

def camera():
    return {"device_id":"cam", "sequence":1, "capture_uptime_ms":2, "trigger":"timer", "width":160, "height":120, "decoded_pixels":19200, "selected_pixels":0, "blue_value":None, "error":None}

class Tests(unittest.TestCase):
    def test_ring(self):
        h=RingHistory(2); h.append(1); h.append(2); h.append(3)
        self.assertEqual(h.to_list(), [2,3]); self.assertEqual(h.latest(),3)
    def test_isolated_sampling(self):
        r=SensorSampler(Broken(), Light(), clock=lambda:7).sample()
        self.assertEqual(r["dht_status"],"error"); self.assertEqual(r["tsl2591_status"],"ok"); self.assertEqual(r["visible"],15)
    def test_tsl_channels(self):
        v=TSL2591(I2C()).read(); self.assertEqual(v["full_spectrum"],100); self.assertEqual(v["infrared"],20); self.assertEqual(v["visible"],80); self.assertGreater(v["lux"],0)
    def test_calculation_placeholder(self): self.assertEqual(calculate(None,[]), {"value":None,"status":"not_configured"})
    def test_routes_and_validation(self):
        s,c=RingHistory(3),RingHistory(3); s.append(SensorSampler(DHT(),Light(),clock=lambda:10).sample())
        app=Application(s,c,clock=lambda:20)
        status,_,body=app.route("GET","/api/v1/state"); self.assertEqual(status,200); self.assertEqual(json.loads(body)["sensor_age_ms"],10)
        status,_,_=app.route("POST","/api/v1/camera/readings",json.dumps(camera()).encode()); self.assertEqual(status,201); self.assertEqual(len(c),1)
        status,_,_=app.route("POST","/api/v1/camera/readings",b"{}"); self.assertEqual(status,400)
        self.assertEqual(app.route("POST","/api/v1/state")[0],405); self.assertEqual(app.route("GET","/nope")[0],404)
    def test_reject_bool_integer(self):
        x=camera(); x["sequence"]=True
        with self.assertRaises(ValueError): validate_camera_reading(x)

if __name__ == "__main__": unittest.main()
