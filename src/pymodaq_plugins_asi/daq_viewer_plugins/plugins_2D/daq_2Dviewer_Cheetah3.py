import numpy as np

from pymodaq_utils.utils import ThreadCommand
from pymodaq_data.data import DataToExport, Axis
from pymodaq_gui.parameter import Parameter
from qtpy import QtWidgets, QtCore
from qtpy.QtCore import QThread
from pymodaq.control_modules.viewer_utility_classes import DAQ_Viewer_base, comon_parameters, main
from pymodaq.utils.data import DataFromPlugins
from pymodaq_utils.logger import set_logger, get_module_name

from pymodaq_plugins_asi.hardware.cheetah3 import Cheetah3

logger = set_logger(get_module_name(__file__))
# class PythonWrapperOfYourInstrument:
#     #  TODO Replace this fake class with the import of the real python wrapper of your instrument
#     pass

# TODO:
# (1) change the name of the following class to DAQ_2DViewer_TheNameOfYourChoice
# (2) change the name of this file to daq_2Dviewer_TheNameOfYourChoice ("TheNameOfYourChoice" should be the SAME
#     for the class name and the file name.)
# (3) this file should then be put into the right folder, namely IN THE FOLDER OF THE PLUGIN YOU ARE DEVELOPING:
#     pymodaq_plugins_my_plugin/daq_viewer_plugins/plugins_2D
class DAQ_2DViewer_Cheetah3(DAQ_Viewer_base):
    """ Instrument plugin class for a 2D viewer.
    
    This object inherits all functionalities to communicate with PyMoDAQ’s DAQ_Viewer module through inheritance via
    DAQ_Viewer_base. It makes a bridge between the DAQ_Viewer module and the Python wrapper of a particular instrument.

    TODO Complete the docstring of your plugin with:
        * The set of instruments that should be compatible with this instrument plugin.
        * With which instrument it has actually been tested.
        * The version of PyMoDAQ during the test.
        * The version of the operating system.
        * Installation instructions: what manufacturer’s drivers should be installed to make it run?

    Attributes:
    -----------
    controller: object
        The particular object that allow the communication with the hardware, in general a python wrapper around the
         hardware library.
         
    # TODO add your particular attributes here if any

    """
    live_mode_available = True
    callback_signal = QtCore.Signal()
    params = comon_parameters + [
        {'title' : 'Exposure time', 'name' : 'exposure_time', 'type' : 'float', 'value' : 0.5},
        {'title' : 'Display image', 'name' : 'is_image', 'type' : 'bool', 'value' : True},
        {'title' : 'X full binning', 'name' : 'binned_x', 'type' : 'bool', 'value' : False},
        {'title' : 'Y full binning', 'name' : 'binned_y', 'type' : 'bool', 'value' : False}    
    ]

    def ini_attributes(self):
        #  TODO declare the type of the wrapper (and assign it to self.controller) you're going to use for easy
        #  autocompletion
        self.controller: Cheetah3 = None

        # TODO declare here attributes you want/need to init with a default value

        self.x_axis = None
        self.y_axis = None
        self.is_image = True
        self.binned_x = False
        self.binned_y = False

    def commit_settings(self, param: Parameter):
        """Apply the consequences of a change of value in the detector settings

        Parameters
        ----------
        param: Parameter
            A given parameter (within detector_settings) whose value has been changed by the user
        """
        # TODO for your custom plugin
        if param.name() == "exposure_time":
            self.controller.exposure_time = param.value()
        elif param.name() == 'is_image' : 
            self.is_image = param.value()
        elif param.name() == 'binned_x' : 
            self.binned_x = param.value()
        elif param.name() == 'binned_y' : 
            self.binned_y = param.value()
        #elif ...

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
        # self.controller = self.ini_controller_init(slave_controller = controller, new_controller = Cheetah3() )  # TODO when writing your own plugin remove this line and modify the one below
        if self.is_master:
            self.controller = Cheetah3()  #instantiate you driver with whatever arguments are needed
            initialized = self.controller.check_connection()  # TODO
            info = "The DAQ_viewer Cheetah3 has successfully started"
            self.x_axis = Axis(data=np.linspace(0,  512 - 1, 512, dtype=int), label='Pixels', index=1)
            self.y_axis = Axis(data=np.linspace(0, 512 - 1, 512, dtype=int), label='Pixels', index=1)

            self.callback = MyCallback(self.controller.wait_for_acq)
            self.callback_thread = QtCore.QThread()
            self.callback.moveToThread(self.callback_thread)
            self.callback.data_sig.connect(self.emit_data)  # when the wait for acquisition returns (with data taken), emit_data will be fired

            self.callback_signal.connect(self.callback.read_status)
            self.callback_thread.callback = self.callback
            self.callback_thread.start()
        else:
            self.controller = controller
            initialized = True

        return info, initialized

    def close(self):
        """Terminate the communication protocol"""
        ## TODO for your custom plugin
        raise NotImplementedError  # when writing your own plugin remove this line
        if self.is_master:
            #  self.controller.your_method_to_terminate_the_communication()  # when writing your own plugin replace this line
            ...

    def emit_data(self):
        # Add a bool as arg so that I can pick finishing acquisition or current
        # Avant de broadcaster les données, il vaut mieux créer une copie pour éviter d'avoir des soucis de pointeur. Le reshape doit faire une copie à priori.
        """
            Fonction used to emit data obtained by callback.

            See Also
            --------
            daq_utils.ThreadCommand
        """
        try:
            for i in range(self.controller.ntriggers) : 
                image = self.controller.preview().reshape((512,512)).astype(float) 
                dtp =[]
                if self.is_image : 
                    dtp.append(DataFromPlugins(name='Cheetah3 image',
                                                data=[np.atleast_1d(
                                                image) ]))
                if self.binned_x : 
                    dtp.append(DataFromPlugins(name = 'Cheetah3 sum X',
                                    data = [np.atleast_1d(image.sum(axis = 0))],
                                    dim = 'Data1D'))
                    
                if self.binned_y : 
                    dtp.append(DataFromPlugins(name = 'Cheetah3 sum Y',
                                    data = [np.atleast_1d(image.sum(axis = 1))],
                                    dim = 'Data1D'))
                        
                self.dte_signal.emit(DataToExport('Cheetah3',
                                                data=dtp))
                QtWidgets.QApplication.processEvents()  # here to be sure the timeevents are executed even if in continuous grab mode
            # self.callback_signal.emit()
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
                self.callback_signal.emit()

            else:
                self.controller.ntriggers = 1
                self.controller.start()
                self.callback_signal.emit()  # will trigger the waitfor acquisition


        except Exception as e:
            self.emit_status(ThreadCommand('Update_Status', [str(e), "log"]))
        #########################################################

    def stop(self):
        """Stop the current grab hardware wise if necessary"""
        ## TODO for your custom plugin
        self.controller.stop()


class MyCallback(QtCore.QObject):
    """

    """
    data_sig = QtCore.Signal()
    # bool dans le data sig pour gérer le data_sig_temp

    def __init__(self, status_fn):
        super(MyCallback, self).__init__()
        self.status_fn = status_fn

    def read_status(self):
        ind = self.status_fn()
        if ind == 0 :
            logger.info('End of acquistion')
            pass
        elif ind == 1 :
            self.data_sig.emit()
            # faire 2 cas, soit l'acqusition d'1 frame est en cours : data_sig_temp
            # soit il a fini et il faut data_sig

        else : 
            raise NotImplementedError('Message to clarify TODO')

if __name__ == '__main__':
    main(__file__)
