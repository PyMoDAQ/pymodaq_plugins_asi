import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from qtpy import QtWidgets, QtCore
from qtpy.QtCore import QThread
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_utils.logger import set_logger, get_module_name
import collections

from pymodaq_plugins_asi.hardware.cheetah3 import Cheetah3

logger = set_logger(get_module_name(__file__))

################
# Code Outline #
################

# I. DAQ_2DViewer_Cheetah3
# I. 1. Parameters
# I. 2. Initialisation
# I. 3. Data acquisition
# II. Callback class
# III. Local testing code

############################
# I. DAQ_2DViewer_Cheetah3 #
############################

class DAQ_2DViewer_Cheetah3(DAQ_Viewer_base):
    """ Instrument plugin class for the Cheetah3 camera. It is a frame-based implementation of the camera.
    
    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    * This plugin is compatible with the Cheetah3 (2025) camera from Amsterdam Scientific instruments.
    * It has been tested with the Cheetah3 (2025).
    * This plugin was tested with PyMoDAQ 5.1.x on a windows 10 system.
    * To run this plugin you need another computer that controls the camera through ASI's Serval software.

    Attributes:
    -----------
    controller: Cheetah3
        The particular object that allows the communication with the camera.
    x_axis: Axis
        The horizontal axis of the camera #TODO Implement the dispersive scale
    y_axis: Axis
        The vertical axis of the camera
    binning : str
        The full binning status, either None (2D data), Vertical or Horizontal (1D data)
  
    Notes
    -----
    Additional attributes for the asynchronous acquistion

    callback: Cheetah3Callback
        The callback object for asynchronous acquistion
    callback_thread : QThread
        The callback lives on a different thread.
    startup_callback_signal
        The callback emits a signal when data are ready.

    Comments were made on how it works and can be found by search CT{0-99}.
    """

    ####################
    # I. 1. Parameters #
    ####################

    params = comon_parameters + [
        {'title' : "Frame-based camera settings", 'name' : 'camera_settings', 'type' : 'group', 'expanded' : True, 'children' : [
            {'title' : 'Exposure time', 'name' : 'exposure_time', 'type' : 'float', 'value' : 0.5},
            {'title' : 'Full binning', 'name' : 'binning', 'type' : 'itemselect', 'value' : dict(all_items = ['None','Vertical', 'Horizontal' ], selected = ['None']) }
        ]},
        {'title' : 'File paths', 'name' : 'file_paths', 'type' : 'group', 'expanded' : False, 'children' : [
            {'title' : 'bpc file path', 'name' : 'bpc_file_path', 'type' : 'str', 'value' : '/home/asi/bpc/'},
            {'title' : 'dacs file path', 'name' : 'dacs_file_path', 'type' : 'str', 'value' : '/home/asi/dacs/'},
            {'title' : 'save folder path', 'name' : 'save_folder_path', 'type' : 'str', 'value' : '/home/asi/data/'},
        ]}           
    ]

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        if param.name() == "exposure_time":
            self.controller.exposure_time = param.value()
        elif param.name() == 'binning' :
            self.binning = param.value()['selected']
        elif param.name() == 'bpc_file_path' : 
            self.controller.config.add_bpc_file(param.value())
        elif param.name() == 'dacs_file_path' : 
            self.controller.config.add_dacs_file(param.value())
        elif param.name() == 'save_folder_path' : 
            self.controller.config.add_save_folder(param.value())
        elif param.name() == 'destination' : 
            self.controller.config.build_destination(param.value()["selected"])

    ########################
    # I. 1. Initialisation #
    ########################

    live_mode_available = True
    # CT01. We create a signal object to start the execution of the callback thread.
    startup_callback_signal = QtCore.Signal()
    callback_signal = QtCore.Signal()

    
    def ini_attributes(self):
        self.controller: Cheetah3 = None

        self.x_axis = None
        self.y_axis = None
        self.binning = 'None'

    def ini_detector(self, controller=None):
        """Detector communication initialization

        Parameters
        ----------
        controller: (object)
            custom object of a PyMoDAQ plugin (Slave case). None if only one actuator/detector by controller
            (Master case)

        Returns
        -------
        info: str
        initialized: bool
            False if initialization failed otherwise True
        """
        self.controller = self.ini_detector_init(slave_controller = controller, new_controller = Cheetah3() ) 
        if self.is_master:
            initialized = self.controller.check_connection()
            info = "The DAQ_viewer Cheetah3 has successfully started"
            self.x_axis = Axis(data=np.linspace(0,  512 - 1, 512, dtype=int), label='Pixels', index=1)
            self.y_axis = Axis(data=np.linspace(0, 512 - 1, 512, dtype=int), label='Pixels', index=1)

            # CT02. An object (called callback), is instanciated.
            self.callback = Cheetah3Callback(self.controller)
            # CT03. A thread object is created (callback_thread)
            self.callback_thread = QtCore.QThread()
            # CT04. The thread object is made ready to be executed parallel to the main thread
            self.callback.moveToThread(self.callback_thread)
            # CT05. The function to be called by the thread is the callback object
            self.callback_thread.callback = self.callback
            # CT06. We make the thread ready to execute
            self.callback_thread.start()
            # CT07. We connect the signal to the execution of data read-out from the detector
            self.startup_callback_signal.connect(self.callback.start_readout)
            self.callback_signal.connect(self.callback.readout)
            # CT08. We connect the signal of the callback to the execution of PyMoDAQ GUI to display data.
            self.callback.data_sig.connect(self.emit_data)
            self.callback.data_sig_startup.connect(self.emit_data)
        else:
            self.controller = controller
            initialized = True

        profile_names = self.controller.config.destination_names_list()
        self.settings.addChild({'title' : 'Data destination', 'name' : 'destination', 'type' : 'itemselect', 'value' : dict(
            all_items = profile_names, selected =['live_preview']
        ), 'checkbox' : True})

        return info, initialized

    def close(self):
        """Terminate the communication protocol"""
        ## TODO for your custom plugin
        pass
        # raise NotImplementedError  # when writing your own plugin remove this line
        # if self.is_master:
        #     #  self.controller.your_method_to_terminate_the_communication()  # when writing your own plugin replace this line
        #     ...

    ##########################
    # I. 3. Data acquisition #
    ##########################

    def emit_data(self,data : np.ndarray):
        # Add a bool as arg so that I can pick finishing acquisition or current
        # Avant de broadcaster les données, il vaut mieux créer une copie pour éviter d'avoir des soucis de pointeur. Le reshape doit faire une copie à priori.
        """
            Fonction used to emit data obtained by callback.

            See Also
            --------
            daq_utils.ThreadCommand
        """
        # CT13. The callback emitted a signal to display data
        try:

            image = data.reshape((512,512)).astype(float) 
            dtp =[]
            if self.binning == 'None' : 
                dtp.append(DataFromPlugins(name='Cheetah3 image',
                                            data=[np.atleast_1d(
                                            image) ]))
            elif self.binning == 'Vertical' : 
                dtp.append(DataFromPlugins(name = 'Cheetah3 sum X',
                                data = [np.atleast_1d(image.sum(axis = 0))],
                                dim = 'Data1D'))
                
            elif self.binning == 'Horizontal' : 
                dtp.append(DataFromPlugins(name = 'Cheetah3 sum Y',
                                data = [np.atleast_1d(image.sum(axis = 1))],
                                dim = 'Data1D'))
                    
            self.dte_signal.emit(DataToExport('Cheetah3',
                                            data=dtp))
                # QtWidgets.QApplication.processEvents() 
            # CT14. Once the data are displayed we come back to the callback to fetch additional data.
            self.callback_signal.emit()
        except Exception as e:
            print("An exception occured in emit data")
            self.emit_status(ThreadCommand('Update_Status', [str(e), 'log']))

    def grab_data(self, Naverage=1, **kwargs):
        """Start a grab from the detector

        Parameters
        ----------
        Naverage: int
            Number of hardware averaging (if hardware averaging is possible, self.hardware_averaging should be set to
            True in class preamble and you should code this implementation)
        kwargs: dict
            others optionals arguments
        """
        ## TODO for your custom plugin: you should choose EITHER the synchrone or the asynchrone version following

        ##synchrone version (blocking function)
        try:

            if kwargs.get('live',False) == True :
                self.controller.ntriggers = int(2e9)
                self.controller.start()
                # CT9. We trigger the execution of the callback thread start_readout function. 
                self.startup_callback_signal.emit()

            else:
                self.controller.ntriggers = 1
                self.controller.start()
                self.startup_callback_signal.emit()


        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [str(e), "log"]))
        #########################################################

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        ## TODO for your custom plugin
        self.controller.stop()

######################
# II. Callback class #
######################

class Cheetah3Callback(QtCore.QObject):
    """

    """
    data_sig_startup = QtCore.Signal(np.ndarray)
    data_sig = QtCore.Signal(np.ndarray)

    def __init__(self, controller):
        super(Cheetah3Callback, self).__init__()
        self.buffer = collections.deque(maxlen=100)
        self.controller = controller
 
    def start_readout(self):
        while True :
            # CT10. We start a blocking function. It waits until data are avaible.
            current_image = self.controller.preview() 
            self.buffer.append(current_image)
            if len(self.buffer) > 0 :
                # CT11. One data are ready we want them displayed, so we signal the main thread
                self.data_sig_startup.emit(self.buffer.pop())
            if self.controller.get_status() == "DA_STOPPING" or self.controller.get_status() == "DA_IDLE" : 
                logger.info("Acquisition finished")
                break

            # CT12. The side thread continues to pile up data in the rolling buffer
    
    def readout(self) :
            # CT15. Since the loop is still running 
        while True :
            if len(self.buffer) > 0 : 
                break
            else :
                if self.controller.get_status() == "DA_STOPPING" or self.controller.get_status() == "DA_IDLE" :
                    return
        self.data_sig.emit(self.buffer.pop())

###########################            
# III. Local testing code #
###########################

if __name__ == '__main__':
    main(__file__)
