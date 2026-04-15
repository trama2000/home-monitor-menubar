from setuptools import setup

APP = ['home_monitor.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,
    'plist': {
        'LSUIElement': True,  # Hide from Dock
        'CFBundleName': 'Home Monitor',
        'CFBundleDisplayName': 'Home Monitor',
        'CFBundleIdentifier': 'com.trama2000.homemonitor',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True,
        },
    },
    'packages': ['requests', 'rumps'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    install_requires=['rumps', 'requests'],
)
