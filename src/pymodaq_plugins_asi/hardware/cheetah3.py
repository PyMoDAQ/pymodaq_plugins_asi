import requests
import json
from pymodaq_plugins_asi.utils import Config
from pymodaq_utils.logger import set_logger, get_module_name
from pint import Quantity
from PIL import Image
from io import BytesIO
import numpy as np

logger = set_logger(get_module_name(__file__))

################
# Code Outline #
################

# I. Cheetah3 config class
# II. Cheetah3 controller class
#   II. 1. `requests` generic functions
#   II. 2. Detector configuration loading functions
#   II. 3. Cheetah3 properties
#   II. 4. Cheetah3 start/stop functions
# III. Local testing code

############################
# I. Cheetah3 config class #
############################

class Cheetah3Config :
    """
    Configuration class for the cheetah3 camera. Manages the config_cheetah3.toml file.

    Attributes
    ----------

    :config: The PyMoDAQ configuration object that is generated from config_asi.toml.

    :destination: A dictionnary containing the serval-readable destinations for the serval data outputs.
    """

    def __init__(self):
        """
        Reads and stores values of the config_cheetah3.toml file from the user preference folder.

        Parameters
        ----------

        Result
        ------ 
        """
        self.config = Config()
        self.build_destination()

    def build_destination(self, destination_names = ['live_preview']) -> None :
        """
        Updates the attribute self.destination with one or several configurated profiles.

        Parameters
        ----------
        
        :param destination_names: list of destination names

        Results
        -------

        None
        """
        self.destination = dict()
        for destination_name in destination_names : 
            self.destination.update(self.config['CHEETAH3']['destinations'][destination_name])

    def add_destination(self, destination : dict, destination_name  = '') -> None : 
        """
        Updates the destinations dict with an input destination and saves it to the user config file.

        Parameters
        ----------

        :param destination: Input destination dictionnary, it has to be a valid input for Serval. (Check ASI documentation.)
        :param destination_name: Gives a profile name to the input destination so that it is later stored in the config.toml. In case you don't want to add it to the file, leave it empty. 
        
        Results
        -------

        None
        """
        self.destination.update(destination)
        if len(destination_name) > 0  : 
            self.config['CHEETAH3']['destinations'][destination_name].update(destination)
            self.config.save()

    def destination_names_list(self) -> list[str] :
        """
        Gets all the destination profiles listed in the configuration file.
        
        Results
        -------

        :profile_name_list: list of the destination profiles.
        """
        profile_name_list = [] 
        for key in self.config["CHEETAH3"]["destinations"] : 
            profile_name_list.append(key)
        return profile_name_list
    
    def add_bpc_file(self, file_path : str) -> None :
        """
        Adds a bpc file paths to the list of available bpc file paths and saves it to the config file.
        
        Parameters
        ----------

        :param file_path: File path of the Cheetah3 computer to the bpc file.

        Results
        -------

        None
        """ 
        bpc_files = self.config["CHEETAH3"]["file_paths"]['bpc']
        bpc_files.append(file_path)
        self.config["CHEETAH3"]["file_paths"]['bpc'] = bpc_files
        self.config.save()

    def add_dacs_file(self, file_path : str) -> None :
        """
        Adds a dacs file paths to the list of available dacs file paths and saves it to the config file.
        
        Parameters
        ----------

        :param file_path: File path of the Cheetah3 computer to the dacs file.

        Results
        -------

        None
        """ 
        dacs_files = self.config["CHEETAH3"]["file_paths"]['dacs']
        dacs_files.append(file_path)
        self.config["CHEETAH3"]["file_paths"]['dacs'] = dacs_files
        self.config.save()

    def add_save_folder(self, folder_path : str) -> None :
        """
        Adds a path to the list of available folders paths for saving data and saves it to the config file.
        
        Parameters
        ----------

        :param folder_path: File path of the Cheetah3 computer to where the data are saved.

        Results
        -------

        None
        """ 
        save_folders = self.config["CHEETAH3"]["file_paths"]['data']
        save_folders.append(folder_path)
        self.config["CHEETAH3"]["file_paths"]['dacs'] = save_folders
        self.config.save()

#################################
# II. Cheetah3 controller class #
#################################

class Cheetah3() :
    """
    Camera class that manages the communication with the hardware.

    The detector has a lot of checkable/tunable parameters. 
    
    * :dashboard: Set of general parameters of the hardawre and software. (software version, measurement status, etc ...)
    
    * :detector_config: Set of detector related technical parameters such as triggers, dwell time, voltages, etc ...
    
    * :destination: Controls in which mode and to which adresses the data are sent. The same data can be send to several channels simultaneously.

    * :pixel_config: Part of the detector_config that controls which pixels of the hardware are activated.

    Attributes
    ----------
    :config: The Cheetah3Config object that manages the PyMoDAQ config object

    :serverurl: base url for the communication through http with Serval

    :dashboard: see above.

    :detector_config: see above.
    """

    def __init__(self):
        """
        Instantiate the camera object that controls the hardware through Serval.
        """
        self.config = Cheetah3Config()
        self.serverurl = self.config.config['CHEETAH3']['connection']['serverurl']
        self.dashboard = self.get_dashboard()
        self.detector_config = self.get_detector_config()
        self._bpc_file = None
        self._dacs_file = None
        self._save_folder = None
        self._exposure_time = Quantity('10ms')
        self._readout_time = Quantity('10ms')
        self._ntriggers = 1
        self._destination_profiles = ['live_preview']


    #######################################
    # II. 1. `requests` generic functions #
    #######################################

    def get_request(self, url : str, expected_status=200) -> requests.Response:
        """
        Generic function. Get a value as an http request.

        Parameters
        ----------
        :param url: http://adress:port/command to ask the server

        :param expected_status: The server status code to be expected from communication. 200 status is a successful communication.

        Results
        -------

        :Response: Response object from the server

        """
        response = requests.get(url=url)
        if response.status_code != expected_status:
            raise Exception("Failed GET request: {}, response: {} {}".format(url, response.status_code, response.text))

        return response

    def put_request(self, url : str, data : str, expected_status=200) -> requests.Response:
        """
        Generic function. Sends data to the server.

        Parameters
        ----------
        :param url: http://adress:port/ to ask the server

        :param data: data to be sent to the server. e.g. a detector config to change detection parameters.

        :param expected_status: The server status code to be expected from communication. 200 status is a successful communication.

        Results
        -------

        :Response: Response object from the server

        """
        response = requests.put(url=url, data=data)
        if response.status_code != expected_status:
            raise Exception("Failed PUT request: {}, response: {} {}".format(url, response.status_code, response.text))

        return response
    
    def check_connection(self) -> bool:
        """
        Checks connection with SERVAL

        Results
        -------

        True if the connection is established. Raises an exception otherwise.
        """

        # Response "200" is expected when request has succeeded
        self.get_request(url=self.serverurl, expected_status=200)
        logger.info('Connection to the Cheetah3 successful.')
        return True
    
    #####################################################
    #   II. 2. Detector configuration loading functions #
    #####################################################

    def get_dashboard(self) -> dict :
        """
        Gets the Cheetah3 dashboard.
        
        Results
        -------

        :dashboard: Dictionnary of the current state of the server, detector and measurement.
        """ 
        response = self.get_request(url=self.serverurl + '/dashboard')
        dashboard = json.loads(response.text)
        return dashboard

    def get_detector_config(self) -> dict :
        """
        Gets the Cheetah3 detector configuration.
        
        Results
        -------

        :detector_config: Dictionnary of the current configuration of the detector.
        """  
        response = self.get_request(url=self.serverurl + '/detector/config')
        detector_config = json.loads(response.text)
        return detector_config

    def load_pixel_config(self) -> None:
        """
        Sets the dacs and bpc files of the detector.

        Results
        -------
        None
        """
        # load a binary pixel configuration exported by SoPhy, the file should exist on the server
        response = self.get_request(url=self.serverurl + '/config/load?format=pixelconfig&file=' + self.bpc_file)
        logger.debug(f'Response of loading binary pixel configuration file:{response.text}' )

        #  .... and the corresponding DACs file
        response = self.get_request(url=self.serverurl + '/config/load?format=dacs&file=' + self.dacs_file)
        logger.debug(f'Response of loading DACs file: {response.text}')

    def set_detector_config(self,trigger_mode = 'continuous',ntriggers=1,trigger_period=0.5) -> None : 
        """
        Sets the main detector parameters of the detector.

        Parameters
        ----------

        :trigger_mode: Set the trigger mode of the camera. currently, `CONTINUOUS` and `AUTOTRIGSTART_STOP` are implemented. 

        :ntriggers: Number of triggers. Set it to a very large number to have a "infinite" mode.

        :trigger_period: Unused currently. It will be used with other trigger modes.
        
        Results
        -------
        
        None
        """
        if trigger_mode == 'continuous' : 
            self.set_continuous_mode()
        elif trigger_mode == 'automatic' : 
            self.set_automatic_mode(ntriggers = ntriggers)
        self.put_request(url=self.serverurl +'/detector/config', data = json.dumps(self.detector_config))


        logger.debug(f'Loaded config :\nTriggerMode : {self.detector_config['TriggerMode']}\nExposureTime : {self.detector_config['ExposureTime']}\nTriggerPeriod : {self.detector_config['TriggerPeriod']}\nnTriggers : {self.detector_config['nTriggers']}')

    def set_continuous_mode(self, **kwargs) -> None :
        """
        Modifies the detector config for continuous acquisition mode. 

        Results
        -------
        None

        Notes
        -----
        The `TriggerPeriod` and the `ExposureTime` have to be set equal.
        """ 
        self.detector_config['TriggerMode'] = 'CONTINUOUS'
        self.detector_config['TriggerPeriod'] = self.exposure_time.magnitude
        self.detector_config['ExposureTime'] = self.exposure_time.magnitude
        self.detector_config['nTriggers'] = 1 

    def set_automatic_mode(self, **kwargs) -> None : 
        """
        Modifies the detector config for autotrigger start stop acquisition mode. 

        Results
        -------
        None

        Notes
        -----
        A minimal time of 2 ms is added for readout, between two exposures. 
        """ 
        self.detector_config['TriggerMode'] = 'AUTOTRIGSTART_TIMERSTOP'
        self.detector_config['TriggerPeriod'] = (self.exposure_time + self._readout_time ).magnitude
        self.detector_config['ExposureTime'] = self.exposure_time.magnitude
        self.detector_config['nTriggers'] = kwargs['ntriggers'] 

    def set_destination(self, profile_list : list[str]) -> None:
        """
        Sets the destination of the data 
        """
        for profile in profile_list : 
            assert profile in self.config.destination_names_list(), f"You have to first add this profile : {profile} to the available list of profiles : {self.config.destination_names_list()}"
        self.config.build_destination(profile_list) 
        self.put_request(url = self.serverurl + '/server/destination', data = json.dumps(self.config.destination))  

    ##############################
    # II. 3. Cheetah3 properties #
    ##############################

    @property
    def bpc_file(self) -> str: 
        if self._bpc_file is None : 
            self._bpc_file = self.config.config['CHEETAH3']['file_paths']['bpc'][0]
        return self._bpc_file

    @bpc_file.setter
    def bpc_file(self, filename : str) -> None : 
        if filename in self.config.config['CHEETAH3']['file_paths']['bpc'] :
            self._bpc_file = filename
        else :
            logger.info(f'the bpc file : {filename} is not part of the available files.')  

    @property
    def dacs_file(self) -> str : 
        if self._dacs_file is None : 
            self._dacs_file = self.config.config['CHEETAH3']['file_paths']['dacs'][0]
        return self._dacs_file

    @dacs_file.setter
    def dacs_file(self, filename : str) -> None : 
        if filename in self.config.config['CHEETAH3']['file_paths']['dacs'] :
            self._dacs_file = filename
        else :
            logger.info(f'the dacs file : {filename} is not part of the available files.') 

    @property
    def save_folder(self) -> str : 
        if self._save_folder is None : 
            self._save_folder = self.config.config['CHEETAH3']['file_paths']['data'][0]
        return self._save_folder

    @save_folder.setter
    def save_folder(self, folder_name : str) -> None : 
        if folder_name in self.config.config['CHEETAH3']['file_paths']['data'] :
            self._save_folder = folder_name
        else :
            logger.info(f'the dacs file : {folder_name} is not part of the available files.') 

    @property
    def exposure_time (self) -> float : 
        return self._exposure_time.to('s')
    
    @exposure_time.setter
    def exposure_time(self,value : float) -> None : 
        q = Quantity(value,'s')
        self._exposure_time = q.to('s') 

    @property
    def ntriggers(self) -> int : 
        return self._ntriggers

    @ntriggers.setter
    def ntriggers(self, value : int) -> None : 
        self._ntriggers = value

    @property
    def destination_profiles(self) -> list[str] : 
        return self._destination_profiles
    
    @destination_profiles.setter
    def destination_profiles(self,value : list[str]) -> None :
        self._destination_profiles = value

    ########################################
    # II. 4. Cheetah3 start/stop functions #
    ########################################

    def start(self):
        """Perform acquisition

        Keyword arguments:
        serverurl -- the URL of the running SERVAL (string)
        """
        self.set_detector_config(ntriggers=self.ntriggers, trigger_mode='automatic')
        self.set_destination(profile_list=self.destination_profiles)
        response = self.get_request(url=self.serverurl + '/measurement/start')
        logger.info('Response of acquisition start: ' + response.text)

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
            
###########################            
# III. Local testing code #
###########################

if __name__ == '__main__' : 
    cc = Cheetah3Config()
    cc.config
    # cam = Cheetah3()
    # cam.check_connection()
    # # cam.start_listening()
    # # print(cam.get_dashboard())
    # # print(cam.bpc_file)
    # # print(cam.detector_config)
    # # print(cam.serverurl)
    # cam.exposure_time = '0.5s'
    # cam.set_detector_config(trigger_mode='automatic',ntriggers=75)
    # # print(cam.get_detector_config())
    # cam.set_destination("basic")
    # # response = cam.get_request(url = cam.serverurl + '/server/destination')
    # # data = response.text
    # # # print(data)
    # cam.start()
    # # print(cam.get_dashboard())
    # cam.wait_for_acq()
    # i = 0 
    # measure = True
    # while measure :
    #     try :  
    #         print(cam.preview().sum() + i)
    #         i+=1
    #         if cam.get_status() ==  'DA_IDLE' : 
    #             measure= False
    #     except KeyboardInterrupt : 
    #         cam.stop()
    #         break
    # #     cam.wait_for_acq()
    #     # cam.wait_for_acq()
    # # print(cam.preview().shape)
