class Cheetah3Constants :
    detector_config = {
        "LogLevel" : 1,
        "Fan1PWM" : 100,
        "Fan2PWM" : 100,
        "BiasVoltage" : 100,
        "BiasEnabled" : True,
        "Polarity" : "Positive",
        "PeriphClk80" : False,
        'ChainMode' : None,
        "TriggerIn" : 0,
        "TriggerOut" : 0,
        "TriggerPeriod" : 0.02,
        "ExposureTime" : 0.0002,
        "TriggerDelay" : 0.0,
        "TriggerMode" : "AUTOTRIGSTART_TIMERSTOP",
        "nTriggers" : 100,
        "Tdc" : [ "PN0123", "PN0123" ],
        "GlobalTimestampInterval" : 10.0,
        "ExternalReferenceClock" : False
        }

    trigger_modes = ['PEXSTART_NEXSTOP',
                     'NEXSTART_PEXSTOP',
                     'PEXSTART_TIMERSTOP',
                     'NEXSTART_TIMERSTOP',
                     'AUTOTRIGSTART_TIMERSTOP',
                     'CONTINUOUS',
                     'SOFTWARESTART_TIMERSTOP',
                     'SOFTWARESTART_SOFTWARESTOP'
                     ]
    
    
    