from uiautomator import Device
import subprocess
import time


resource_ids = {
    'wifi_connect': 'smartisanos:id/btn_ok'
}


configs = {
    'SSID': 'ZMI_B19A',
    'password': '91275682'
}


activities = {
    'setting': 'com.android.settings/com.android.settings.Settings',
    'wifi_setting': 'com.android.settings/.wifi.WifiSettingsActivity',
    'screen_off_setting': 'com.android.settings/.ScreenOffTimeoutActivity'
}


def adb_shell(cmd):
    subprocess.Popen(['adb', 'shell'] + cmd)


def start_activity(activity):
    subprocess.Popen(['adb', 'shell', 'am', 'start', '-n', activity])


def wifi():
    # Wi-Fi setting
    start_activity(activities['wifi_setting'])
    time.sleep(1)
    d(text=configs['SSID']).click()
    time.sleep(1)
    adb_shell(['input', 'text', configs['password']])
    time.sleep(1)
    d(resourceId=resource_ids['wifi_connect']).click()


def bt_off():
    start_activity(activities['setting'])
    print()


def scrn_off():
    # Screen-off setting
    start_activity(activities['setting'])
    time.sleep(1)
    d(resourceId='com.android.settings:id/list_view').child_by_text('Screen & Font',
                                                                    className='android.widget.RelativeLayout').click()
    time.sleep(0.5)
    d(text='Screen Timeout').click()
    time.sleep(0.5)
    d(text='30 minutes').click()


if __name__ == '__main__':
    d = Device()
    # wifi()
    # scrn_off()
    bt_off()



