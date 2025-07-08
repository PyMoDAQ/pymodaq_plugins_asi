import os
import pathlib
import requests
import json
from pymodaq_plugins_asi.utils import Config
import re

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
                selected_files.append(file)

        return selected_files

class Cheetah3() :

    def __init__(self):
        self.config = Cheetah3Config()
        self.serverurl = self.config.config['CHEETAH3']['connection']['serverurl']

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