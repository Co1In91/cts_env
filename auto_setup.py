from uiautomator import Device, JsonRPCError
from subprocess import Popen, PIPE
import sys
import logging


config = {
    'setting_main_activity': 'com.android.settings/.Settings',
    'check_wifi': {
        'main_activity': 'com.android.settings/.Settings',
        'ssid': 'ASUS',
        'password': 'haifeng2211'
    },
    'check_language':{
        'activity': 'android.settings.LOCALE_SETTINGS'
    }
}


class AdvanceDevice(Device):

    @staticmethod
    def shell(cmd):
        return Popen(['adb', 'shell', '{0}'.format(cmd)]).communicate()

    @staticmethod
    def start_activity(activity):
        Popen(['adb', 'shell', 'am', 'start', '-n', activity], stdout=PIPE, stderr=PIPE)

    @staticmethod
    def start_activity_a(activity):
        Popen(['adb', 'shell', 'am', 'start', '-a', activity], stdout=PIPE, stderr=PIPE)

    @staticmethod
    def current_activity():
        cmd = 'adb shell dumpsys window windows | grep -E "mCurrentFocus" | cut -d " " -f 5 | cut -d "}" -f 1'
        p = Popen(cmd.split(), stdout=PIPE, stderr=PIPE)
        activity = p.stdout.read()
        return str(activity, encoding='utf-8').strip()


class Setup:
    d = Device
    device_id = None
    log = None
    device = None

    def __init__(self, device_id=None):
        self.log = self.logger()
        self.device_id = device_id
        self.device = self.connect_device()

    def make_dump_file(self):
        self.device.dump(self.device.current_activity().split('/')[0] + '.xml')

    def default(self):
        self.check_display()
        self.check_bt()
        self.check_wifi()
        self.check_location()
        self.disable_scrn_lock()

    def connect_device(self):
        if self.device_id:
            device = AdvanceDevice()
        else:
            device = AdvanceDevice(self.device_id)
        self.log.debug('{0} is connected'.format(device.info['productName']))
        return device

    def disable_scrn_lock(self):
        self.log.debug('disable screen lock')
        self.device.start_activity(config['setting_main_activity'])
        self.device(className='android.support.v7.widget.RecyclerView').child_by_text(
            'Security', allow_scroll_search=True, className='android.widget.TextView'
        ).click()
        self.device(text='Screen lock').click()
        self.device(text='None').click()

    def back_to_setting(self):
        while self.device.current_activity() != config['setting_main_activity']:
            self.device.press.back()

    def check_location(self):
        self.log.debug('switch location mode to high accuracy')
        self.device.start_activity(config['setting_main_activity'])
        self.device(className='android.support.v7.widget.RecyclerView').child_by_text(
            'Location', allow_scroll_search=True, className='android.widget.TextView'
        ).click()

        if self.device(resourceId='com.android.settings:id/switch_bar').text == 'Off':
            self.device(resourceId='com.android.settings:id/switch_bar').click()

        self.device(text='Mode').click()
        self.device(text='High accuracy').click()
        self.log.debug('done')

    def check_bt(self):
        self.log.debug('turn BT off')
        self.device.start_activity(config['setting_main_activity'])
        self.device(className='android.support.v7.widget.RecyclerView').child_by_text(
            'Bluetooth', allow_scroll_search=True, className='android.widget.TextView'
        ).click()
        if self.device(resourceId='com.android.settings:id/switch_bar').text != 'Off':
            self.device(resourceId='com.android.settings:id/switch_bar').click()
        self.log.debug('done')

    def check_display(self):
        self.log.debug('set sleep time to 30 min')
        self.device.start_activity(config['check_display']['main_activity'])
        self.device(className='android.support.v7.widget.RecyclerView').child_by_text(
            'Display', allow_scroll_search=True, className='android.widget.TextView'
        ).click()
        if self.device.current_activity().endswith('com.android.settings.Settings$DisplaySettingsActivity'):
            self.device(text='Sleep').click()
            self.device(text='30 minutes').click()
            self.log.debug('done')

        self.log.debug('turn off auto-rotate')
        self.device(resourceId='com.android.settings:id/list').child_by_text(
            'When device is rotated', allow_scroll_search=True, className='android.widget.TextView'
        ).click()
        self.device(text='Stay in portrait view').click()
        self.log.debug('done')

    def check_wifi(self):
        self.log.debug('connect Wi-Fi')
        self.device.start_activity(config['setting_main_activity'])
        self.device(className='android.support.v7.widget.RecyclerView').child_by_text(
            'Wi‑Fi', allow_scroll_search=True
        ).click()
        if self.device(resourceId='com.android.settings:id/switch_bar').text == 'Off':
            self.device(resourceId='com.android.settings:id/switch_bar').click()

        try:
            self.device(resourceId='com.android.settings:id/list').child_by_text(
                config['check_wifi']['ssid'], allow_scroll_search=True, className='android.widget.TextView'
            ).click()
        except JsonRPCError:
            self.log.error('can not find SSID %s' % config['check_wifi']['ssid'])
            return False

        if not self.device(text='FORGET').exists:
            self.device(resourceId='com.android.settings:id/password').click()
            self.device.shell('input text ' + config['check_wifi']['password'])
            self.device(text='CONNECT', className='android.widget.Button').click()
        self.log.debug('done')

    @staticmethod
    def logger():
        logger = logging.getLogger('test')
        logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(funcName)s] %(message)s')
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.debug('init')
        return logger


if __name__ == '__main__':
    setup = Setup()
    if len(sys.argv) > 1:
        if sys.argv[1] == 'dump':
            setup.make_dump_file()
            sys.exit(0)
    setup.default()
