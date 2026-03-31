from pymodaq_plugins_asi.hardware.cheetah3 import Cheetah3
import json
import socket
import time

class Tp3toolsConfig:

    def __init__(self):
        self.bin = False
        self.bytedepth = 0
        self.cumul = False
        self.mode = 0
        self.xspim_size = 0
        self.yspim_size = 0
        self.xscan_size = 0
        self.yscan_size = 0
        self.pixel_time = 0
        self.time_delay = 0
        self.time_width = 0
        self.time_resolved = False
        self.save_locally = False
        self.pixel_mask = 0
        self.video_time = 0
        self.threshold = 0
        self.bias_voltage = 0
        self.destination_port = 0
        self.acquisition_us = 1000 #1 ms
        self.sup0 = 0.0
        self.sup1 = 0.0
        #self.__custom_meas = False
        #self.__custom_shape = None
        
    
        
    def create_configuration_bytes(self):
        return json.dumps(self.__dict__).encode()
    

class Tp3toolsCheetah3(Cheetah3) :
    
    def __init__(self):
        self.tp3config = Tp3toolsConfig()
        super().__init__()
    
    def acquistion(self) : 
        
        self.tp3config.mode = 2
        self.tp3config.bytedepth = 4
        self.ntriggers = 500
        self.set_detector_config(ntriggers=self.ntriggers, trigger_mode='automatic')
        self.set_destination(['tp3_tools'])
        response = self.get_request(url=self.serverurl + '/measurement/start')
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        address = ('10.35.44.20',8088)
        client.connect(address)
        client.send(self.tp3config.create_configuration_bytes())
        while True : 
            try : 
                # time.sleep(0.1)
                data = bytearray(client.recv(128))
                print(data)
            except KeyboardInterrupt : 
                print('stop')
                break
        
    
if __name__ == '__main__' : 
    t = Tp3toolsCheetah3()
    t.acquistion()