import oss2
import bs4
import requests
import re
import os
import sys
from urllib.parse import urlsplit
from optparse import OptionParser
import yaml
from zipfile import ZipFile as zf
from time import sleep


pkg_type = {
    'android-cts-\d': 'android-cts',
    'android-cts-verifier-\d': 'android-cts-verifier',
    'android-cts-media-\d': 'android-cts-media'
}


def percentage(consumed_bytes, total_bytes):
    if total_bytes:
        rate = int(100 * (float(consumed_bytes) / float(total_bytes)))
        print('\r{0}% '.format(rate), end='')
        sys.stdout.flush()


class Package:
    pkg_type = ''

    def __init__(self, url):
        self.url = url
        self.file_name = urlsplit(self.url).path.split('/')[-1]
        self.pure_name = '.'.join(self.file_name.split('.')[:-1])
        for k, v in pkg_type.items():
            if re.match(k, self.file_name):
                self.pkg_type = v

    def __getitem__(self):
        return self.file_name

    def __str__(self):
        return self.file_name

    @property
    def android_version(self):
        if self.pkg_type != 'android-cts-media':
            return re.search(r'-(\d+\.\d+)', self.file_name).group(1)
        else:
            return ''

    @property
    def release(self):
        if self.pkg_type != 'android-cts-media':
            return re.search(r'_r(\d+)-', self.file_name).group(1)
        else:
            return re.search(r'-(\d\.\d+)\.zip', self.file_name).group(1)

    @property
    def platform(self):
        if self.pkg_type != 'android-cts-media':
            return re.search(r'_r\d+-(.+)\.zip', self.file_name).group(1)
        else:
            return ''


class PackageManager:
    base_path = os.path.abspath(os.path.dirname(__file__))
    origin = 'https://source.android.com/compatibility/cts/downloads'
    access_key_id = ''
    access_key_secret = ''
    bucket = ''
    endpoint = ''
    mirror = ''
    proxy = {}

    def __init__(self):
        self.read_config()
        self.domain = urlsplit(self.origin).netloc
        if not os.path.exists(os.path.join(self.base_path, 'packages')):
            os.mkdir(os.path.join(self.base_path, 'packages'))

    def read_config(self):
        if os.path.exists(os.path.join(self.base_path, 'cts.yaml')):
            parsed_config = yaml.load(open(os.path.join(self.base_path, 'cts.yaml')))
            self.access_key_id = parsed_config['oss'][0]['access_key_id']
            self.access_key_secret = parsed_config['oss'][0]['access_key_secret']
            self.bucket = parsed_config['oss'][0]['bucket']
            self.endpoint = parsed_config['oss'][0]['endpoint']
            self.mirror = parsed_config['mirror'][0]['link']

        else:
            print('missing config.yaml, downloading')

    def fetch_package_list(self, remote=None):
        proxy_url = {}
        if not remote:
            remote = self.origin
            proxy_url = self.proxy
        print('fetching {0}\n'.format(remote))
        content = requests.get(remote, proxies=proxy_url).content
        soup = bs4.BeautifulSoup(content, 'html.parser')
        a_tags = soup.find_all(href=re.compile('dl.google.com'))
        pkg_urls = list(map(lambda x: x.get('href'), a_tags))
        # save downloads.html
        if remote == self.origin:
            print('update html to oss')
            oss_auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            bucket = oss2.Bucket(oss_auth, self.endpoint, self.bucket)
            bucket.put_object('cts_packages.html', content, progress_callback=percentage)
            bucket.put_object_acl('cts_packages.html', oss2.OBJECT_ACL_PUBLIC_READ)
            print('\n')
        pkg_list = [Package(url) for url in pkg_urls]
        print('{0:30}\t{2:10}\t{1:10}\t{3:10}'.format('Type', 'Android', 'Release', 'Platform'))
        for pkg in pkg_list:
            print('{0:30}\tr{2:10}\t{1:10}\t{3:10}'.format(
                pkg.pkg_type, pkg.android_version, pkg.release, pkg.platform))
        print('\n')
        return pkg_list

    def push_to_oss(self):
        pkg_list = self.fetch_package_list()
        pkg_dir = os.path.join(self.base_path, 'packages')
        if not os.path.exists(pkg_dir):
            os.mkdir(pkg_dir)

        print('\n\nSyncing packages to OSS')
        oss_auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        bucket = oss2.Bucket(oss_auth, self.endpoint, self.bucket)
        for pkg in pkg_list:
            if not bucket.object_exists(pkg.file_name):
                print('remote: {0} is not exist'.format(pkg))
                # check local package
                if os.path.exists(os.path.join(pkg_dir, pkg.file_name)):
                    print('local: {0} is exist'.format(pkg))
                else:
                    print('local: {0} is not exist'.format(pkg))
                    print('downloading {0}'.format(pkg.file_name))
                    r = requests.get(pkg.url, stream=True)
                    f = open(os.path.join(pkg_dir, pkg.file_name), 'wb')
                    for chunk in r.iter_content(chunk_size=512):
                        if chunk:
                            f.write(chunk)

                # upload to oss
                sleep(2)
                print('pushing {0}'.format(pkg.file_name))
                bucket.put_object_from_file(pkg.file_name, os.path.join(self.base_path, 'packages', pkg.file_name),
                                            progress_callback=percentage)
                bucket.put_object_acl(pkg.file_name, oss2.OBJECT_ACL_PUBLIC_READ)
                os.remove(os.path.join(self.base_path, 'packages', pkg.file_name))

            else:
                print('remote: {0} is exist'.format(pkg))

    def clone(self):
        oss_auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        bucket = oss2.Bucket(oss_auth, self.endpoint, self.bucket)
        pkg_list = self.fetch_package_list(remote=self.mirror)
        pkg_dir = os.path.join(self.base_path, 'packages')

        print('\n\nCloning packages to local: {0}'.format(pkg_dir))
        for pkg in pkg_list:
            if not os.path.exists(os.path.join(pkg_dir, pkg.file_name)):
                if not bucket.object_exists(pkg.file_name):
                    print('remote: {0} is not exist'.format(pkg))
                else:
                    print('downloading {0}'.format(pkg.file_name))
                    local_dst = os.path.join(pkg_dir, pkg.file_name)
                    bucket.get_object_to_file(pkg.file_name, local_dst, progress_callback=percentage)
                    print('local: {0} is exist'.format(pkg))
                    zf(local_dst, 'r').extractall(os.path.join(pkg_dir, pkg.file_name))

    def download(self, android_version, platform='linux_x86-arm'):
        oss_auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        bucket = oss2.Bucket(oss_auth, self.endpoint, self.bucket)
        pkg_list = self.fetch_package_list(remote=self.mirror)
        pkg_dir = os.path.join(self.base_path, 'packages')
        count = 0
        for pkg in pkg_list:
            if str(pkg.android_version) == str(android_version) and platform in pkg.platform:
                count += 1
                local_dst = os.path.join(pkg_dir, pkg.file_name)
                if pkg.file_name in os.listdir(os.path.join(self.base_path, 'packages')):
                    print('local: {0} is exist'.format(pkg))
                    zf(local_dst, 'r').extractall(os.path.join(self.base_path, 'packages', pkg.pure_name))
                    os.remove(local_dst)
                elif pkg.pure_name in os.listdir(os.path.join(self.base_path, 'packages')):
                    pass
                else:
                    print('downloading {0}'.format(pkg.file_name))
                    bucket.get_object_to_file(pkg.file_name, local_dst, progress_callback=percentage)
                    zf(local_dst, 'r').extractall(os.path.join(self.base_path, 'packages', pkg.pure_name))
                    os.remove(local_dst)

        if not count:
            print('packages not found')

    def download_media(self, media_version):
        oss_auth = oss2.Auth(self.access_key_id, self.access_key_secret)
        bucket = oss2.Bucket(oss_auth, self.endpoint, self.bucket)
        pkg_list = self.fetch_package_list(remote=self.mirror)
        pkg_dir = os.path.join(self.base_path, 'packages')
        count = 0
        for pkg in pkg_list:
            if str(pkg.release) == str(media_version) and pkg.pkg_type == 'android-cts-media':
                count += 1
                local_dst = os.path.join(pkg_dir, pkg.file_name)
                if pkg.file_name in os.listdir(os.path.join(self.base_path, 'packages')):
                    print('local: {0} is exist'.format(pkg))
                    zf(local_dst, 'r').extractall(os.path.join(self.base_path, 'packages', pkg.pure_name))
                    os.remove(local_dst)
                elif pkg.pure_name in os.listdir(os.path.join(self.base_path, 'packages')):
                    pass
                else:
                    print('downloading {0}'.format(pkg.file_name))
                    bucket.get_object_to_file(pkg.file_name, local_dst, progress_callback=percentage)
                    zf(local_dst, 'r').extractall(os.path.join(self.base_path, 'packages', pkg.pure_name))
                    os.remove(local_dst)
        if not count:
            print('packages not found')


if __name__ == '__main__':
    pm = PackageManager()

    parser = OptionParser('usage: python3 CTS.py [-d <filename>|-p|-c|-o|-l|-h]')
    parser.add_option("-p", "--push", action="store_true",
                      dest="push_to_oss",
                      default=False,
                      help="push cts sources to aliyun oss if your network can access android official site")

    parser.add_option("-c", "--clone", action="store_true",
                      dest="clone",
                      default=False,
                      help="clone all packages from origin")

    parser.add_option("-o", "--origin", action="store_true",
                      dest="fetch",
                      default=False,
                      help="list all origin packages")

    parser.add_option("-l", "--list", action="store_true",
                      dest="fetch_mirror",
                      default=False,
                      help="list all mirror packages")

    parser.add_option("-a", "--android", action="store",
                      dest="download_android",
                      default=0,
                      help="download a package, -d <ANDROID_VERSION> ")

    parser.add_option("-m", "--media", action="store",
                      dest="download_media",
                      default=0,
                      help="download a package, -m <MEDIA_VERSION> ")

    parser.add_option("-x", "--proxy", action="store",
                      dest="proxy",
                      help="push package in proxy")

    (options, args) = parser.parse_args()

    if options.proxy:
        pm.proxy = {'https': options.proxy}

    if options.push_to_oss:
        pm.push_to_oss()

    elif options.clone:
        pm.clone()

    elif options.fetch:
        pm.fetch_package_list()

    elif options.fetch_mirror:
        pm.fetch_package_list(remote=pm.mirror)

    elif options.download_android:
        pm.download(options.download_android)

    elif options.download_media:
        pm.download_media(options.download_media)

    else:
        parser.print_help()

