# -*- coding: utf-8 -*-
import os
import re
import time
import json
import random
import mimetypes
import xml.dom.minidom
from traceback import format_exc

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder


class WebWeChat(object):
    def run(self):
        print('微信网页版 ... 开动')
        while True:
            self.get_uuid()
            print('[*] 正在获取 uuid ... ')
            self.show_qrcode()
            print('请使用微信扫描二维码以登录 ... ')
            if not self.wait_login():
                print('[*] 请在手机上点击确认以登录 ... ')
                continue
            if not self.wait_login(0):
                continue
            break
        self.login()
        print('[*] 正在登录 ... ')
        self.init()
        print('[*] 微信初始化 ... ')
        self.status_notify()
        print('[*] 开启状态通知 ... ')
        self.get_contact()
        print('[*] 获取联系人 ... ')
        print('[*] 应有 %s 个联系人，读取到联系人 %d 个' % (self.memberCount, len(self.memberList)))
        print('[*] 共有 %d 个群 | %d 个直接联系人 | %d 个特殊账号 ｜ %d 公众号或服务号' % (len(self.groupList),
                                                                    len(self.contactList), len(self.specialUsersList),
                                                                    len(self.publicUsersList)))
        self.batch_get_contact()
        print('[*] 获取群 ... ')
        self.listening_loop()

    def __init__(self):
        self.my_info = {}
        self.memberList = []
        self.memberCount = 0
        self.contactList = []  # 好友列表
        self.groupList = []  # 群列表
        self.groupMemeberList = []  # 群成员列表
        self.publicUsersList = []  # 公众号／服务号列表
        self.specialUsersList = []  # 特殊账号列表

        self.uuid = ''
        self.base_uri = ''
        self.base_host = ''
        self.redirect_uri = ''
        self.uin = ''
        self.sid = ''
        self.skey = ''
        self.file_index = -1
        self.pass_ticket = ''
        self.deviceId = 'e' + repr(random.random())[2:17]
        self.base_request = {}
        self.synckey = ''
        self.SyncKey = []
        self.syncHost = ''
        self.__user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) ' \
                            'Chrome/48.0.2564.109 Safari/537.36'
        self.__session = requests.session()
        self.__session.headers = {'User-agent': self.__user_agent}

    def get_uuid(self):
        url = 'https://login.weixin.qq.com/jslogin'
        params = {
            'appid': 'wx782c26e4c19acffb',
            'fun': 'new',
            'lang': self.LANGUAGE,
            '_': int(time.time())}
        r = self.__session.post(url, params=params)
        data = r.text
        if data == '':
            return False
        pm = re.search(r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"', data)
        if pm:
            code = pm.group(1)
            self.uuid = pm.group(2)
            return code == '200'
        return False

    def show_qrcode(self):
        url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
        params = {
            't': 'webwx',
            '_': int(time.time())
        }
        data = self.__session.post(url, params).content
        if data == '':
            return
        with open("qrcode.jpg", "wb") as f:
            f.write(data)
        os.startfile("qrcode.jpg")

    def wait_login(self, tip=1):
        time.sleep(tip)
        url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (
            tip, self.uuid, int(time.time()))
        data = self.__session.get(url).text
        if data == '':
            return False
        pm = re.search(r'window.code=(\d+);', data)
        code = pm.group(1)

        if code == '201':
            return True
        elif code == '200':
            pm = re.search(r'window.redirect_uri="(\S+?)";', data)
            r_uri = pm.group(1) + '&fun=new'
            self.redirect_uri = r_uri
            self.base_uri = r_uri[:r_uri.rfind('/')]
            self.base_host = self.base_uri[8:].partition('/')[0]
            return True
        elif code == '408':
            print('[登陆超时]')
        else:
            print('[登陆异常]')
        return False

    def login(self):
        data = self.__session.get(self.redirect_uri).text
        if data == '':
            return False
        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement
        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data

        if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
            return False

        self.base_request = {
            'Uin': int(self.uin),
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.deviceId,
        }
        return True

    def init(self):
        url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        params = {
            'BaseRequest': self.base_request
        }
        self.__session.headers.update({'ContentType': 'application/json; charset=UTF-8'})
        r = self.__session.post(url, json=params)
        r.encoding = 'utf-8'
        dic = r.json()
        if dic == '':
            return False
        self.SyncKey = dic['SyncKey']
        self.my_info = dic['User']
        self.synckey = '|'.join(
            [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])
        return dic['BaseResponse']['Ret'] == 0

    def status_notify(self):
        url = self.base_uri + '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % self.pass_ticket
        params = {
            'BaseRequest': self.base_request,
            "Code": 3,
            "FromUserName": self.my_info['UserName'],
            "ToUserName": self.my_info['UserName'],
            "ClientMsgId": int(time.time())
        }
        r = self.__session.post(url, json=params)
        r.encoding = 'utf-8'
        dic = r.json()
        if dic == '':
            return False

        return dic['BaseResponse']['Ret'] == 0

    def get_contact(self):
        url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        r = self.__session.post(url, json={})
        r.encoding = 'utf-8'
        dic = r.json()
        if dic == '':
            return False

        self.memberCount = dic['MemberCount']
        self.memberList = dic['MemberList']
        contact_list = self.memberList[:]

        for i in range(len(contact_list) - 1, -1, -1):
            contact = contact_list[i]
            if contact['VerifyFlag'] & 8 != 0:  # 公众号/服务号
                contact_list.remove(contact)
                self.publicUsersList.append(contact)
            elif contact['UserName'] in self.SpecialUsers:  # 特殊账号
                contact_list.remove(contact)
                self.specialUsersList.append(contact)
            elif contact['UserName'].find('@@') != -1:  # 群聊
                contact_list.remove(contact)
                self.groupList.append(contact)
            elif contact['UserName'] == self.my_info['UserName']:  # 自己
                contact_list.remove(contact)
        self.contactList = contact_list
        return True

    def batch_get_contact(self):
        url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.base_request,
            "Count": len(self.groupList),
            "List": [{"UserName": g['UserName'], "EncryChatRoomId": ""} for g in self.groupList]}
        r = self.__session.post(url, json=params)
        r.encoding = 'utf-8'
        dic = r.json()
        if dic == '':
            return False

        self.groupList = dic['ContactList']
        for i in range(dic['Count'] - 1, -1, -1):
            for member in self.groupList[i]['MemberList']:
                self.groupMemeberList.append(member)
        return True

    def get_group_user(self, group_id):
        url = self.base_uri + '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.base_request,
            "Count": 1,
            "List": [{"UserName": group_id, "EncryChatRoomId": ""}]}
        r = self.__session.post(url, json=params)
        r.encoding = 'utf-8'
        dic = r.json()
        if dic == '':
            return False
        user_list = dic['ContactList'][0]['MemberList']
        return user_list

    def test_sync_host(self):
        """
        测试同步主机
        :return:连接成功返回True失败返回False
        """
        for host1 in ['webpush.', 'webpush2.']:
            self.syncHost = host1 + self.base_host
            try:
                retcode = self.sync_check()[0]
            except Exception as e:
                print(e)
                retcode = -1
            if retcode == '0':
                return True
        return False

    def sync_check(self):
        params = {
            'r': int(time.time()),
            'sid': self.sid,
            'uin': self.uin,
            'skey': self.skey,
            'deviceid': self.deviceId,
            'synckey': self.synckey,
            '_': int(time.time())}
        url = 'https://' + self.syncHost + '/cgi-bin/mmwebwx-bin/synccheck'
        try:
            r = self.__session.get(url, params=params)
            r.encoding = 'utf-8'
            data = r.text
            pm = re.search(r'window.synccheck=\{retcode:"(\d+)",selector:"(\d+)"\}', data)
            retcode = pm.group(1)
            selector = pm.group(2)
            return [retcode, selector]
        except Exception as e:
            print(e)
            return [-1, -1]

    def sync(self):
        url = self.base_uri + '/webwxsync?sid=%s&skey=%s&lang=en_US&pass_ticket=%s' % (
            self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.base_request,
            'SyncKey': self.SyncKey,
            'rr': ~int(time.time())}
        try:
            r = self.__session.post(url, json=params, timeout=60)
            r.encoding = 'utf-8'
            dic = r.json()
            if dic['BaseResponse']['Ret'] == 0:
                self.SyncKey = dic['SyncKey']
                self.synckey = '|'.join(
                    [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])
            return dic
        except Exception as e:
            print(e)
            return None

    def listening_loop(self):
        print('[*] 进入消息监听模式 ... 成功')
        self.test_sync_host()
        print('[*] 同步线路测试成功 ... ')
        while True:
            check_time = time.time()
            try:
                [retcode, selector] = self.sync_check()
                if retcode == '1100':  # 从微信客户端上登出
                    print('你在微信客户端上登出，线程结束')
                    break
                elif retcode == '1101':  # 从其它设备上登了网页微信
                    print('你从其它设备上登了网页微信，线程结束')
                    break
                elif retcode == '0':
                    if selector == 0:
                        print('无事件')
                    else:
                        r = self.sync()
                        print('同步微信信息 sync_check:', retcode, selector, r['AddMsgList'])

                else:
                    print('[DEBUG] sync_check:', retcode, selector)
            except Exception as e:
                print('[ERROR] Except in proc_msg , ', e, format_exc())
            # 睡眠
            self.send_image('C:\\Users\\dingf\\Desktop\\好胸.gif')
            check_time = time.time() - check_time
            if check_time < 0.8:
                print('睡眠', 1 - check_time)
                time.sleep(10 - check_time)

    def upload_media(self, file_path, is_img=False):
        self.file_index += 1
        if not os.path.exists(file_path):
            print('[ERROR] File not exists.')
            return None
        url_1 = 'https://file.' + self.base_host + '/cgi-bin/mmwebwx-bin/webwxuploadmedia?f=json'
        url_2 = 'https://file2.' + self.base_host + '/cgi-bin/mmwebwx-bin/webwxuploadmedia?f=json'
        flen = str(os.path.getsize(file_path))
        ftype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        multipart_encoder = MultipartEncoder(
            fields={
                'id': 'WU_FILE_%s' % str(self.file_index),
                'name': os.path.basename(file_path),
                'type': ftype,
                'lastModifiedDate': time.strftime('%m/%d/%Y, %H:%M:%S GMT+0800 (CST)'),
                'size': flen,
                'mediatype': 'pic' if is_img else 'doc',
                'uploadmediarequest': json.dumps({
                    'BaseRequest': self.base_request,
                    'ClientMediaId': int(time.time()),
                    'TotalLen': flen,
                    'StartPos': 0,
                    'DataLen': flen,
                    'MediaType': 4}, ensure_ascii=False).encode('utf8'),
                'webwx_data_ticket': self.__session.cookies['webwx_data_ticket'],
                'pass_ticket': self.pass_ticket,
                'filename': (os.path.basename(file_path), open(file_path, 'rb'), ftype.split('/')[1])})
        data = re.sub(b'\*utf-8\'\'(\S+)\r', lambda m: b'"' + m.group(1) + b'"\r', multipart_encoder.to_string())
        headers = {
            'Host': 'file2.wx.qq.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:42.0) Gecko/20100101 Firefox/42.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://wx2.qq.com/',
            'Content-Type': multipart_encoder.content_type,
            'Origin': 'https://wx2.qq.com',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'}
        try:
            r = self.__session.post(url_1, data=data, headers=headers)
            if r.json()['BaseResponse']['Ret'] != 0:
                # 当file返回值不为0时则为上传失败，尝试第二服务器上传
                r = self.__session.post(url_2, data=data, headers=headers)
            if r.json()['BaseResponse']['Ret'] != 0:
                print('[ERROR] Upload media failure.')
                return None
            mid = r.json()['MediaId']
            return mid
        except Exception as e:
            print(e)
            return None

    def send_text(self, text, to='filehelper'):
        """
        发送文本消息
        :param text: 文本消息
        :param to: 接受者id:UserName;默认 文件传输助手
        :return:
        """
        url = self.base_uri + '/webwxsendmsg?pass_ticket=%s' % self.pass_ticket
        msg_id = str(int(time.time() * 1000)) + str(random.random())[:5].replace('.', '')
        params = {
            'BaseRequest': self.base_request,
            'Msg': {
                "Type": 1,
                "Content": text,
                "FromUserName": self.my_info['UserName'],
                "ToUserName": to,
                "LocalID": msg_id,
                "ClientMsgId": msg_id}}
        data = json.dumps(params, ensure_ascii=False).encode('utf8')  # 否则会乱码
        r = self.__session.post(url, data=data)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def send_file(self, file_path, uid='filehelper'):
        mid = self.upload_media(file_path)
        if mid is None or not mid:
            return False
        return self.send_file_by_mid(mid, file_path, uid)

    def send_file_by_mid(self, mid, file_path, uid):
        url = self.base_uri + '/webwxsendappmsg?fun=async&f=json&pass_ticket=' + self.pass_ticket
        msg_id = str(int(time.time() * 1000)) + str(random.random())[:5].replace('.', '')
        data = {
            'BaseRequest': self.base_request,
            'Msg': {
                'Type': 6,
                'Content': (
                    "<appmsg appid='wxeb7ec651dd0aefa9' sdkver=''><title>%s</title><des></des><action></action>"
                    "<type>6</type><content></content><url></url><lowurl></lowurl><appattach><totallen>%s</totallen>"
                    "<attachid>%s</attachid><fileext>%s</fileext></appattach><extinfo></extinfo></appmsg>" % (
                        os.path.basename(file_path), str(os.path.getsize(file_path)), mid, file_path.split('.')[-1])),
                'FromUserName': self.my_info['UserName'],
                'ToUserName': uid,
                'LocalID': msg_id,
                'ClientMsgId': msg_id}}
        try:
            r = self.__session.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf8'))
            if r.json()['BaseResponse']['Ret'] == 0:
                return True
            else:
                return False
        except Exception as e:
            print(e)
            return False

    def send_image(self, image_path, uid='filehelper'):
        mid = self.upload_media(image_path, is_img=True)
        if mid is None:
            return False
        url = self.base_uri + '/webwxsendmsgimg?fun=async&f=json'
        data = {
            'BaseRequest': self.base_request,
            'Msg': {
                'Type': 3,
                'MediaId': mid,
                'FromUserName': self.my_info['UserName'],
                'ToUserName': uid,
                'LocalID': str(time.time() * 1e7),
                'ClientMsgId': str(time.time() * 1e7)}}
        if image_path[-4:] == '.gif':
            url = self.base_uri + '/webwxsendemoticon?fun=sys'
            data['Msg']['Type'] = 47
            data['Msg']['EmojiFlag'] = 2
        try:
            r = self.__session.post(url, data=json.dumps(data, ensure_ascii=False).encode('utf8'))
            if r.json()['BaseResponse']['Ret'] == 0:
                return True
            else:
                return False
        except Exception as e:
            print(e)
            return False

    LANGUAGE = 'zh_CN'
    SpecialUsers = ['blogapp', 'blogappweixin', 'brandsessionholder', 'facebookapp', 'feedsapp', 'filehelper',
                    'floatbottle', 'fmessage', 'gh_22b87fa7cb3c', 'lbsapp', 'masssendapp', 'medianote', 'meishiapp',
                    'newsapp', 'notification_messages', 'officialaccounts', 'qmessage', 'qqfriend', 'qqmail', 'qqsync',
                    'readerapp', 'shakeapp', 'tmessage', 'userexperience_alarm', 'voip', 'weibo', 'weixin',
                    'weixinreminder', 'wxid_novlwrv3lqwv11', 'wxitil']

