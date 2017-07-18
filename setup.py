from cx_Freeze import setup, Executable
import os

executable = Executable(script='py-purecloud-participant-data.py')

options = {
    "build_exe": {
        'include_files': [
            os.path.join(os.getcwd(), 'cacert.pem'),
            os.path.join(os.getcwd(), 'implicit.htm_'),
            os.path.join(os.getcwd(), 'configuration.json'),
			os.path.join(os.getcwd(), 'queries.json')
        ]
    }
}

setup(
    version='0.1',
    requires=['requests','PureCloudPlatformApiSdk'],
    options=options,
    executables=[executable])
