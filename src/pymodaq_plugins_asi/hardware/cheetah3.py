import os
import pathlib
import requests
import json
from pymodaq_plugins_asi.utils import Config
import re
from pymodaq_utils.logger import set_logger, get_module_name
from pymodaq_plugins_asi.hardware import cheetah3_consts as c3c
from pint import Quantity
from pathlib import Path
from PIL import Image
from io import BytesIO
import numpy as np
import socket
import threading

logger = set_logger(get_module_name(__file__))
destinations_path = Path(__file__).parent / Path('destinations.json')

class Cheetah3Config :

    def __init__(self):
        self.config = Config()
        self.bpcs = self.list_hardware_files('bpc')
        self.dacss = self.list_hardware_files('dacs')

    def list_hardware_files(self, extension) : 
        folder_path = pathlib.Path(self.config['CHEETAH3']['folders'][extension])
        all_files = os.listdir(folder_path)
        selected_files = []
        for file in all_files : 
            m = re.match(r"(.*)(\." + extension + r")", file)
            if m : 
                selected_files.append(pathlib.Path(folder_path) / pathlib.Path(file))

        return selected_files

class Cheetah3() :

    def __init__(self):
        self.config = Cheetah3Config()
        self.serverurl = self.config.config['CHEETAH3']['connection']['serverurl']
        self.dashboard = self.get_dashboard()
        self.detector_config = self.get_detector_config()
        self._bpc_file = None
        self._dacs_file = None
        self._exposure_time = Quantity('10ms')
        self._readout_time = Quantity('10ms')
        self._ntriggers = 1

    def get_request(self, url, expected_status=200):
        response = requests.get(url=url)
        if response.status_code != expected_status:
            raise Exception("Failed GET request: {}, response: {} {}".format(url, response.status_code, response.text))

        return response

    def put_request(self, url, data, expected_status=200):
        response = requests.put(url=url, data=data)
        if response.status_code != expected_status:
            raise Exception("Failed PUT request: {}, response: {} {}".format(url, response.status_code, response.text))

        return response
    
    def check_connection(self):
        """Check connection with SERVAL

        Keyword arguments:
        serverurl -- the URL of the running SERVAL (string)
        """

        # Response "200" is expected when request has succeeded
        self.get_request(url=self.serverurl, expected_status=200)
        logger.info('Connection to the Cheetah3 successful.')
        return True

    def get_dashboard(self) : 
        response = self.get_request(url=self.serverurl + '/dashboard')
        data = response.text
        dashboard = json.loads(data)
        return dashboard

    def get_detector_config(self) : 
        response = self.get_request(url=self.serverurl + '/detector/config')
        data = response.text
        detector_config = json.loads(data)
        return detector_config

    def load_pixel_config(self):
        """Load detector parameters required for operation, prints statuses
        """
        # load a binary pixel configuration exported by SoPhy, the file should exist on the server
        response = self.get_request(url=self.serverurl + '/config/load?format=pixelconfig&file=' + self.bpc_file)
        data = response.text
        logger.info(f'Response of loading binary pixel configuration file:{data}' )

        #  .... and the corresponding DACs file
        response = self.get_request(url=self.serverurl + '/config/load?format=dacs&file=' + self.dacs_file)
        data = response.text
        logger.info(f'Response of loading DACs file: {data}')

    def set_detector_config(self,trigger_mode = 'continuous',ntriggers=1,trigger_period=0.5) : 
        if trigger_mode == 'continuous' : 
            self.set_continuous_mode()
        elif trigger_mode == 'automatic' : 
            self.set_automatic_mode(ntriggers = ntriggers)
        self.put_request(url=self.serverurl +'/detector/config', data = json.dumps(self.detector_config))
        print(self.detector_config)
        # logger.info(f'Loaded config :\nTriggerMode : {self.detector_config['TriggerMode']}\nExposureTime : {self.detector_config['ExposureTime']}\nTriggerPeriod : {self.detector_config['TriggerPeriod']}\nnTriggers : {self.detector_config['nTriggers']}')

    def set_continuous_mode(self, **kwargs) : 
        self.detector_config['TriggerMode'] = 'CONTINUOUS'
        self.detector_config['TriggerPeriod'] = self.exposure_time.magnitude
        self.detector_config['ExposureTime'] = self.exposure_time.magnitude
        self.detector_config['nTriggers'] = 1 

    def set_automatic_mode(self, **kwargs) : 
        self.detector_config['TriggerMode'] = 'AUTOTRIGSTART_TIMERSTOP'
        self.detector_config['TriggerPeriod'] = (self.exposure_time + self._readout_time ).magnitude
        self.detector_config['ExposureTime'] = self.exposure_time.magnitude
        self.detector_config['nTriggers'] = kwargs['ntriggers'] 

    def set_destination(self, profile : str) : 
        with open(destinations_path, 'r') as f : 
            profiles = json.load(f)
        current_profile = profiles[profile]
        self.put_request(url = self.serverurl + '/server/destination', data = json.dumps(current_profile))  

    def start(self):
        """Perform acquisition

        Keyword arguments:
        serverurl -- the URL of the running SERVAL (string)
        """
        self.set_detector_config(ntriggers=self.ntriggers, trigger_mode='automatic')
        self.set_destination(profile='basic')
        response = self.get_request(url=self.serverurl + '/measurement/start')
        data = response.text
        logger.info('Response of acquisition start: ' + data)

    def preview(self):
        """Preview of collected data

        Keyword arguments:
        serverurl -- the URL of the running SERVAL (string)
        ntrig -- number of triggers to be executed (integer, defaul value is 1)
        """

        # Getting preview data. This is blocking, so it will wait until an image is ready.

        response = self.get_request(url=self.serverurl + '/measurement/image')
        image = Image.open(BytesIO(response.content))
        # Show the data in the image
        return np.array(image)
    
    def get_status(self) :
        if self.get_dashboard()["Measurement"] is None : 
            return None
        else : 
            return self.get_dashboard()["Measurement"]["Status"]

    def wait_for_acq(self) : 
        while True : 
            status = self.get_status() 
            if status == "DA_RECORDING" : 
                return 1
            elif status == "DA_IDLE" : 
                pass
            elif status == "DA_PREPARING" :
                pass
            elif status == "DA_STOPPING" : 
                return 0 

    def stop(self) : 
        response = self.get_request(url=self.serverurl + '/measurement/stop')
        data = response.text
        logger.info('Response of acquisition stop : ' + data)
            
    @property
    def bpc_file(self) : 
        if self._bpc_file is None : 
            self._bpc_file = self.config.bpcs[0]
        return self._bpc_file

    @bpc_file.setter
    def bpc_file(self, filename) : 
        if filename in self.config.bpcs :
            self._bpc_file = filename
        else :
            logger.info(f'the bpc file : {filename} is not part of the available files.')  

    @property
    def dacs_file(self) : 
        if self._dacs_file is None : 
            self._dacs_file = self.config.dacss[0]
        return self._dacs_file

    @dacs_file.setter
    def dacs_file(self, filename) : 
        if filename in self.config.dacss :
            self._dacs_file = filename
        else :
            logger.info(f'the dacs file : {filename} is not part of the available files.') 

    @property
    def exposure_time (self) : 
        return self._exposure_time.to('s')
    
    @exposure_time.setter
    def exposure_time(self,value) : 
        q = Quantity(value,'s')
        self._exposure_time = q.to('s') 

    @property
    def ntriggers(self) : 
        return self._ntriggers

    @ntriggers.setter
    def ntriggers(self, value) : 
        self._ntriggers = value
    



if __name__ == '__main__' : 
    cam = Cheetah3()
    cam.check_connection()
    # cam.start_listening()
    # print(cam.get_dashboard())
    # print(cam.bpc_file)
    # print(cam.detector_config)
    # print(cam.serverurl)
    cam.exposure_time = '0.5s'
    cam.set_detector_config(trigger_mode='automatic',ntriggers=75)
    # print(cam.get_detector_config())
    cam.set_destination("basic")
    # response = cam.get_request(url = cam.serverurl + '/server/destination')
    # data = response.text
    # # print(data)
    cam.start()
    # print(cam.get_dashboard())
    cam.wait_for_acq()
    i = 0 
    measure = True
    while measure :
        try :  
            print(cam.preview().sum() + i)
            i+=1
            if cam.get_status() ==  'DA_IDLE' : 
                measure= False
        except KeyboardInterrupt : 
            cam.stop()
            break
    #     cam.wait_for_acq()
        # cam.wait_for_acq()
    # print(cam.preview().shape)
